"""UserPreferences model with fuzzy validation against repository vocabulary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

BudgetType = Literal["low", "medium", "high"]


class ValidationSuggestion(BaseModel):
    """Returned when a field fails fuzzy validation."""
    field: str
    provided: str
    suggestions: list[str]
    message: str


class PreferenceValidationError(ValueError):
    """Raised when UserPreferences cannot be resolved against known vocabulary."""

    def __init__(self, suggestions: list[ValidationSuggestion]) -> None:
        self.suggestions = suggestions
        msgs = "; ".join(s.message for s in suggestions)
        super().__init__(msgs)


class UserPreferences(BaseModel):
    """Validated user preferences for restaurant filtering."""

    location: str = Field(..., min_length=1, description="Neighbourhood or area name")
    budget: BudgetType = Field(..., description="Budget tier: low / medium / high")
    cuisine: str | None = Field(default=None, description="Preferred cuisine type (optional)")
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Minimum acceptable rating")
    additional_preferences: str | None = Field(
        default=None,
        max_length=500,
        description="Free-text additional preferences (max 500 chars)",
    )

    @field_validator("location", mode="before")
    @classmethod
    def strip_location(cls, v: object) -> str:
        return str(v).strip()

    @field_validator("cuisine", mode="before")
    @classmethod
    def strip_cuisine(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("min_rating", mode="before")
    @classmethod
    def clamp_rating(cls, v: object) -> float:
        try:
            f = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(5.0, f))

    @field_validator("additional_preferences", mode="before")
    @classmethod
    def sanitize_additional(cls, v: object) -> str | None:
        if v is None:
            return None
        import re
        # Strip control characters to prevent prompt injection
        s = re.sub(r"[\x00-\x1f\x7f]", " ", str(v)).strip()
        return s[:500] if s else None

    @model_validator(mode="after")
    def validate_against_vocabulary(self) -> "UserPreferences":
        """
        No-op by default — vocabulary fuzzy matching is done externally
        (in FilterService) since the repository isn't available at model creation.
        This hook is here so orchestrator can call it after injecting vocab.
        """
        return self
