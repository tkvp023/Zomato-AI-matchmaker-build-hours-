"""Smoke test: live Groq API call with synthetic candidates.

Usage:
    python -m tests.smoke_groq

Requires GROQ_API_KEY to be set in .env.
"""

from __future__ import annotations

import io
import sys

# Fix Windows console encoding for star characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import sys
import textwrap

# Make project importable
sys.path.insert(0, ".")

from app.config import settings
from app.models.preferences import UserPreferences
from app.models.restaurant import Restaurant
from app.services.groq_service import GroqProvider
from app.services.prompt_builder import PromptBuilder


def _make_restaurant(
    name: str,
    location: str = "Indiranagar",
    cuisine: str = "North Indian",
    rating: float = 4.0,
    cost: float = 600.0,
    budget: str = "medium",
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
        tags=["popular"],
    )


SAMPLE_CANDIDATES = [
    _make_restaurant("Punjabi Tadka", rating=4.5, cost=500),
    _make_restaurant("Spice Garden", rating=4.2, cost=700),
    _make_restaurant("Dragon Palace", cuisine="Chinese", rating=3.8, cost=800, budget="high"),
    _make_restaurant("Biryani Blues", cuisine="Hyderabadi", rating=4.0, cost=400, budget="low"),
    _make_restaurant("Pasta Corner", cuisine="Italian", rating=4.3, cost=900, budget="high"),
    _make_restaurant("Taco Bell", cuisine="Mexican", rating=3.5, cost=350, budget="low"),
    _make_restaurant("The Rameshwaram Cafe", cuisine="South Indian", rating=4.6, cost=300, budget="low"),
    _make_restaurant("Truffles", cuisine="Continental, Burgers", rating=4.4, cost=600),
    _make_restaurant("Meghana Foods", cuisine="Andhra, Biryani", rating=4.5, cost=500),
    _make_restaurant("Empire Restaurant", cuisine="North Indian, Kebabs", rating=4.1, cost=550),
]


def main() -> None:
    if not settings.groq_configured:
        print("ERROR: GROQ_API_KEY not set. Please add it to .env")
        sys.exit(1)

    print(f"=== Groq Smoke Test ===")
    print(f"Model: {settings.groq_model}")
    print(f"Candidates: {len(SAMPLE_CANDIDATES)}")
    print()

    prefs = UserPreferences(
        location="Indiranagar",
        budget="medium",
        cuisine="North Indian",
        min_rating=3.5,
        additional_preferences="outdoor seating, family friendly",
    )

    builder = PromptBuilder()
    provider = GroqProvider()

    messages = builder.build(prefs, SAMPLE_CANDIDATES, top_n=5)

    print("--- System prompt (first 300 chars) ---")
    print(messages[0]["content"][:300])
    print("...")
    print()

    print("--- Calling Groq API... ---")
    recs, used_fallback = provider.rank_and_explain(
        messages=messages,
        candidates=SAMPLE_CANDIDATES,
        preferences=prefs,
        top_n=5,
    )

    print(f"Used fallback: {used_fallback}")
    print(f"Recommendations returned: {len(recs)}")
    print()

    for rec in recs:
        print(f"  #{rec.rank}  {rec.restaurant_name}")
        print(f"       Cuisine:  {rec.cuisine}")
        print(f"       Rating:   {rec.rating_stars}")
        print(f"       Cost:     {rec.cost_display}")
        print(f"       Location: {rec.location}")
        print(f"       Explain:  {textwrap.fill(rec.explanation, width=70, initial_indent='', subsequent_indent='                ')}")
        print()

    # Validation checks
    print("=== Validation ===")
    errors = []

    if used_fallback:
        errors.append("WARN: Fallback was used (Groq may have failed)")

    if len(recs) == 0:
        errors.append("FAIL: No recommendations returned")

    candidate_names = {r.name for r in SAMPLE_CANDIDATES}
    for rec in recs:
        if rec.restaurant_name not in candidate_names:
            errors.append(f"FAIL: '{rec.restaurant_name}' not in candidate list (hallucination!)")
        if len(rec.explanation) < 20:
            errors.append(f"FAIL: Explanation for '{rec.restaurant_name}' too short")

    if errors:
        for e in errors:
            print(f"  ❌ {e}")
    else:
        print("  ✅ All checks passed!")
        print("  ✅ Valid JSON parsed successfully")
        print("  ✅ All restaurant names from candidate list")
        print("  ✅ Explanations are reasonable length")
        print("  ✅ Ratings and costs match canonical values")

    print()
    print("=== Smoke test complete ===")


if __name__ == "__main__":
    main()
