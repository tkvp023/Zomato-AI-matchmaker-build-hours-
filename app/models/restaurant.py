from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


BudgetTier = Literal["low", "medium", "high"]


class Restaurant(BaseModel):
    """Canonical restaurant record derived from the Zomato dataset."""

    id: str = Field(..., description="Stable unique identifier")
    name: str = Field(..., description="Restaurant name")
    location: str = Field(..., description="Neighbourhood / area")
    city: str = Field(default="", description="City")
    cuisine: list[str] = Field(default_factory=list, description="List of cuisine types")
    rating: float = Field(..., ge=0.0, le=5.0, description="Aggregate rating 0–5")
    cost_for_two: float = Field(default=0.0, ge=0.0, description="Approximate cost for two (INR)")
    budget_tier: BudgetTier = Field(..., description="Derived budget tier: low / medium / high")
    address: str = Field(default="", description="Full address string")
    tags: list[str] = Field(default_factory=list, description="Extra keyword tags")

    @field_validator("cuisine", "tags", mode="before")
    @classmethod
    def coerce_to_list(cls, value: object) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    @field_validator("rating", mode="before")
    @classmethod
    def coerce_rating(cls, value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @field_validator("cost_for_two", mode="before")
    @classmethod
    def coerce_cost(cls, value: object) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            import re
            digits = re.sub(r"[^\d.]", "", value)
            return float(digits) if digits else 0.0
        return 0.0

    # Convenience helpers
    @property
    def cuisine_str(self) -> str:
        return ", ".join(self.cuisine)

    @property
    def cost_display(self) -> str:
        if self.cost_for_two:
            return f"₹{int(self.cost_for_two)} for two"
        return "N/A"
