"""Unit tests for PromptBuilder — Phase 3."""

from __future__ import annotations

import json

import pytest

from app.models.preferences import UserPreferences
from app.models.restaurant import Restaurant
from app.services.prompt_builder import PromptBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builder() -> PromptBuilder:
    return PromptBuilder()


def _make_restaurant(name: str, location: str = "Indiranagar", cuisine: str = "North Indian") -> Restaurant:
    return Restaurant(
        id=name.lower().replace(" ", "_"),
        name=name,
        location=location,
        city="Bangalore",
        cuisine=cuisine,
        rating=4.2,
        cost_for_two=600.0,
        budget_tier="medium",
        address="",
        tags=["popular"],
    )


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
def candidates() -> list[Restaurant]:
    return [
        _make_restaurant("Punjabi Tadka"),
        _make_restaurant("Spice Garden"),
        _make_restaurant("Dragon Palace", cuisine="Chinese"),
    ]


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------

class TestPromptBuilderStructure:
    def test_returns_two_messages(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert len(messages) == 2

    def test_first_message_is_system(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert messages[0]["role"] == "system"

    def test_second_message_is_user(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert messages[1]["role"] == "user"

    def test_messages_have_content_key(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert "content" in messages[0]
        assert "content" in messages[1]

    def test_system_prompt_non_empty(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert len(messages[0]["content"]) > 100

    def test_user_message_non_empty(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert len(messages[1]["content"]) > 50


# ---------------------------------------------------------------------------
# System prompt content tests
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_contains_top_n(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=5)
        assert "5" in messages[0]["content"]

    def test_contains_json_schema(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert "recommendations" in messages[0]["content"]
        assert "restaurant_name" in messages[0]["content"]

    def test_contains_anti_hallucination_rule(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        system = messages[0]["content"].lower()
        assert "do not invent" in system or "only recommend" in system or "candidate list" in system

    def test_contains_injection_guard(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        system = messages[0]["content"].lower()
        assert "ignore any instructions" in system or "system rules" in system


# ---------------------------------------------------------------------------
# User message content tests
# ---------------------------------------------------------------------------

class TestUserMessage:
    def test_contains_all_candidate_names(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        user_msg = messages[1]["content"]
        for r in candidates:
            assert r.name in user_msg

    def test_contains_location_preference(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert prefs.location in messages[1]["content"]

    def test_contains_budget_preference(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert prefs.budget in messages[1]["content"]

    def test_contains_cuisine_preference(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert prefs.cuisine in messages[1]["content"]

    def test_contains_min_rating(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert str(prefs.min_rating) in messages[1]["content"]

    def test_contains_additional_preferences(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        assert "outdoor seating" in messages[1]["content"]

    def test_candidates_block_is_valid_json(self, builder, prefs, candidates):
        """The candidates JSON array in the user message must be parseable."""
        messages = builder.build(prefs, candidates, top_n=3)
        user_msg = messages[1]["content"]
        # Extract the JSON part after the header
        json_part = user_msg.split("## Candidate Restaurants (JSON)\n", 1)[1]
        parsed = json.loads(json_part)
        assert isinstance(parsed, list)
        assert len(parsed) == len(candidates)

    def test_candidate_entry_has_required_fields(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=3)
        user_msg = messages[1]["content"]
        json_part = user_msg.split("## Candidate Restaurants (JSON)\n", 1)[1]
        parsed = json.loads(json_part)
        for entry in parsed:
            assert "name" in entry
            assert "cuisine" in entry
            assert "rating" in entry
            assert "cost_for_two" in entry
            assert "location" in entry

    def test_no_cuisine_renders_any(self, builder, candidates):
        prefs_no_cuisine = UserPreferences(location="Indiranagar", budget="medium")
        messages = builder.build(prefs_no_cuisine, candidates, top_n=3)
        assert "Any" in messages[1]["content"]

    def test_top_n_in_user_message(self, builder, prefs, candidates):
        messages = builder.build(prefs, candidates, top_n=7)
        assert "7" in messages[1]["content"]

    def test_different_top_n_changes_system_prompt(self, builder, prefs, candidates):
        m3 = builder.build(prefs, candidates, top_n=3)
        m5 = builder.build(prefs, candidates, top_n=5)
        # System prompts should differ only in the top_n number
        assert m3[0]["content"] != m5[0]["content"]
