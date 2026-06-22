"""Pydantic models specific to the REST API layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RatingRange(BaseModel):
    """Min and max available ratings."""
    min: float
    max: float


class MetadataResponse(BaseModel):
    """Response model for /api/v1/metadata containing UI form options."""
    locations: list[str] = Field(description="List of available locations")
    cuisines: list[str] = Field(description="List of available cuisines")
    budget_tiers: list[str] = Field(description="Available budget tiers")
    rating_range: RatingRange = Field(description="Min and max possible ratings")


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    status: str = Field(description="Overall API status (e.g., 'ok')")
    dataset_loaded: bool = Field(description="True if the repository dataset is loaded in memory")
    restaurant_count: int = Field(description="Total number of restaurants in the repository")
    groq_configured: bool = Field(description="True if GROQ_API_KEY is configured")
