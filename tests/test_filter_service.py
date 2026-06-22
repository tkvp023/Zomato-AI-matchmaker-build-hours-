"""Unit tests for FilterService and UserPreferences — Phase 2."""

from __future__ import annotations

import pytest

from app.models.preferences import PreferenceValidationError, UserPreferences
from app.models.restaurant import Restaurant
from app.services.filter_service import FilterService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_restaurant(
    name: str = "Test Restaurant",
    location: str = "Indiranagar",
    cuisine: str = "North Indian, Chinese",
    rating: float = 4.0,
    cost_for_two: float = 600.0,
    budget_tier: str = "medium",
    tags: list[str] | None = None,
) -> Restaurant:
    return Restaurant(
        id=name.lower().replace(" ", "_"),
        name=name,
        location=location,
        city="Bangalore",
        cuisine=cuisine,
        rating=rating,
        cost_for_two=cost_for_two,
        budget_tier=budget_tier,  # type: ignore[arg-type]
        address="",
        tags=tags or [],
    )


@pytest.fixture
def sample_restaurants() -> list[Restaurant]:
    return [
        _make_restaurant("Punjabi Tadka",    location="Indiranagar", cuisine="North Indian",        rating=4.2, cost_for_two=600,  budget_tier="medium"),
        _make_restaurant("Dragon Palace",    location="Indiranagar", cuisine="Chinese",              rating=3.8, cost_for_two=500,  budget_tier="medium"),
        _make_restaurant("Pizza Hub",        location="Indiranagar", cuisine="Italian, Fast Food",   rating=4.5, cost_for_two=350,  budget_tier="low"),
        _make_restaurant("Fine Dine",        location="Indiranagar", cuisine="Continental",          rating=4.7, cost_for_two=1500, budget_tier="high"),
        _make_restaurant("Street Bites",     location="Whitefield",  cuisine="Street Food",          rating=4.0, cost_for_two=200,  budget_tier="low"),
        _make_restaurant("Sushi World",      location="Whitefield",  cuisine="Japanese",             rating=4.3, cost_for_two=1200, budget_tier="high"),
        _make_restaurant("Curry Corner",     location="Koramangala", cuisine="South Indian",         rating=3.5, cost_for_two=300,  budget_tier="low"),
        _make_restaurant("Masala Magic",     location="Koramangala", cuisine="North Indian, Mughlai",rating=4.1, cost_for_two=800,  budget_tier="medium"),
        _make_restaurant("Burger Stop",      location="MG Road",     cuisine="Fast Food, American",  rating=3.9, cost_for_two=400,  budget_tier="low"),
        _make_restaurant("The Bistro",       location="MG Road",     cuisine="Continental, Cafe",    rating=4.6, cost_for_two=900,  budget_tier="medium"),
    ]


@pytest.fixture
def service(sample_restaurants) -> FilterService:
    return FilterService(sample_restaurants, top_k=25)


# ---------------------------------------------------------------------------
# UserPreferences model tests
# ---------------------------------------------------------------------------

class TestUserPreferences:
    def test_valid_minimal(self):
        p = UserPreferences(location="Indiranagar", budget="medium")
        assert p.location == "Indiranagar"
        assert p.cuisine is None
        assert p.min_rating == 0.0

    def test_rating_clamp_above_five(self):
        p = UserPreferences(location="X", budget="low", min_rating=9.9)
        assert p.min_rating == 5.0

    def test_rating_clamp_below_zero(self):
        p = UserPreferences(location="X", budget="low", min_rating=-1.0)
        assert p.min_rating == 0.0

    def test_strips_whitespace_location(self):
        p = UserPreferences(location="  Whitefield  ", budget="low")
        assert p.location == "Whitefield"

    def test_cuisine_none_when_empty_string(self):
        p = UserPreferences(location="X", budget="low", cuisine="")
        assert p.cuisine is None

    def test_additional_preferences_truncated(self):
        p = UserPreferences(location="X", budget="low", additional_preferences="a" * 600)
        assert len(p.additional_preferences) == 500

    def test_additional_preferences_strips_control_chars(self):
        p = UserPreferences(location="X", budget="low", additional_preferences="good\x00food")
        assert "\x00" not in p.additional_preferences


# ---------------------------------------------------------------------------
# FilterService.validate_preferences tests
# ---------------------------------------------------------------------------

