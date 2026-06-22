"""Preprocessor — normalizes the raw Zomato DataFrame into Restaurant objects."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import pandas as pd

from app.models.restaurant import BudgetTier, Restaurant

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Location alias map  (raw value → canonical name)
# Extend as needed after inspecting the dataset.
# ---------------------------------------------------------------------------
_LOCATION_ALIASES: dict[str, str] = {
    "indira nagar": "Indiranagar",
    "indiranagar": "Indiranagar",
    "mg road": "MG Road",
    "m.g. road": "MG Road",
    "koramangala 5th block": "Koramangala",
    "koramangala 4th block": "Koramangala",
    "koramangala 1st block": "Koramangala",
    "church street": "Church Street",
    "brigade road": "Brigade Road",
    "whitefield": "Whitefield",
    "jp nagar": "JP Nagar",
    "j.p. nagar": "JP Nagar",
    "hsr layout": "HSR Layout",
    "btm layout": "BTM Layout",
    "btm": "BTM Layout",
    "electronic city": "Electronic City",
    "marathahalli": "Marathahalli",
    "jayanagar": "Jayanagar",
    "malleswaram": "Malleswaram",
    "rajajinagar": "Rajajinagar",
    "hebbal": "Hebbal",
    "yelahanka": "Yelahanka",
    "rt nagar": "RT Nagar",
    "r.t. nagar": "RT Nagar",
}

# Budget tier thresholds (INR, cost-for-two)
_BUDGET_LOW_MAX = 400
_BUDGET_HIGH_MIN = 1000


class Preprocessor:
    """Transforms a raw Zomato DataFrame into a list of validated Restaurant objects."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, df: pd.DataFrame) -> list[Restaurant]:
        """Full normalization pipeline. Returns only valid Restaurant records."""
        df = df.copy()
        logger.info("Preprocessing %d raw records…", len(df))

        df = self._rename_columns(df)
        df = self._drop_required_nulls(df)
        df = self._normalize_locations(df)
        df = self._normalize_cuisines(df)
        df = self._parse_cost(df)
        df = self._assign_budget_tier(df)
        df = self._normalize_ratings(df)
        df = self._assign_ids(df)

        restaurants = self._to_models(df)
        logger.info("Preprocessing complete: %d valid records.", len(restaurants))
        return restaurants

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Map known raw column name variants to our canonical names."""
        rename_map: dict[str, str] = {}

        col_lower = {c.lower().strip(): c for c in df.columns}

        candidates: dict[str, list[str]] = {
            "name": ["name", "restaurant name", "restaurant_name", "title"],
            "location": ["location", "locality", "area", "neighbourhood", "neighborhood", "locality verbose"],
            "city": ["city", "listed_in(city)"],
            "cuisine": ["cuisines", "cuisine", "cuisine type"],
            "rating": ["aggregate rating", "rating", "rate", "avg rating"],
            "cost_for_two": [
                "average cost for two", "cost for two", "cost_for_two",
                "approx. cost(for two people)", "approx cost for two",
                "approx_cost(for two people)"
            ],
            "address": ["address", "full address"],
        }

        for canonical, variants in candidates.items():
            for variant in variants:
                if variant in col_lower:
                    original = col_lower[variant]
                    if original != canonical:
                        rename_map[original] = canonical
                    break

        if rename_map:
            df = df.rename(columns=rename_map)

        return df

    @staticmethod
    def _drop_required_nulls(df: pd.DataFrame) -> pd.DataFrame:
        required = [c for c in ("name", "location", "rating") if c in df.columns]
        before = len(df)
        df = df.dropna(subset=required)
        df = df[df["name"].astype(str).str.strip() != ""]
        df = df[df["location"].astype(str).str.strip() != ""]
        logger.debug("Dropped %d rows missing required fields.", before - len(df))
        return df.reset_index(drop=True)

    @staticmethod
    def _normalize_locations(df: pd.DataFrame) -> pd.DataFrame:
        def _norm(val: Any) -> str:
            s = str(val).lower().strip()
            return _LOCATION_ALIASES.get(s, str(val).strip().title())

        df["location"] = df["location"].apply(_norm)
        return df

    @staticmethod
    def _normalize_cuisines(df: pd.DataFrame) -> pd.DataFrame:
        def _norm(val: Any) -> str:
            if pd.isna(val):
                return ""
            parts = re.split(r"[,/|]", str(val))
            seen: list[str] = []
            for p in parts:
                p = p.strip().title()
                if p and p not in seen:
                    seen.append(p)
            return ", ".join(seen)

        if "cuisine" in df.columns:
            df["cuisine"] = df["cuisine"].apply(_norm)
        return df

    @staticmethod
    def _parse_cost(df: pd.DataFrame) -> pd.DataFrame:
        def _parse(val: Any) -> float:
            if pd.isna(val):
                return 0.0
            # Always work from string representation to avoid pandas locale inference
            s = str(val).strip()
            if s in ("", "nan", "None", "N/A", "n/a"):
                return 0.0
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
            # Remove commas (thousands separators) then extract digits only
            # Keep a single decimal point only if it appears AFTER at least one digit
            cleaned = s.replace(",", "")
            # Extract all digit sequences and join — handles "Rs. 1200" → "1200"
            digit_parts = re.findall(r"\d+", cleaned)
            if not digit_parts:
                return 0.0
            # If there's exactly one run with a dot (e.g. "12.50"), preserve it
            dot_match = re.search(r"(\d+\.\d+)", cleaned)
            if dot_match:
                digits = dot_match.group(1)
            else:
                digits = "".join(digit_parts)
            return float(digits) if digits else 0.0

        if "cost_for_two" in df.columns:
            df["cost_for_two"] = df["cost_for_two"].apply(_parse)
        else:
            df["cost_for_two"] = 0.0
        return df

    @staticmethod
    def _assign_budget_tier(df: pd.DataFrame) -> pd.DataFrame:
        def _tier(cost: float) -> BudgetTier:
            if cost <= _BUDGET_LOW_MAX:
                return "low"
            if cost >= _BUDGET_HIGH_MIN:
                return "high"
            return "medium"

        df["budget_tier"] = df["cost_for_two"].apply(_tier)
        return df

    @staticmethod
    def _normalize_ratings(df: pd.DataFrame) -> pd.DataFrame:
        def _norm(val: Any) -> float:
            if pd.isna(val):
                return 0.0
            if isinstance(val, (int, float)):
                f = float(val)
            else:
                cleaned = re.sub(r"[^\d.]", "", str(val))
                f = float(cleaned) if cleaned else 0.0
            # Some datasets use a 1–100 scale; normalise to 0–5
            if f > 10:
                f = f / 20.0
            return max(0.0, min(5.0, round(f, 1)))

        df["rating"] = df["rating"].apply(_norm)
        return df

    @staticmethod
    def _assign_ids(df: pd.DataFrame) -> pd.DataFrame:
        def _make_id(row: pd.Series) -> str:
            key = f"{row.get('name', '')}|{row.get('location', '')}|{row.get('cuisine', '')}"
            return hashlib.md5(key.encode()).hexdigest()[:12]  # noqa: S324

        if "id" not in df.columns:
            df["id"] = df.apply(_make_id, axis=1)
        else:
            mask = df["id"].isna() | (df["id"].astype(str).str.strip() == "")
            df.loc[mask, "id"] = df[mask].apply(_make_id, axis=1)
        return df

    @staticmethod
    def _to_models(df: pd.DataFrame) -> list[Restaurant]:
        records: list[Restaurant] = []
        for _, row in df.iterrows():
            try:
                records.append(
                    Restaurant(
                        id=str(row.get("id", "")),
                        name=str(row.get("name", "")).strip(),
                        location=str(row.get("location", "")).strip(),
                        city=str(row.get("city", "")).strip() if not pd.isna(row.get("city")) else "",
                        cuisine=str(row.get("cuisine", "")),
                        rating=row.get("rating", 0.0),
                        cost_for_two=row.get("cost_for_two", 0.0),
                        budget_tier=row.get("budget_tier", "medium"),
                        address=str(row.get("address", "")).strip() if not pd.isna(row.get("address", None)) else "",
                        tags=[],
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping invalid row: %s", exc)
        return records
