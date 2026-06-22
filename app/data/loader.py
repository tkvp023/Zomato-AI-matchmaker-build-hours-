"""DatasetLoader — fetches the Zomato dataset from Hugging Face with retry/backoff."""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


class DatasetLoadError(RuntimeError):
    """Raised when the dataset cannot be loaded after all retries."""


class DatasetLoader:
    """Loads the Zomato dataset from Hugging Face and returns a pandas DataFrame."""

    def __init__(self, dataset_id: str | None = None) -> None:
        self._dataset_id = dataset_id or settings.hf_dataset_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Download and return the dataset as a DataFrame (all splits merged)."""
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(
                    "Loading dataset '%s' (attempt %d/%d)…",
                    self._dataset_id,
                    attempt,
                    _MAX_RETRIES,
                )
                return self._fetch()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = _BACKOFF_BASE ** attempt
                logger.warning(
                    "Dataset load failed (attempt %d): %s. Retrying in %.0fs…",
                    attempt,
                    exc,
                    wait,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(wait)

        raise DatasetLoadError(
            f"Failed to load dataset '{self._dataset_id}' after {_MAX_RETRIES} attempts."
        ) from last_error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch(self) -> pd.DataFrame:
        from datasets import load_dataset  # lazy import — heavy dependency

        ds = load_dataset(self._dataset_id, trust_remote_code=True)
        frames: list[pd.DataFrame] = []
        for split_name, split_data in ds.items():
            df: pd.DataFrame = split_data.to_pandas()
            df["_split"] = split_name
            frames.append(df)

        if not frames:
            raise DatasetLoadError("Dataset returned no splits.")

        combined = pd.concat(frames, ignore_index=True)
        logger.info("Loaded %d raw records from '%s'.", len(combined), self._dataset_id)
        return combined

    # ------------------------------------------------------------------
    # Convenience: inspect raw columns
    # ------------------------------------------------------------------

    @staticmethod
    def inspect(df: pd.DataFrame) -> dict[str, Any]:
        """Return a summary dict useful for debugging column names / types."""
        return {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample": df.head(2).to_dict(orient="records"),
        }
