"""RecommendationOrchestrator — end-to-end pipeline from preferences to response."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.data.repository import RestaurantRepository
from app.models.preferences import PreferenceValidationError, UserPreferences
from app.models.recommendation import RecommendationResponse
from app.services.filter_service import FilterResult, FilterService
from app.services.groq_service import GroqProvider
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class RecommendationOrchestrator:
    """
    Coordinates the full recommendation pipeline:

      1. Validate ``UserPreferences`` (fuzzy-match location/cuisine)
      2. Apply deterministic filters → candidate list
      3. If zero candidates → return empty ``RecommendationResponse`` with suggestions
      4. Build LLM prompt via ``PromptBuilder``
      5. Call ``GroqProvider.rank_and_explain``
      6. Merge and format into ``RecommendationResponse``

    All service dependencies are injected for testability.
    """

    def __init__(
        self,
        repository: RestaurantRepository,
        filter_service: FilterService | None = None,
        prompt_builder: PromptBuilder | None = None,
        groq_provider: GroqProvider | None = None,
        top_n: int | None = None,
    ) -> None:
        self._repository = repository
        self._filter_service = filter_service or FilterService(repository.get_all())
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._groq_provider = groq_provider or GroqProvider()
        self._top_n = top_n if top_n is not None else settings.top_n_recommendations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self, preferences: UserPreferences) -> RecommendationResponse:
        """Run the full pipeline; never raises — returns structured response."""
        pipeline_start = time.monotonic()

        # --- Step 1: Validate preferences ---
        try:
            validated = self._filter_service.validate_preferences(preferences)
            logger.info(
                "Preferences validated — location=%s, cuisine=%s, budget=%s",
                validated.location,
                validated.cuisine,
                validated.budget,
            )
        except PreferenceValidationError as exc:
            logger.warning("Preference validation failed: %s", exc)
            suggestions_text = "; ".join(s.message for s in exc.suggestions)
            return RecommendationResponse(
                empty_reason=f"Could not validate your preferences: {suggestions_text}",
                filters_applied=self._snapshot_filters(preferences),
            )

        # --- Step 2: Apply filters ---
        filter_result: FilterResult = self._filter_service.filter(validated)
        logger.info(
            "Filter pipeline complete — %d candidates (stages: %s)",
            len(filter_result.candidates),
            ", ".join(
                f"{s.stage}:{s.count_before}→{s.count_after}"
                for s in filter_result.stage_counts
            ),
        )

        # --- Step 3: Zero candidates → early return ---
        if filter_result.is_empty:
            logger.info("Zero candidates after filtering.")
            return RecommendationResponse(
                empty_reason=filter_result.empty_reason
                or (
                    "No restaurants match your filters. "
                    "Try a different location, lower the minimum rating, "
                    "or change the budget tier."
                ),
                total_candidates_considered=0,
                filters_applied=self._snapshot_filters(validated, filter_result),
            )

        # --- Step 4: Build prompt ---
        messages = self._prompt_builder.build(
            validated, filter_result.candidates, self._top_n
        )

        # --- Step 5: Call Groq (with fallback) ---
        groq_start = time.monotonic()
        recommendations, used_fallback = self._groq_provider.rank_and_explain(
            messages=messages,
            candidates=filter_result.candidates,
            preferences=validated,
            top_n=self._top_n,
        )
        groq_elapsed = time.monotonic() - groq_start
        logger.info(
            "Groq step complete in %.2fs — %d recommendations (fallback=%s)",
            groq_elapsed,
            len(recommendations),
            used_fallback,
        )

        # --- Step 6: Format and return ---
        # Format estimated_cost as human-readable string in cost_display property
        # (already on the Recommendation model). Build summary.
        summary = ""
        if not used_fallback:
            # Try to extract an LLM-generated summary from the raw response
            # The GroqProvider doesn't expose it directly, so we generate one
            summary = (
                f"Found {len(recommendations)} great picks in "
                f"{validated.location} for a {validated.budget} budget"
            )
            if validated.cuisine:
                summary += f" — {validated.cuisine} cuisine"
            summary += "."
        else:
            summary = (
                "AI-powered ranking was unavailable; showing top-rated restaurants "
                "based on your filters."
            )

        pipeline_elapsed = time.monotonic() - pipeline_start
        logger.info("Pipeline finished in %.2fs.", pipeline_elapsed)

        return RecommendationResponse(
            recommendations=recommendations,
            summary=summary,
            total_candidates_considered=len(filter_result.candidates),
            filters_applied=self._snapshot_filters(validated, filter_result),
            used_fallback=used_fallback,
        )

    # ------------------------------------------------------------------
    # Vocabulary accessors (for UI dropdowns)
    # ------------------------------------------------------------------

    @property
    def locations(self) -> list[str]:
        """Sorted, unique location list from the repository."""
        return self._filter_service.locations

    @property
    def cuisines(self) -> list[str]:
        """Sorted, unique cuisine list from the repository."""
        return self._filter_service.cuisines

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot_filters(
        prefs: UserPreferences,
        filter_result: FilterResult | None = None,
    ) -> dict[str, Any]:
        """Create a serialisable snapshot of applied filters."""
        snap: dict[str, Any] = {
            "location": prefs.location,
            "budget": prefs.budget,
            "cuisine": prefs.cuisine,
            "min_rating": prefs.min_rating,
            "additional_preferences": prefs.additional_preferences,
        }
        if filter_result is not None:
            snap["stages"] = [
                {
                    "stage": s.stage,
                    "before": s.count_before,
                    "after": s.count_after,
                }
                for s in filter_result.stage_counts
            ]
        return snap
