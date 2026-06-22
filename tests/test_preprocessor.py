"""Unit tests for app/data/preprocessor.py — Phase 1.6."""

from __future__ import annotations

import pandas as pd
import pytest

from app.data.preprocessor import Preprocessor, _BUDGET_LOW_MAX, _BUDGET_HIGH_MIN


@pytest.fixture
def preprocessor() -> Preprocessor:
    return Preprocessor()


def _make_df(**overrides) -> pd.DataFrame:
    """Return a minimal valid raw DataFrame row, with optional overrides."""
    base = {
        "name": ["Test Restaurant"],
        "location": ["Indiranagar"],
        "cuisines": ["North Indian, Chinese"],
        "aggregate rating": [4.2],
        "average cost for two": [600],
        "city": ["Bangalore"],
        "address": ["123 Test St"],
    }
    base.update({k: [v] for k, v in overrides.items()})
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# Column renaming
# ---------------------------------------------------------------------------

class TestRenameColumns:
    def test_renames_cuisines_to_cuisine(self, preprocessor):
        df = _make_df()
        df = preprocessor._rename_columns(df)
        assert "cuisine" in df.columns

    def test_renames_aggregate_rating(self, preprocessor):
        df = _make_df()
        df = preprocessor._rename_columns(df)
        assert "rating" in df.columns

    def test_renames_average_cost_for_two(self, preprocessor):
        df = _make_df()
        df = preprocessor._rename_columns(df)
        assert "cost_for_two" in df.columns


# ---------------------------------------------------------------------------
# Null dropping
# ---------------------------------------------------------------------------

class TestDropRequiredNulls:
    def test_drops_null_name(self, preprocessor):
        df = pd.DataFrame({
            "name": [None, "Good Place"],
            "location": ["Indiranagar", "Indiranagar"],
            "rating": [4.0, 3.5],
        })
        result = preprocessor._drop_required_nulls(df)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Good Place"

    def test_drops_null_location(self, preprocessor):
        df = pd.DataFrame({
            "name": ["A", "B"],
            "location": [None, "Whitefield"],
            "rating": [4.0, 3.5],
        })
        result = preprocessor._drop_required_nulls(df)
        assert len(result) == 1

    def test_drops_empty_string_name(self, preprocessor):
        df = pd.DataFrame({
            "name": ["   ", "Valid"],
            "location": ["L", "L"],
            "rating": [4.0, 3.5],
        })
        result = preprocessor._drop_required_nulls(df)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Location normalisation
# ---------------------------------------------------------------------------

class TestNormalizeLocations:
    @pytest.mark.parametrize("raw,expected", [
        ("indiranagar", "Indiranagar"),
        ("indira nagar", "Indiranagar"),
        ("INDIRANAGAR", "Indiranagar"),
        ("mg road", "MG Road"),
        ("whitefield", "Whitefield"),
        ("jp nagar", "JP Nagar"),
        ("church street", "Church Street"),
        ("SomeUnknownArea", "Someunknownarea"),  # title-cased fallback
    ])
    def test_normalises(self, preprocessor, raw, expected):
        df = pd.DataFrame({"location": [raw]})
        result = preprocessor._normalize_locations(df)
        assert result.iloc[0]["location"] == expected


# ---------------------------------------------------------------------------
# Cuisine normalisation
# ---------------------------------------------------------------------------

class TestNormalizeCuisines:
    def test_title_cases_and_deduplicates(self, preprocessor):
        df = pd.DataFrame({"cuisine": ["north indian, north indian, chinese"]})
        result = preprocessor._normalize_cuisines(df)
        assert result.iloc[0]["cuisine"] == "North Indian, Chinese"

    def test_handles_pipe_separator(self, preprocessor):
        df = pd.DataFrame({"cuisine": ["italian|mexican"]})
        result = preprocessor._normalize_cuisines(df)
        cuisines = result.iloc[0]["cuisine"].split(", ")
        assert "Italian" in cuisines
        assert "Mexican" in cuisines

    def test_handles_null(self, preprocessor):
        df = pd.DataFrame({"cuisine": [None]})
        result = preprocessor._normalize_cuisines(df)
        assert result.iloc[0]["cuisine"] == ""


