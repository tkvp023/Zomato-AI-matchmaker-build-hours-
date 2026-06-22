"""FilterService — validates preferences and filters restaurants to TOP_K candidates."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from app.config import settings
from app.models.preferences import (
    PreferenceValidationError,
    UserPreferences,
    ValidationSuggestion,
)
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 80       # minimum score (0–100) for a fuzzy match to count
_FUZZY_SUGGESTIONS = 3      # how many close matches to show on failure
_KEYWORD_BOOST_WEIGHT = 0.1 # small nudge for additional_preferences keyword matches


@dataclass
class FilterStageCount:
    stage: str
    count_before: int
    count_after: int

    @property
    def dropped(self) -> int:
        return self.count_before - self.count_after


@dataclass
class FilterResult:
    """Output of FilterService.filter()."""
    candidates: list[Restaurant]
    stage_counts: list[FilterStageCount] = field(default_factory=list)
    resolved_location: str = ""
    resolved_cuisine: str | None = None
    empty_reason: str = ""

    @property
    def is_empty(self) -> bool:
        return len(self.candidates) == 0


class FilterService:
    """
    Validates UserPreferences against known vocabulary, then applies a
    deterministic multi-stage filter pipeline to produce TOP_K candidates.
    """

    def __init__(
        self,
        restaurants: list[Restaurant],
        top_k: int | None = None,
    ) -> None:
        self._restaurants = restaurants
        self._top_k = top_k if top_k is not None else settings.top_k_candidates
        self._locations: list[str] = sorted({r.location for r in restaurants if r.location})
        self._cuisines: list[str] = sorted(
            {c for r in restaurants for c in r.cuisine if c}
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_preferences(self, prefs: UserPreferences) -> UserPreferences:
        """
        Fuzzy-match location and cuisine against known vocabulary.
        Returns a new UserPreferences with resolved values, or raises
        PreferenceValidationError with suggestions.
        """
        errors: list[ValidationSuggestion] = []
        resolved_location = self._resolve_field(
            prefs.location, self._locations, "location", errors
        )
        resolved_cuisine = None
        if prefs.cuisine:
            resolved_cuisine = self._resolve_field(
                prefs.cuisine, self._cuisines, "cuisine", errors, required=False
            )

        if errors:
            raise PreferenceValidationError(errors)

        return prefs.model_copy(
            update={
                "location": resolved_location or prefs.location,
                "cuisine": resolved_cuisine,
            }
        )

    def filter(self, prefs: UserPreferences) -> FilterResult:
        """
        Run the full filter pipeline and return a FilterResult.

        Pipeline order (matches architecture §7.2):
          1. Location (fuzzy + substring)
          2. Rating  (>= min_rating)
          3. Cuisine (token match, skipped if None)
          4. Budget  (exact tier match)
          5. Keyword boost from additional_preferences (soft — re-sorts, no hard exclude)
          6. Cap at TOP_K (pre-sorted by rating desc)
        """
        pool = list(self._restaurants)
        stages: list[FilterStageCount] = []

        # --- Stage 1: Location ---
        before = len(pool)
        pool = self._filter_location(pool, prefs.location)
        stages.append(FilterStageCount("location", before, len(pool)))
        logger.debug("After location filter: %d", len(pool))

        if not pool:
            return FilterResult(
                candidates=[],
                stage_counts=stages,
                resolved_location=prefs.location,
                resolved_cuisine=prefs.cuisine,
                empty_reason=(
                    f"No restaurants found in '{prefs.location}'. "
                    "Try a nearby area or check the spelling."
                ),
            )

        # --- Stage 2: Rating ---
        before = len(pool)
        pool = [r for r in pool if r.rating >= prefs.min_rating]
        stages.append(FilterStageCount("min_rating", before, len(pool)))
        logger.debug("After rating filter (>=%.1f): %d", prefs.min_rating, len(pool))

        # --- Stage 3: Cuisine ---
        if prefs.cuisine:
            before = len(pool)
            pool = self._filter_cuisine(pool, prefs.cuisine)
            stages.append(FilterStageCount("cuisine", before, len(pool)))
            logger.debug("After cuisine filter ('%s'): %d", prefs.cuisine, len(pool))

        # --- Stage 4: Budget ---
        before = len(pool)
        pool = [r for r in pool if r.budget_tier == prefs.budget]
        stages.append(FilterStageCount("budget", before, len(pool)))
        logger.debug("After budget filter ('%s'): %d", prefs.budget, len(pool))

        if not pool:
            return FilterResult(
                candidates=[],
                stage_counts=stages,
                resolved_location=prefs.location,
                resolved_cuisine=prefs.cuisine,
                empty_reason=(
                    f"No '{prefs.budget}' budget restaurants match your filters. "
                    "Try a different budget or lower the minimum rating."
                ),
            )

        # --- Stage 5: Sort by rating desc (+ keyword boost) ---
        pool = self._sort_with_boost(pool, prefs.additional_preferences)

        # --- Stage 6: Cap at TOP_K ---
        before = len(pool)
        pool = pool[: self._top_k]
        stages.append(FilterStageCount("top_k_cap", before, len(pool)))

        return FilterResult(
            candidates=pool,
            stage_counts=stages,
            resolved_location=prefs.location,
            resolved_cuisine=prefs.cuisine,
        )

    # ------------------------------------------------------------------
    # Vocabulary accessors (for UI dropdowns)
    # ------------------------------------------------------------------

    @property
    def locations(self) -> list[str]:
        return list(self._locations)

    @property
    def cuisines(self) -> list[str]:
        return list(self._cuisines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_field(
        value: str,
        vocabulary: list[str],
        field_name: str,
        errors: list[ValidationSuggestion],
        *,
        required: bool = True,
    ) -> str | None:
        """Exact match → substring match → fuzzy match. Returns resolved value or None."""
        if not vocabulary:
            return value  # can't validate without vocab

        # 1. Exact case-insensitive match
        val_lower = value.lower()
        for v in vocabulary:
            if v.lower() == val_lower:
                return v

        # 2. Substring match
        matches = [v for v in vocabulary if val_lower in v.lower() or v.lower() in val_lower]
        if matches:
            return matches[0]

        # 3. Fuzzy match
        results = process.extract(
            value, vocabulary, scorer=fuzz.WRatio, limit=_FUZZY_SUGGESTIONS
        )
        best_score = results[0][1] if results else 0

        if best_score >= _FUZZY_THRESHOLD:
            return results[0][0]

        if required:
            suggestions = [r[0] for r in results]
            errors.append(
                ValidationSuggestion(
                    field=field_name,
                    provided=value,
                    suggestions=suggestions,
                    message=(
                        f"'{value}' is not a recognised {field_name}. "
                        f"Did you mean: {', '.join(suggestions)}?"
                    ),
                )
            )
        return None

    @staticmethod
    def _filter_location(pool: list[Restaurant], location: str) -> list[Restaurant]:
        """Case-insensitive substring match on location field."""
        loc_lower = location.lower()
        return [
            r for r in pool
            if loc_lower in r.location.lower() or r.location.lower() in loc_lower
        ]

    @staticmethod
    def _filter_cuisine(pool: list[Restaurant], cuisine: str) -> list[Restaurant]:
        """Token-level match: any cuisine token in restaurant's cuisine list."""
        target = cuisine.lower()
        return [
            r for r in pool
            if any(target in c.lower() or c.lower() in target for c in r.cuisine)
        ]

    @staticmethod
    def _sort_with_boost(
        pool: list[Restaurant], additional: str | None
    ) -> list[Restaurant]:
        """
        Sort by rating desc, with a small boost for keyword matches from
        additional_preferences (soft re-rank, never hard excludes).
        """
        if not additional:
            return sorted(pool, key=lambda r: r.rating, reverse=True)

        keywords = [kw.strip().lower() for kw in additional.split() if kw.strip()]

        def score(r: Restaurant) -> float:
            searchable = (
                r.name.lower()
                + " "
                + r.cuisine_str.lower()
                + " "
                + " ".join(t.lower() for t in r.tags)
            )
            matches = sum(1 for kw in keywords if kw in searchable)
            boost = _KEYWORD_BOOST_WEIGHT * matches
            return r.rating + boost

        return sorted(pool, key=score, reverse=True)
