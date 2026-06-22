"""Unit tests for GroqProvider — Phase 3.

All tests mock the Groq SDK; no live API calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.preferences import UserPreferences
from app.models.recommendation import GroqRawResponse, Recommendation
from app.models.restaurant import Restaurant
from app.services.groq_service import GroqProvider, GroqServiceError


# ---------------------------------------------------------------------------
# Shared fixtures
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


@pytest.fixture
def candidates() -> list[Restaurant]:
    return [
        _make_restaurant("Punjabi Tadka", rating=4.5, cost=500, budget="medium"),
        _make_restaurant("Spice Garden", rating=4.2, cost=700, budget="medium"),
        _make_restaurant("Dragon Palace", cuisine="Chinese", rating=3.8, cost=800, budget="high"),
        _make_restaurant("Biryani Blues", cuisine="Hyderabadi", rating=4.0, cost=400, budget="low"),
        _make_restaurant("Pasta Corner", cuisine="Italian", rating=4.3, cost=900, budget="high"),
    ]


@pytest.fixture
def prefs() -> UserPreferences:
    return UserPreferences(
        location="Indiranagar",
        budget="medium",
        cuisine="North Indian",
        min_rating=3.5,
        additional_preferences="outdoor seating",
    )


@pytest.fixture
def provider() -> GroqProvider:
    return GroqProvider(api_key="test-key", model="test-model")


def _valid_groq_json(candidates: list[Restaurant], top_n: int = 3) -> str:
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
# JSON parsing tests
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_valid_json_parses(self, provider):
        raw = provider._parse_json('{"recommendations": [{"rank": 1, "restaurant_name": "A", "explanation": "Good"}], "summary": "ok"}')
        assert isinstance(raw, GroqRawResponse)
        assert len(raw.recommendations) == 1
        assert raw.summary == "ok"

    def test_empty_recommendations_returns_empty_list(self, provider):
        raw = provider._parse_json('{"recommendations": []}')
        assert raw.recommendations == []

    def test_strips_markdown_fences(self, provider):
        content = '```json\n{"recommendations": [], "summary": "test"}\n```'
        raw = provider._parse_json(content)
        assert isinstance(raw, GroqRawResponse)
        assert raw.summary == "test"

    def test_invalid_json_raises(self, provider):
        with pytest.raises(json.JSONDecodeError):
            provider._parse_json("this is not json at all")

    def test_recommendations_not_list_coerced_to_empty(self, provider):
        raw = provider._parse_json('{"recommendations": "invalid"}')
        assert raw.recommendations == []


# ---------------------------------------------------------------------------
# Parse-and-merge tests
# ---------------------------------------------------------------------------

class TestParseAndMerge:
    def test_merges_with_canonical_fields(self, provider, candidates):
        raw = GroqRawResponse(
            recommendations=[
                {"rank": 1, "restaurant_name": "Punjabi Tadka", "explanation": "Excellent North Indian food."},
            ],
            summary="Top pick.",
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=3)
        assert len(recs) == 1
        rec = recs[0]
        assert rec.restaurant_name == "Punjabi Tadka"
        assert rec.rating == 4.5  # canonical value, not from LLM
        assert rec.estimated_cost == 500.0
        assert rec.location == "Indiranagar"
        assert rec.cuisine == "North Indian"
        assert rec.explanation == "Excellent North Indian food."

    def test_rejects_unknown_restaurant(self, provider, candidates):
        raw = GroqRawResponse(
            recommendations=[
                {"rank": 1, "restaurant_name": "Unknown Place", "explanation": "Not in list."},
                {"rank": 2, "restaurant_name": "Punjabi Tadka", "explanation": "Good food."},
            ],
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=3)
        # Only the known restaurant should survive
        assert len(recs) == 1
        assert recs[0].restaurant_name == "Punjabi Tadka"

    def test_substring_match_works(self, provider, candidates):
        """LLM might return a slightly different name; substring matching should handle it."""
        raw = GroqRawResponse(
            recommendations=[
                {"rank": 1, "restaurant_name": "Punjabi Tadka Restaurant", "explanation": "Great."},
            ],
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=3)
        assert len(recs) == 1
        assert recs[0].restaurant_name == "Punjabi Tadka"

    def test_respects_top_n_cap(self, provider, candidates):
        raw = GroqRawResponse(
            recommendations=[
                {"rank": i, "restaurant_name": r.name, "explanation": f"Rank {i} pick."}
                for i, r in enumerate(candidates, start=1)
            ],
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=2)
        assert len(recs) == 2

    def test_deduplicates_by_name(self, provider, candidates):
        raw = GroqRawResponse(
            recommendations=[
                {"rank": 1, "restaurant_name": "Punjabi Tadka", "explanation": "First mention."},
                {"rank": 2, "restaurant_name": "Punjabi Tadka", "explanation": "Duplicate."},
                {"rank": 3, "restaurant_name": "Spice Garden", "explanation": "Another pick."},
            ],
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=5)
        names = [r.restaurant_name for r in recs]
        assert names.count("Punjabi Tadka") == 1

    def test_assigns_rank_when_missing(self, provider, candidates):
        raw = GroqRawResponse(
            recommendations=[
                {"restaurant_name": "Punjabi Tadka", "explanation": "Good food."},
            ],
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=3)
        assert recs[0].rank >= 1

    def test_empty_explanation_uses_template(self, provider, candidates):
        raw = GroqRawResponse(
            recommendations=[
                {"rank": 1, "restaurant_name": "Punjabi Tadka", "explanation": ""},
            ],
        )
        recs = provider._parse_and_merge(raw, candidates, top_n=3)
        assert len(recs[0].explanation) > 10  # template generates a reasonable explanation


# ---------------------------------------------------------------------------
# Fallback ranker tests
# ---------------------------------------------------------------------------

class TestFallbackRanker:
    def test_returns_top_n_results(self, provider, candidates, prefs):
        recs = provider._fallback_rank(candidates, prefs, top_n=3)
        assert len(recs) == 3

    def test_ranks_are_sequential(self, provider, candidates, prefs):
        recs = provider._fallback_rank(candidates, prefs, top_n=3)
        ranks = [r.rank for r in recs]
        assert ranks == [1, 2, 3]

    def test_all_fields_populated(self, provider, candidates, prefs):
        recs = provider._fallback_rank(candidates, prefs, top_n=2)
        for rec in recs:
            assert rec.restaurant_name
            assert rec.explanation
            assert rec.location

    def test_budget_match_boosts_score(self, provider, prefs):
        """Restaurants matching user's budget (medium) should rank higher than non-matching."""
        cands = [
            _make_restaurant("High Budget", rating=4.0, budget="high"),
            _make_restaurant("Medium Budget", rating=4.0, budget="medium"),
        ]
        recs = provider._fallback_rank(cands, prefs, top_n=2)
        # Medium budget should rank first because it matches the preference
        assert recs[0].restaurant_name == "Medium Budget"

    def test_cuisine_match_boosts_score(self, provider, prefs):
        """Restaurants matching user's cuisine preference should rank higher."""
        cands = [
            _make_restaurant("Italian Place", cuisine="Italian", rating=4.0, budget="medium"),
            _make_restaurant("North Indian Place", cuisine="North Indian", rating=4.0, budget="medium"),
        ]
        recs = provider._fallback_rank(cands, prefs, top_n=2)
        # North Indian should rank first because it matches
        assert recs[0].restaurant_name == "North Indian Place"

    def test_rating_has_highest_weight(self, provider, prefs):
        """Higher-rated restaurant should still beat budget+cuisine match if rating gap is large."""
        cands = [
            _make_restaurant("Low Rated Match", cuisine="North Indian", rating=2.0, budget="medium"),
            _make_restaurant("High Rated NoMatch", cuisine="Italian", rating=5.0, budget="high"),
        ]
        recs = provider._fallback_rank(cands, prefs, top_n=2)
        # 5.0 * 0.5 = 2.5 vs 2.0 * 0.5 + 0.3 + 0.2 = 1.5
        assert recs[0].restaurant_name == "High Rated NoMatch"

    def test_keyword_overlap_adds_boost(self, provider):
        prefs = UserPreferences(
            location="Indiranagar",
            budget="medium",
            additional_preferences="biryani",
        )
        cands = [
            _make_restaurant("Plain Place", cuisine="North Indian", rating=4.0, budget="medium"),
            _make_restaurant("Biryani House", cuisine="Hyderabadi Biryani", rating=4.0, budget="medium"),
        ]
        recs = provider._fallback_rank(cands, prefs, top_n=2)
        # "biryani" keyword overlaps with "Biryani House" name + cuisine
        assert recs[0].restaurant_name == "Biryani House"

    def test_handles_no_additional_preferences(self, provider, candidates):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        recs = provider._fallback_rank(candidates, prefs, top_n=3)
        assert len(recs) == 3

    def test_handles_empty_candidates(self, provider, prefs):
        recs = provider._fallback_rank([], prefs, top_n=3)
        assert recs == []

    def test_top_n_larger_than_candidates(self, provider, prefs):
        cands = [_make_restaurant("Solo")]
        recs = provider._fallback_rank(cands, prefs, top_n=5)
        assert len(recs) == 1


