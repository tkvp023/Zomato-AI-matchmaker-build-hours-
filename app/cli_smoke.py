"""CLI smoke test — runs the full recommendation pipeline with hardcoded preferences.

Usage:
    python -m app.cli_smoke

Requires:
  - Dataset to be available (will download on first run)
  - GROQ_API_KEY in .env (falls back to deterministic ranker if missing)
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-35s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> None:
    from app.data.repository import RestaurantRepository
    from app.models.preferences import UserPreferences
    from app.services.orchestrator import RecommendationOrchestrator

    # --- 1. Load repository ---
    print("\n" + "=" * 60)
    print("  🍽️  Restaurant Recommender — CLI Smoke Test")
    print("=" * 60)

    print("\n📦 Loading dataset...")
    repo = RestaurantRepository()
    repo.load()
    print(f"   ✅ {len(repo.get_all())} restaurants loaded.")
    print(f"   📍 {len(repo.get_locations())} locations")
    print(f"   🍕 {len(repo.get_cuisines())} cuisines")

    # --- 2. Initialize orchestrator ---
    orchestrator = RecommendationOrchestrator(repository=repo)

    # --- 3. Define test preferences ---
    test_cases = [
        UserPreferences(
            location="Indiranagar",
            budget="medium",
            cuisine="North Indian",
            min_rating=3.5,
            additional_preferences="outdoor seating, family friendly",
        ),
        UserPreferences(
            location="Whitefield",
            budget="high",
            min_rating=4.0,
        ),
        UserPreferences(
            location="Koramangala",
            budget="low",
            cuisine="South Indian",
            min_rating=3.0,
        ),
    ]

    # --- 4. Run each test case ---
    for i, prefs in enumerate(test_cases, start=1):
        print(f"\n{'─' * 60}")
        print(f"  Test Case {i}")
        print(f"{'─' * 60}")
        print(f"  📍 Location: {prefs.location}")
        print(f"  💰 Budget:   {prefs.budget}")
        print(f"  🍕 Cuisine:  {prefs.cuisine or 'Any'}")
        print(f"  ⭐ Min Rating: {prefs.min_rating}")
        print(f"  📝 Notes:    {prefs.additional_preferences or 'None'}")
        print()

        result = orchestrator.recommend(prefs)

        if result.is_empty:
            print(f"  ⚠️  No results: {result.empty_reason}")
            continue

        print(f"  📊 Candidates considered: {result.total_candidates_considered}")
        print(f"  🤖 Fallback used: {'Yes' if result.used_fallback else 'No'}")
        print(f"  💬 Summary: {result.summary}")
        print()

        for rec in result.recommendations:
            print(f"  #{rec.rank}  {rec.restaurant_name}")
            print(f"      {rec.rating_stars}  |  {rec.cuisine}  |  {rec.cost_display}")
            print(f"      📍 {rec.location}")
            print(f"      💡 {rec.explanation}")
            print()

    print("=" * 60)
    print("  ✅ Smoke test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