# ---------------------------------------------------------------------------
# Cost parsing
# ---------------------------------------------------------------------------

class TestParseCost:
    @pytest.mark.parametrize("raw,expected", [
        (600, 600.0),
        (600.0, 600.0),
        ("₹600 for two", 600.0),
        ("600", 600.0),
        ("Rs. 1,200", 1200.0),
        (None, 0.0),
        ("", 0.0),
        ("N/A", 0.0),
    ])
    def test_parses(self, preprocessor, raw, expected):
        # Use dtype=object so pandas doesn't coerce string values to floats
        df = pd.DataFrame({"cost_for_two": pd.array([raw], dtype=object)})
        result = preprocessor._parse_cost(df)
        assert result.iloc[0]["cost_for_two"] == expected


# ---------------------------------------------------------------------------
# Budget tier assignment
# ---------------------------------------------------------------------------

class TestAssignBudgetTier:
    def test_low(self, preprocessor):
        df = pd.DataFrame({"cost_for_two": [float(_BUDGET_LOW_MAX)]})
        result = preprocessor._assign_budget_tier(df)
        assert result.iloc[0]["budget_tier"] == "low"

    def test_high(self, preprocessor):
        df = pd.DataFrame({"cost_for_two": [float(_BUDGET_HIGH_MIN)]})
        result = preprocessor._assign_budget_tier(df)
        assert result.iloc[0]["budget_tier"] == "high"

    def test_medium(self, preprocessor):
        df = pd.DataFrame({"cost_for_two": [600.0]})
        result = preprocessor._assign_budget_tier(df)
        assert result.iloc[0]["budget_tier"] == "medium"

    def test_zero_cost_is_low(self, preprocessor):
        df = pd.DataFrame({"cost_for_two": [0.0]})
        result = preprocessor._assign_budget_tier(df)
        assert result.iloc[0]["budget_tier"] == "low"


# ---------------------------------------------------------------------------
# Rating normalisation
# ---------------------------------------------------------------------------

class TestNormalizeRatings:
    @pytest.mark.parametrize("raw,expected", [
        (4.2, 4.2),
        ("4.2", 4.2),
        ("4.2/5", 4.2),
        (None, 0.0),
        (0, 0.0),
        (5.0, 5.0),
    ])
    def test_normalises(self, preprocessor, raw, expected):
        df = pd.DataFrame({"rating": [raw]})
        result = preprocessor._normalize_ratings(df)
        assert result.iloc[0]["rating"] == pytest.approx(expected, abs=0.05)

    def test_clamps_above_five(self, preprocessor):
        df = pd.DataFrame({"rating": [6.0]})
        result = preprocessor._normalize_ratings(df)
        assert result.iloc[0]["rating"] <= 5.0


# ---------------------------------------------------------------------------
# Full pipeline smoke test (no network)
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_run_returns_restaurants(self, preprocessor):
        df = _make_df()
        results = preprocessor.run(df)
        assert len(results) == 1
        r = results[0]
        assert r.name == "Test Restaurant"
        assert r.location == "Indiranagar"
        assert r.rating == pytest.approx(4.2, abs=0.1)
        assert r.budget_tier == "medium"
        assert isinstance(r.id, str) and len(r.id) > 0

    def test_run_drops_invalid_rows(self, preprocessor):
        df = pd.DataFrame({
            "name": [None, "Valid"],
            "location": ["L", "L"],
            "cuisines": ["Indian", "Indian"],
            "aggregate rating": [4.0, 3.5],
            "average cost for two": [500, 500],
        })
        results = preprocessor.run(df)
        assert len(results) == 1
        assert results[0].name == "Valid"