# ---------------------------------------------------------------------------
# Template explanation tests
# ---------------------------------------------------------------------------

class TestTemplateExplanation:
    def test_includes_restaurant_name(self, provider):
        r = _make_restaurant("Test Place")
        explanation = provider._template_explanation(r)
        assert "Test Place" in explanation

    def test_includes_rating(self, provider):
        r = _make_restaurant("Test Place", rating=4.5)
        explanation = provider._template_explanation(r)
        assert "4.5" in explanation

    def test_includes_cost(self, provider):
        r = _make_restaurant("Test Place", cost=800)
        explanation = provider._template_explanation(r)
        assert "800" in explanation

    def test_includes_budget_pref_when_given(self, provider):
        r = _make_restaurant("Test Place")
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        explanation = provider._template_explanation(r, prefs)
        assert "medium" in explanation

    def test_no_prefs_still_works(self, provider):
        r = _make_restaurant("Test Place")
        explanation = provider._template_explanation(r)
        assert len(explanation) > 10


# ---------------------------------------------------------------------------
# rank_and_explain (integration with mocked Groq)
# ---------------------------------------------------------------------------

class TestRankAndExplain:
    def test_valid_groq_response_returns_recommendations(self, provider, candidates, prefs):
        valid_json = _valid_groq_json(candidates, top_n=3)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            recs, used_fallback = provider.rank_and_explain(
                messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                candidates=candidates,
                preferences=prefs,
                top_n=3,
            )

        assert not used_fallback
        assert len(recs) == 3
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_malformed_json_triggers_fallback(self, provider, candidates, prefs):
        mock_response = _mock_groq_response("this is not json {{{ bad")

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            recs, used_fallback = provider.rank_and_explain(
                messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                candidates=candidates,
                preferences=prefs,
                top_n=3,
            )

        assert used_fallback
        assert len(recs) == 3  # fallback still produces results

    def test_api_exception_triggers_fallback(self, provider, candidates, prefs):
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = RuntimeError("Connection failed")
            recs, used_fallback = provider.rank_and_explain(
                messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                candidates=candidates,
                preferences=prefs,
                top_n=3,
            )

        assert used_fallback
        assert len(recs) == 3

    def test_empty_llm_recommendations_triggers_fallback(self, provider, candidates, prefs):
        """LLM returns valid JSON but with no recommendations → fallback."""
        mock_response = _mock_groq_response('{"recommendations": []}')

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            recs, used_fallback = provider.rank_and_explain(
                messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                candidates=candidates,
                preferences=prefs,
                top_n=3,
            )

        assert used_fallback
        assert len(recs) == 3

    def test_llm_returns_unknown_restaurants_gets_partial_then_fallback(self, provider, candidates, prefs):
        """LLM returns names not in candidates → those are rejected; if 0 valid → fallback."""
        bad_json = json.dumps({
            "recommendations": [
                {"rank": 1, "restaurant_name": "Nonexistent A", "explanation": "Fake."},
                {"rank": 2, "restaurant_name": "Nonexistent B", "explanation": "Also fake."},
            ],
        })
        mock_response = _mock_groq_response(bad_json)

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            recs, used_fallback = provider.rank_and_explain(
                messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                candidates=candidates,
                preferences=prefs,
                top_n=3,
            )

        assert used_fallback  # all recommendations were unknown, so fallback activates
        assert len(recs) == 3

    def test_retries_on_api_failure(self, provider, candidates, prefs):
        """Provider should retry up to _MAX_RETRIES times before falling back."""
        call_count = 0

        def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Temporary failure")
            return _mock_groq_response(_valid_groq_json(candidates, top_n=3))

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = fail_then_succeed
            # Patch sleep to avoid actual waiting
            with patch("app.services.groq_service.time.sleep"):
                recs, used_fallback = provider.rank_and_explain(
                    messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                    candidates=candidates,
                    preferences=prefs,
                    top_n=3,
                )

        assert not used_fallback  # second attempt succeeded
        assert call_count == 2

    def test_no_crash_on_recommendation_with_all_fields(self, provider, candidates, prefs):
        """Ensure Recommendation objects have all expected fields."""
        valid_json = _valid_groq_json(candidates, top_n=2)
        mock_response = _mock_groq_response(valid_json)

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            recs, _ = provider.rank_and_explain(
                messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
                candidates=candidates,
                preferences=prefs,
                top_n=2,
            )

        for rec in recs:
            assert rec.rank >= 1
            assert rec.restaurant_name
            assert rec.explanation
            assert rec.rating >= 0
            assert rec.estimated_cost >= 0
            assert rec.location
            # Verify display properties work
            assert rec.cost_display
            assert rec.rating_stars
