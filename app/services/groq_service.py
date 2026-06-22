"""GroqProvider — calls Groq API, parses response, falls back to deterministic ranker."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import settings
from app.models.preferences import UserPreferences
from app.models.recommendation import GroqRawResponse, Recommendation
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_BACKOFF_BASE = 2.0  # seconds
_TIMEOUT = 30        # seconds


class GroqServiceError(RuntimeError):
    """Raised when Groq is unreachable and fallback is also unavailable."""


class GroqProvider:
    """
    Wraps the Groq SDK.  On parse failure or API error it transparently
    activates the deterministic fallback ranker.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.groq_api_key
        self._model   = model   or settings.groq_model
        self._client  = None    # lazy-init to avoid import cost at startup

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank_and_explain(
        self,
        messages: list[dict[str, str]],
        candidates: list[Restaurant],
        preferences: UserPreferences,
        top_n: int,
    ) -> tuple[list[Recommendation], bool]:
        """
        Call Groq and return (recommendations, used_fallback).
        Falls back to deterministic ranking on any error or bad JSON.
        """
        raw: GroqRawResponse | None = None
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                raw = self._call_groq(messages)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = _BACKOFF_BASE ** attempt
                logger.warning(
                    "Groq call failed (attempt %d/%d): %s. Retrying in %.0fs…",
                    attempt, _MAX_RETRIES, exc, wait,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(wait)

        if raw is not None:
            recs = self._parse_and_merge(raw, candidates, top_n)
            if recs:
                logger.info("Groq returned %d valid recommendations.", len(recs))
                return recs, False
            logger.warning("Groq response parsed but yielded 0 valid recommendations; using fallback.")
        else:
            logger.warning("All Groq attempts failed (%s); using fallback.", last_error)

        return self._fallback_rank(candidates, preferences, top_n), True

    # ------------------------------------------------------------------
    # Groq API call
    # ------------------------------------------------------------------

    def _call_groq(self, messages: list[dict[str, str]]) -> GroqRawResponse:
        client = self._get_client()
        t0 = time.monotonic()
        response = client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.3,
            response_format={"type": "json_object"},
            timeout=_TIMEOUT,
        )
        elapsed = time.monotonic() - t0
        logger.info("Groq responded in %.2fs.", elapsed)

        content = response.choices[0].message.content or ""
        return self._parse_json(content)

    def _get_client(self):  # type: ignore[return]
        if self._client is None:
            from groq import Groq  # lazy import
            self._client = Groq(api_key=self._api_key)
        return self._client

    # ------------------------------------------------------------------
    # Response parsing & merge
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(content: str) -> GroqRawResponse:
        """Parse raw LLM text into GroqRawResponse, raise on failure."""
        content = content.strip()
        # Strip potential markdown fences
        if content.startswith("```"):
            content = "\n".join(content.splitlines()[1:])
            if content.endswith("```"):
                content = content[: content.rfind("```")]

        data: dict[str, Any] = json.loads(content)  # raises json.JSONDecodeError on bad JSON
        return GroqRawResponse(**data)

    def _parse_and_merge(
        self,
        raw: GroqRawResponse,
        candidates: list[Restaurant],
        top_n: int,
    ) -> list[Recommendation]:
        """
        Merge LLM rank+explanation with canonical fields from the candidate list.
        Reject any recommendation whose name does not match a candidate.
        """
        candidate_map: dict[str, Restaurant] = {r.name.lower(): r for r in candidates}
        results: list[Recommendation] = []

        for item in raw.recommendations:
            name_raw: str = str(item.get("restaurant_name", "")).strip()
            name_key = name_raw.lower()

            # Exact match first, then fuzzy fallback via substring
            restaurant = candidate_map.get(name_key)
            if restaurant is None:
                # Try substring match
                for key, r in candidate_map.items():
                    if name_key in key or key in name_key:
                        restaurant = r
                        break

            if restaurant is None:
                logger.warning(
                    "LLM returned unknown restaurant '%s' — skipping.", name_raw
                )
                continue

            explanation = str(item.get("explanation", "")).strip()
            if not explanation:
                explanation = self._template_explanation(restaurant)

            try:
                rank = int(item.get("rank", len(results) + 1))
            except (TypeError, ValueError):
                rank = len(results) + 1

            results.append(
                Recommendation(
                    rank=rank,
                    restaurant_name=restaurant.name,
                    cuisine=restaurant.cuisine_str,
                    rating=restaurant.rating,
                    estimated_cost=restaurant.cost_for_two,
                    location=restaurant.location,
                    explanation=explanation,
                )
            )

        # Deduplicate by name, sort by rank, cap at top_n
        seen: set[str] = set()
        deduped: list[Recommendation] = []
        for rec in sorted(results, key=lambda r: r.rank):
            if rec.restaurant_name not in seen:
                seen.add(rec.restaurant_name)
                deduped.append(rec)

        return deduped[:top_n]

    # ------------------------------------------------------------------
    # Fallback ranker (deterministic)
    # ------------------------------------------------------------------

    def _fallback_rank(
        self,
        candidates: list[Restaurant],
        preferences: UserPreferences,
        top_n: int,
    ) -> list[Recommendation]:
        """
        Score each candidate deterministically and return top_n recommendations
        with template explanations.

        Scoring weights (architecture §3.5):
          rating       × 0.5
          budget match × 0.3
          cuisine match× 0.2
          keyword overlap (soft)
        """
        logger.info("Fallback ranker activated for %d candidates.", len(candidates))

        cuisine_target = (preferences.cuisine or "").lower()
        keywords = []
        if preferences.additional_preferences:
            keywords = [w.lower() for w in preferences.additional_preferences.split()]

        scored: list[tuple[float, Restaurant]] = []
        for r in candidates:
            s = r.rating * 0.5
            s += 0.3 if r.budget_tier == preferences.budget else 0.0
            if cuisine_target:
                s += 0.2 if any(cuisine_target in c.lower() for c in r.cuisine) else 0.0
            if keywords:
                searchable = r.name.lower() + " " + r.cuisine_str.lower()
                matches = sum(1 for kw in keywords if kw in searchable)
                s += 0.05 * matches
            scored.append((s, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_n]

        return [
            Recommendation(
                rank=i + 1,
                restaurant_name=r.name,
                cuisine=r.cuisine_str,
                rating=r.rating,
                estimated_cost=r.cost_for_two,
                location=r.location,
                explanation=self._template_explanation(r, preferences),
            )
            for i, (_, r) in enumerate(top)
        ]

    @staticmethod
    def _template_explanation(
        r: Restaurant,
        prefs: UserPreferences | None = None,
    ) -> str:
        parts = [f"{r.name} is a {r.cuisine_str} restaurant in {r.location}"]
        parts.append(f"rated {r.rating:.1f}/5")
        if r.cost_for_two:
            parts.append(f"with an average cost of ₹{int(r.cost_for_two)} for two")
        if prefs:
            parts.append(f"matching your {prefs.budget} budget preference")
        return " ".join(parts) + "."
