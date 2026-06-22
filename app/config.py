from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    hf_dataset_id: str = Field(
        default="ManikaSaini/zomato-restaurant-recommendation",
        validation_alias="HF_DATASET_ID",
    )
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        validation_alias="GROQ_MODEL",
    )
    top_k_candidates: int = Field(default=25, validation_alias="TOP_K_CANDIDATES", ge=1)
    top_n_recommendations: int = Field(
        default=5,
        validation_alias="TOP_N_RECOMMENDATIONS",
        ge=1,
    )
    cache_dir: Path = Field(default=Path("data/cache"), validation_alias="CACHE_DIR")

    @field_validator("cache_dir", mode="before")
    @classmethod
    def normalize_cache_dir(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            return PROJECT_ROOT / path
        return path

    @model_validator(mode="after")
    def validate_recommendation_limits(self) -> "Settings":
        if self.top_n_recommendations > self.top_k_candidates:
            raise ValueError(
                "TOP_N_RECOMMENDATIONS must be less than or equal to TOP_K_CANDIDATES"
            )
        return self

    @property
    def cache_path(self) -> Path:
        return self.cache_dir.resolve()

    def ensure_cache_dir(self) -> Path:
        self.cache_path.mkdir(parents=True, exist_ok=True)
        return self.cache_path

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key.strip())


settings = Settings()
