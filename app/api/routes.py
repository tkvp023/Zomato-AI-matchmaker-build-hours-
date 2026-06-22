from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.models import HealthResponse, MetadataResponse, RatingRange
from app.config import settings
from app.models.preferences import PreferenceValidationError, UserPreferences
from app.models.recommendation import RecommendationResponse
from app.services.orchestrator import RecommendationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


def get_orchestrator() -> RecommendationOrchestrator:
    """Dependency injection for the orchestrator."""
    from app.api.main import orchestrator
    if orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized",
        )
    return orchestrator


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid preferences"},
        503: {"description": "Service unavailable"},
    },
)
def get_recommendations(
    preferences: UserPreferences,
    orchestrator: RecommendationOrchestrator = Depends(get_orchestrator),
) -> Any:
    """Get restaurant recommendations based on user preferences."""
    try:
        response = orchestrator.recommend(preferences)
        return response
    except PreferenceValidationError as e:
        logger.warning(f"Preference validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "suggestions": [{"field": s.field, "message": s.message} for s in e.suggestions]},
        )
    except Exception as e:
        logger.exception("Unexpected error during recommendation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    status_code=status.HTTP_200_OK,
)
def get_metadata(
    orchestrator: RecommendationOrchestrator = Depends(get_orchestrator),
) -> Any:
    """Get available locations, cuisines, and other metadata for UI dropdowns."""
    return MetadataResponse(
        locations=orchestrator.locations,
        cuisines=orchestrator.cuisines,
        budget_tiers=["low", "medium", "high"],
        rating_range=RatingRange(min=0.0, max=5.0),
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health_check(
    orchestrator: RecommendationOrchestrator = Depends(get_orchestrator),
) -> Any:
    """Check API health and dataset status."""
    return HealthResponse(
        status="ok",
        dataset_loaded=True,  # If orchestrator is available, dataset is loaded
        restaurant_count=len(orchestrator._repository.get_all()),
        groq_configured=bool(settings.groq_api_key),
    )
