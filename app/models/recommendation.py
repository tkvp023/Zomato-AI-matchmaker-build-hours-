"""Output models for the recommendation pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class Recommendation(BaseModel):
    """A single ranked restaurant recommendation with AI explanation."""

    rank: int = Field(..., ge=1, description="Position in the ranked list (1 = best)")
    restaurant_name: str = Field(..., description="Restaurant name")
    cuisine: str = Field(default="", description="Cuisine type(s) as a string")
    rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Aggregate rating")
    estimated_cost: float = Field(default=0.0, ge=0.0, description="Cost for two (INR)")
    location: str = Field(default="", description="Neighbourhood / area")
    explanation: str = Field(..., description="AI-generated personalised explanation")

    @property
    def cost_display(self) -> str:
        if self.estimated_cost:
            return f"₹{int(self.estimated_cost)} for two"
        return "N/A"

    @property
    def rating_stars(self) -> str:
        full = int(self.rating)
        half = 1 if (self.rating - full) >= 0.5 else 0
        return "★" * full + ("½" if half else "") + f"  ({self.rating:.1f})"


class RecommendationResponse(BaseModel):
    """Full response returned by the orchestrator."""

    recommendations: list[Recommendation] = Field(default_factory=list)
    summary: str = Field(default="", description="Optional summary from the LLM")
    total_candidates_considered: int = Field(
        default=0, description="Number of candidates sent to the LLM"
    )
    filters_applied: dict[str, Any] = Field(
        default_factory=dict, description="Snapshot of the filters that were applied"
    )
    used_fallback: bool = Field(
        default=False, description="True when the fallback ranker was used"
    )
    empty_reason: str = Field(
        default="", description="Human-readable reason when recommendations is empty"
    )

    @property
    def is_empty(self) -> bool:
        return len(self.recommendations) == 0


class GroqRawResponse(BaseModel):
    """Schema that the LLM is asked to return as JSON."""

    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = Field(default="")

    @field_validator("recommendations", mode="before")
    @classmethod
    def must_be_list(cls, v: object) -> list:
        if isinstance(v, list):
            return v
        return []
