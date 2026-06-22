from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT, Settings, settings


def test_settings_loads_with_defaults() -> None:
    assert settings.hf_dataset_id == "ManikaSaini/zomato-restaurant-recommendation"
    assert settings.groq_model == "llama-3.3-70b-versatile"
    assert settings.top_k_candidates == 25
    assert settings.top_n_recommendations == 5


def test_cache_path_resolves_under_project_root() -> None:
    assert settings.cache_path == (PROJECT_ROOT / "data" / "cache").resolve()


def test_ensure_cache_dir_creates_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("CACHE_DIR", str(cache_dir))
    test_settings = Settings()
    created = test_settings.ensure_cache_dir()
    assert created.exists()
    assert created.is_dir()


def test_top_n_cannot_exceed_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOP_K_CANDIDATES", "3")
    monkeypatch.setenv("TOP_N_RECOMMENDATIONS", "5")
    with pytest.raises(ValidationError):
        Settings()


def test_groq_configured_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert Settings().groq_configured is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert Settings().groq_configured is True