class TestValidatePreferences:
    def test_exact_location_resolves(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        resolved = service.validate_preferences(prefs)
        assert resolved.location == "Indiranagar"

    def test_case_insensitive_location_resolves(self, service):
        prefs = UserPreferences(location="indiranagar", budget="medium")
        resolved = service.validate_preferences(prefs)
        assert resolved.location == "Indiranagar"

    def test_fuzzy_location_resolves(self, service):
        # "indira nagar" should fuzzy-match to "Indiranagar"
        prefs = UserPreferences(location="indira nagar", budget="medium")
        resolved = service.validate_preferences(prefs)
        assert resolved.location == "Indiranagar"

    def test_unknown_location_raises_with_suggestions(self, service):
        prefs = UserPreferences(location="xyzunknownplace99", budget="medium")
        with pytest.raises(PreferenceValidationError) as exc_info:
            service.validate_preferences(prefs)
        assert exc_info.value.suggestions

    def test_cuisine_resolved(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium", cuisine="chinese")
        resolved = service.validate_preferences(prefs)
        assert resolved.cuisine == "Chinese"

    def test_unknown_cuisine_not_required_no_error(self, service):
        # cuisine is optional — unknown cuisine should NOT raise, just return None
        prefs = UserPreferences(location="Indiranagar", budget="medium", cuisine="Klingon")
        resolved = service.validate_preferences(prefs)
        assert resolved.cuisine is None


# ---------------------------------------------------------------------------
# FilterService.filter — single-stage tests
# ---------------------------------------------------------------------------

class TestFilterLocation:
    def test_filters_to_indiranagar(self, service, sample_restaurants):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = service.filter(prefs)
        for r in result.candidates:
            assert "indiranagar" in r.location.lower()

    def test_filters_to_whitefield(self, service):
        prefs = UserPreferences(location="Whitefield", budget="low")
        result = service.filter(prefs)
        for r in result.candidates:
            assert "whitefield" in r.location.lower()

    def test_unknown_location_returns_empty(self, service):
        prefs = UserPreferences(location="NowhereCity", budget="medium")
        result = service.filter(prefs)
        assert result.is_empty
        assert result.empty_reason


class TestFilterRating:
    def test_min_rating_filters_low_rated(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium", min_rating=4.0)
        result = service.filter(prefs)
        for r in result.candidates:
            assert r.rating >= 4.0

    def test_zero_min_rating_keeps_all(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="low", min_rating=0.0)
        result = service.filter(prefs)
        # Pizza Hub is low budget in Indiranagar, rating 4.5 — should appear
        assert any(r.name == "Pizza Hub" for r in result.candidates)


class TestFilterCuisine:
    def test_cuisine_match(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium", cuisine="Chinese")
        result = service.filter(prefs)
        for r in result.candidates:
            assert any("chinese" in c.lower() for c in r.cuisine)

    def test_no_cuisine_keeps_all_cuisines(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium", cuisine=None)
        result = service.filter(prefs)
        # Both Punjabi Tadka and Dragon Palace are medium in Indiranagar
        names = {r.name for r in result.candidates}
        assert "Punjabi Tadka" in names
        assert "Dragon Palace" in names


class TestFilterBudget:
    def test_low_budget(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="low")
        result = service.filter(prefs)
        for r in result.candidates:
            assert r.budget_tier == "low"

    def test_high_budget(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="high")
        result = service.filter(prefs)
        for r in result.candidates:
            assert r.budget_tier == "high"

    def test_impossible_combo_returns_empty(self, service):
        # Whitefield has no "medium" restaurants in our fixtures
        prefs = UserPreferences(location="Whitefield", budget="medium")
        result = service.filter(prefs)
        assert result.is_empty
        assert result.empty_reason


# ---------------------------------------------------------------------------
# Combined filter + TOP_K cap
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    def test_combined_location_cuisine_budget(self, service):
        prefs = UserPreferences(
            location="Koramangala",
            budget="medium",
            cuisine="North Indian",
        )
        result = service.filter(prefs)
        assert len(result.candidates) >= 1
        assert result.candidates[0].name == "Masala Magic"

    def test_top_k_cap(self, sample_restaurants):
        """With top_k=2, never return more than 2 candidates."""
        svc = FilterService(sample_restaurants, top_k=2)
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = svc.filter(prefs)
        assert len(result.candidates) <= 2

    def test_top_k_cap_stage_recorded(self, sample_restaurants):
        svc = FilterService(sample_restaurants, top_k=1)
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = svc.filter(prefs)
        stage_names = [s.stage for s in result.stage_counts]
        assert "top_k_cap" in stage_names

    def test_results_sorted_by_rating_desc(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = service.filter(prefs)
        ratings = [r.rating for r in result.candidates]
        assert ratings == sorted(ratings, reverse=True)


# ---------------------------------------------------------------------------
# Stage counts metadata
# ---------------------------------------------------------------------------

class TestStageCounts:
    def test_stage_counts_populated(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = service.filter(prefs)
        assert len(result.stage_counts) >= 2  # at least location + budget

    def test_location_stage_first(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = service.filter(prefs)
        assert result.stage_counts[0].stage == "location"

    def test_empty_result_has_stage_counts(self, service):
        prefs = UserPreferences(location="NowhereCity", budget="medium")
        result = service.filter(prefs)
        assert len(result.stage_counts) >= 1


# ---------------------------------------------------------------------------
# Keyword boost (additional_preferences)
# ---------------------------------------------------------------------------

class TestKeywordBoost:
    def test_keyword_match_ranks_higher(self, sample_restaurants):
        """Restaurant whose name/cuisine matches keyword should rank first."""
        svc = FilterService(sample_restaurants, top_k=25)
        prefs = UserPreferences(
            location="MG Road",
            budget="medium",
            additional_preferences="continental cafe bistro",
        )
        result = svc.filter(prefs)
        # "The Bistro" matches keywords; it should be first
        assert result.candidates[0].name == "The Bistro"

    def test_no_keywords_falls_back_to_rating_sort(self, service):
        prefs = UserPreferences(location="Indiranagar", budget="medium")
        result = service.filter(prefs)
        ratings = [r.rating for r in result.candidates]
        assert ratings == sorted(ratings, reverse=True)
