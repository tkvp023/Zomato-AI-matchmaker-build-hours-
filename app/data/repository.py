"""RestaurantRepository — in-memory store with local Parquet cache."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.config import settings
from app.data.loader import DatasetLoader
from app.data.preprocessor import Preprocessor
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "restaurants.parquet"


class RestaurantRepository:
    """Loads, caches, and provides query access to Restaurant records."""

    def __init__(
        self,
        loader: DatasetLoader | None = None,
        preprocessor: Preprocessor | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._loader = loader or DatasetLoader()
        self._preprocessor = preprocessor or Preprocessor()
        self._cache_dir = cache_dir or settings.ensure_cache_dir()
        self._restaurants: list[Restaurant] = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Bootstrap the repository: read cache or download + preprocess."""
        cache_path = self._cache_dir / _CACHE_FILENAME
        if cache_path.exists():
            logger.info("Loading restaurants from cache: %s", cache_path)
            self._restaurants = self._from_parquet(cache_path)
        else:
            logger.info("Cache not found. Downloading dataset…")
            raw_df = self._loader.load()
            self._restaurants = self._preprocessor.run(raw_df)
            self._save_parquet(self._restaurants, cache_path)

        self._loaded = True
        logger.info("Repository ready: %d restaurants.", len(self._restaurants))

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_all(self) -> list[Restaurant]:
        self._ensure_loaded()
        return list(self._restaurants)

    def get_locations(self) -> list[str]:
        self._ensure_loaded()
        return sorted({r.location for r in self._restaurants if r.location})

    def get_cuisines(self) -> list[str]:
        self._ensure_loaded()
        seen: set[str] = set()
        for r in self._restaurants:
            for c in r.cuisine:
                if c:
                    seen.add(c)
        return sorted(seen)

    def get_by_id(self, restaurant_id: str) -> Restaurant | None:
        self._ensure_loaded()
        for r in self._restaurants:
            if r.id == restaurant_id:
                return r
        return None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _save_parquet(restaurants: list[Restaurant], path: Path) -> None:
        rows = [r.model_dump() for r in restaurants]
        # Flatten list fields to comma-separated strings for Parquet compatibility
        for row in rows:
            row["cuisine"] = ", ".join(row["cuisine"])
            row["tags"] = ", ".join(row["tags"])
        df = pd.DataFrame(rows)
        df.to_parquet(path, index=False)
        logger.info("Saved %d records to %s", len(restaurants), path)

    def _from_parquet(self, path: Path) -> list[Restaurant]:
        df = pd.read_parquet(path)
        # Re-run through preprocessor's model conversion
        return self._preprocessor._to_models(df)  # noqa: SLF001

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError(
                "RestaurantRepository has not been loaded. Call .load() first."
            )
