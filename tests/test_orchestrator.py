"""Integration tests for RecommendationOrchestrator — Phase 4.

All tests mock the Groq SDK; no live API calls.
Tests exercise the full pipeline: preferences → filter → prompt → Groq → response.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.models.preferences import UserPreferences, PreferenceValidationError, ValidationSuggestion
from app.models.recommendation import Recommendation, RecommendationResponse
from app.models.restaurant import Restaurant
from app.services.filter_service import FilterService, FilterResult, FilterStageCount
from app.services.groq_service import GroqProvider
from app.services.orchestrator import RecommendationOrchestrator
from app.services.prompt_builder import PromptBuilder


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_restaurant(
    name: str,
    location: str = "Indiranagar",
    cuisine: str = "North Indian",
    rating: float = 4.2,
    cost: float = 600.0,
    budget: str = "medium",
    tags: list[str] | None = None,
) -> Restaurant:
    return Restaurant(
        id=name.lower().replace(" ", "_"),
        name=name,
        location=location,
        city="Bangalore",
        cuisine=cuisine,
        rating=rating,
        cost_for_two=cost,
        budget_tier=budget,
        address="",
        tags=tags or ["popular"],
    )


def _make_candidates(n: int = 10) -> list[Restaurant]:
    """Generate a list of plausible restaurant candidates."""
    restaurants = [
        _make_restaurant("Punjabi Tadka", rating=4.5, cost=500, budget="medium"),
        _make_restaurant("Spice Garden", rating=4.2, cost=700, budget="medium"),
        _make_restaurant("Dragon Palace", cuisine="Chinese", rating=3.8, cost=800, budget="high"),
        _make_restaurant("Biryani Blues", cuisine="Hyderabadi", rating=4.0, cost=400, budget="low"),
        _make_restaurant("Pasta Corner", cuisine="Italian", rating=4.3, cost=900, budget="high"),
        _make_restaurant("Tandoori Nights", rating=4.1, cost=550, budget="medium"),
        _make_restaurant("Dosa Plaza", cuisine="South Indian", rating=3.9, cost=300, budget="low"),
        _make_restaurant("Sushi Express", cuisine="Japanese", rating=4.4, cost=1200, budget="high"),
        _make_restaurant("Curry Leaf", rating=4.0, cost=600, budget="medium"),
        _make_restaurant("Kebab Factory", rating=4.3, cost=650, budget="medium"),
    ]
    return restaurants[:n]


def _valid_groq_json(candidates: list[Restaurant], top_n: int = 5) -> str:
    """Build a valid JSON response matching what the LLM should return."""
    recs = []
    for i, r in enumerate(candidates[:top_n], start=1):
        recs.append({
            "rank": i,
            "restaurant_name": r.name,
            "explanation": f"Great choice in {r.location} matching your preferences for {r.cuisine_str}.",
        })
    return json.dumps({"recommendations": recs, "summary": "Here are your top picks."})


def _mock_groq_response(content: str) -> MagicMock:
    """Build a mock Groq chat completion response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def restaurants() -> list[Restaurant]:
    return _make_candidates(10)


@pytest.fixture
def repository(restaurants) -> MagicMock:
    """Mock RestaurantRepository that returns our test restaurants."""
    repo = MagicMock()
    repo.get_all.return_value = list(restaurants)
    repo.get_locations.return_value = sorted({r.location for r in restaurants})
    repo.get_cuisines.return_value = sorted({c for r in restaurants for c in r.cuisine})
    repo.is_loaded = True
    return repo


@pytest.fixture
def filter_service(restaurants) -> FilterService:
    return FilterService(restaurants, top_k=25)


@pytest.fixture
def prompt_builder() -> PromptBuilder:
    return PromptBuilder()


@pytest.fixture
def groq_provider() -> GroqProvider:
    return GroqProvider(api_key="test-key", model="test-model")


@pytest.fixture
def orchestrator(repository, filter_service, prompt_builder, groq_provider) -> RecommendationOrchestrator:
    return RecommendationOrchestrator(
        repository=repository,
        filter_service=filter_service,
        prompt_builder=prompt_builder,
        groq_provider=groq_provider,
        top_n=5,
    )


@pytest.fixture
def valid_prefs() -> UserPreferences:
    return UserPreferences(
        location="Indiranagar",
        budget="medium",
        cuisine="North Indian",
        min_rating=3.5,
        additional_preferences="outdoor seating",
    )


@pytest.fixture
def any_cuisine_prefs() -> UserPreferences:
    return UserPreferences(
        location="Indiranagar",
        budget="medium",
        min_rating=0.0,
    )


# ---------------------------------------------------------------------------
# Test: Full pipeline with mocked Groq (happy path)
# ---------------------------------------------------------------------------

class TestHappyPath:
    """End-to-end tests where Groq returns valid recommendations."""

    def test_returns_recommendation_response(self, orchestrator, valid_prefs, restaurants):
        # Filter will produce medium-budget candidates in Indiranagar
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium" and r.rating >= 3.5]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(valid_prefs)

        assert isinstance(result, RecommendationResponse)
        assert not result.is_empty

    def test_response_has_recommendations(self, orchestrator, valid_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium" and r.rating >= 3.5]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(valid_prefs)

        assert len(result.recommendations) > 0
        for rec in result.recommendations:
            assert isinstance(rec, Recommendation)
            assert rec.restaurant_name
            assert rec.explanation
            assert rec.rating >= 0
            assert rec.estimated_cost >= 0
            assert rec.location

    def test_response_includes_metadata(self, orchestrator, valid_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium" and r.rating >= 3.5]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(valid_prefs)

        assert result.total_candidates_considered > 0
        assert "location" in result.filters_applied
        assert "budget" in result.filters_applied
        assert result.filters_applied["location"] == "Indiranagar"
        assert result.filters_applied["budget"] == "medium"

    def test_response_has_summary(self, orchestrator, valid_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium" and r.rating >= 3.5]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(valid_prefs)

        assert result.summary
        assert "Indiranagar" in result.summary

    def test_used_fallback_is_false_on_success(self, orchestrator, valid_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium" and r.rating >= 3.5]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(valid_prefs)

        assert result.used_fallback is False

    def test_no_cuisine_filter_returns_more_candidates(self, orchestrator, any_cuisine_prefs, restaurants):
        """When no cuisine is specified, more candidates pass through."""
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium"]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(any_cuisine_prefs)

        assert not result.is_empty
        assert result.total_candidates_considered > 0


# ---------------------------------------------------------------------------
# Test: Zero-candidate path
# ---------------------------------------------------------------------------

class TestZeroCandidates:
    """Tests for when filters produce zero results."""

    def test_impossible_filters_return_empty_response(self, orchestrator):
        """No restaurants match an impossible combination."""
        prefs = UserPreferences(
            location="Indiranagar",
            budget="high",  # few high-budget restaurants in our fixture
            cuisine="North Indian",  # combined with high budget = zero
            min_rating=4.9,  # almost nothing passes this
        )
        result = orchestrator.recommend(prefs)

        assert result.is_empty
        assert len(result.recommendations) == 0
        assert result.empty_reason  # should have a reason message

    def test_empty_response_has_no_exception(self, orchestrator):
        """Ensure zero results returns structured response, not an exception."""
        prefs = UserPreferences(
            location="Indiranagar",
            budget="high",
            min_rating=5.0,  # nobody has 5.0
        )
        # This should NOT raise — orchestrator never raises
        result = orchestrator.recommend(prefs)
        assert isinstance(result, RecommendationResponse)

    def test_empty_response_contains_filter_metadata(self, orchestrator):
        prefs = UserPreferences(
            location="Indiranagar",
            budget="high",
            min_rating=5.0,
        )
        result = orchestrator.recommend(prefs)

        assert "location" in result.filters_applied
        assert result.filters_applied["budget"] == "high"

    def test_empty_response_has_zero_candidates(self, orchestrator):
        prefs = UserPreferences(
            location="Indiranagar",
            budget="high",
            min_rating=5.0,
        )
        result = orchestrator.recommend(prefs)
        assert result.total_candidates_considered == 0


# ---------------------------------------------------------------------------
# Test: Fallback path (Groq failure)
# ---------------------------------------------------------------------------

class TestFallbackPath:
    """Tests for when Groq fails and the deterministic fallback ranker activates."""

    def test_groq_exception_returns_fallback(self, orchestrator, any_cuisine_prefs):
        """Groq raising an exception should trigger fallback, not crash."""
        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API down")
            with patch("app.services.groq_service.time.sleep"):  # skip backoff wait
                result = orchestrator.recommend(any_cuisine_prefs)

        assert isinstance(result, RecommendationResponse)
        assert result.used_fallback is True
        assert len(result.recommendations) > 0

    def test_fallback_recommendations_have_explanations(self, orchestrator, any_cuisine_prefs):
        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API down")
            with patch("app.services.groq_service.time.sleep"):
                result = orchestrator.recommend(any_cuisine_prefs)

        for rec in result.recommendations:
            assert rec.explanation
            assert len(rec.explanation) > 10

    def test_fallback_summary_mentions_unavailable(self, orchestrator, any_cuisine_prefs):
        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API down")
            with patch("app.services.groq_service.time.sleep"):
                result = orchestrator.recommend(any_cuisine_prefs)

        assert "unavailable" in result.summary.lower()

    def test_malformed_json_triggers_fallback(self, orchestrator, any_cuisine_prefs):
        """Groq returns garbage text → fallback activates."""
        mock_response = _mock_groq_response("not valid json {{{")

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(any_cuisine_prefs)

        assert result.used_fallback is True
        assert len(result.recommendations) > 0

    def test_fallback_still_respects_top_n(self, orchestrator, any_cuisine_prefs):
        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = RuntimeError("fail")
            with patch("app.services.groq_service.time.sleep"):
                result = orchestrator.recommend(any_cuisine_prefs)

        assert len(result.recommendations) <= orchestrator._top_n


# ---------------------------------------------------------------------------
# Test: Preference validation failure
# ---------------------------------------------------------------------------

class TestPreferenceValidation:
    """Tests for when user provides an unresolvable location or cuisine."""

    def test_unknown_location_returns_empty_with_reason(self, restaurants):
        """A location not in the vocabulary should return an empty response with suggestions."""
        # Build orchestrator with a filter that has the real vocabulary
        repo = MagicMock()
        repo.get_all.return_value = list(restaurants)

        filter_svc = FilterService(restaurants, top_k=25)
        orchestrator = RecommendationOrchestrator(
            repository=repo,
            filter_service=filter_svc,
            top_n=5,
        )

        prefs = UserPreferences(
            location="Atlantis",  # does not exist
            budget="medium",
        )
        result = orchestrator.recommend(prefs)

        assert result.is_empty
        assert "validate" in result.empty_reason.lower() or "recognised" in result.empty_reason.lower()


# ---------------------------------------------------------------------------
# Test: Response format / output formatting
# ---------------------------------------------------------------------------

class TestOutputFormatting:
    """Verify that the response is correctly formatted."""

    def test_cost_display_is_human_readable(self, orchestrator, any_cuisine_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium"]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(any_cuisine_prefs)

        for rec in result.recommendations:
            # cost_display is a property on Recommendation model
            assert "₹" in rec.cost_display or rec.cost_display == "N/A"

    def test_filters_applied_has_stages_on_success(self, orchestrator, any_cuisine_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium"]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(any_cuisine_prefs)

        assert "stages" in result.filters_applied
        stages = result.filters_applied["stages"]
        assert isinstance(stages, list)
        assert len(stages) > 0
        assert "stage" in stages[0]
        assert "before" in stages[0]
        assert "after" in stages[0]

    def test_cuisine_in_summary_when_specified(self, orchestrator, valid_prefs, restaurants):
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium" and r.rating >= 3.5]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(valid_prefs)

        if not result.is_empty and not result.used_fallback:
            assert "North Indian" in result.summary


# ---------------------------------------------------------------------------
# Test: Vocabulary accessors (for UI dropdowns)
# ---------------------------------------------------------------------------

class TestVocabularyAccessors:
    def test_locations_returns_list(self, orchestrator):
        locs = orchestrator.locations
        assert isinstance(locs, list)
        assert len(locs) > 0

    def test_cuisines_returns_list(self, orchestrator):
        cuisines = orchestrator.cuisines
        assert isinstance(cuisines, list)
        assert len(cuisines) > 0

    def test_locations_are_sorted(self, orchestrator):
        locs = orchestrator.locations
        assert locs == sorted(locs)

    def test_cuisines_are_sorted(self, orchestrator):
        cuisines = orchestrator.cuisines
        assert cuisines == sorted(cuisines)


# ---------------------------------------------------------------------------
# Test: Pipeline never crashes
# ---------------------------------------------------------------------------

class TestRobustness:
    """Ensure the orchestrator never raises — always returns a structured response."""

    def test_no_crash_with_minimal_prefs(self, orchestrator):
        prefs = UserPreferences(location="Indiranagar", budget="low")

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = RuntimeError("fail")
            with patch("app.services.groq_service.time.sleep"):
                result = orchestrator.recommend(prefs)

        assert isinstance(result, RecommendationResponse)

    def test_no_crash_with_high_min_rating(self, orchestrator):
        prefs = UserPreferences(location="Indiranagar", budget="medium", min_rating=5.0)
        result = orchestrator.recommend(prefs)
        assert isinstance(result, RecommendationResponse)

    def test_no_crash_with_long_additional_prefs(self, orchestrator, restaurants):
        prefs = UserPreferences(
            location="Indiranagar",
            budget="medium",
            additional_preferences="a " * 250,  # 500 chars
        )
        medium_candidates = [r for r in restaurants if r.budget_tier == "medium"]
        valid_json = _valid_groq_json(medium_candidates, top_n=5)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(orchestrator._groq_provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = orchestrator.recommend(prefs)

        assert isinstance(result, RecommendationResponse)
