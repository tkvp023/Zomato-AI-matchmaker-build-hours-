"""Integration tests for the FastAPI layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, lifespan
from app.models.preferences import UserPreferences
from app.models.recommendation import RecommendationResponse, Recommendation
from app.services.orchestrator import RecommendationOrchestrator


@pytest.fixture
def mock_orchestrator():
    """Mock the orchestrator to avoid loading the real dataset and hitting Groq."""
    orchestrator = MagicMock(spec=RecommendationOrchestrator)
    orchestrator.locations = ["Indiranagar", "Koramangala"]
    orchestrator.cuisines = ["North Indian", "Italian"]
    orchestrator._repository = MagicMock()
    orchestrator._repository.get_all.return_value = [1, 2, 3]  # Dummy data
    
    # Default successful response
    rec = Recommendation(
        rank=1,
        restaurant_name="Test Cafe",
        rating=4.5,
        estimated_cost=500.0,
        location="Indiranagar",
        cuisine="Cafe",
        explanation="Great coffee.",
    )
    resp = RecommendationResponse(
        recommendations=[rec],
        summary="Here are your picks",
        total_candidates_considered=10,
        filters_applied={"location": "Indiranagar"},
        used_fallback=False,
    )
    orchestrator.recommend.return_value = resp
    
    return orchestrator


@pytest.fixture
def client(mock_orchestrator):
    """Provide a TestClient with the mocked orchestrator injected."""
    # We patch the global orchestrator in app.api.main
    with patch("app.api.main.orchestrator", mock_orchestrator):
        yield TestClient(app)


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["dataset_loaded"] is True
    assert data["restaurant_count"] == 3


def test_metadata(client):
    response = client.get("/api/v1/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["locations"] == ["Indiranagar", "Koramangala"]
    assert data["cuisines"] == ["North Indian", "Italian"]
    assert data["budget_tiers"] == ["low", "medium", "high"]
    assert "rating_range" in data


def test_recommendations_success(client, mock_orchestrator):
    prefs = {
        "location": "Indiranagar",
        "budget": "medium",
        "cuisine": "Cafe",
        "min_rating": 4.0
    }
    response = client.post("/api/v1/recommendations", json=prefs)
    assert response.status_code == 200
    data = response.json()
    
    # Check that orchestrator.recommend was called
    mock_orchestrator.recommend.assert_called_once()
    
    # Check response structure
    assert "recommendations" in data
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["restaurant_name"] == "Test Cafe"
    assert data["summary"] == "Here are your picks"
    assert data["used_fallback"] is False


def test_recommendations_validation_error(client):
    """Test standard Pydantic validation error (e.g. missing required field)."""
    # missing location
    prefs = {
        "budget": "medium"
    }
    response = client.post("/api/v1/recommendations", json=prefs)
    assert response.status_code == 422  # Unprocessable Entity
    data = response.json()
    assert "detail" in data


def test_recommendations_custom_validation_error(client, mock_orchestrator):
    """Test when orchestrator raises PreferenceValidationError."""
    from app.models.preferences import PreferenceValidationError, ValidationSuggestion
    
    # Make orchestrator raise our custom validation error
    suggestion = ValidationSuggestion(
        field="location",
        provided="UnknownArea",
        suggestions=["Indiranagar"],
        message="Try Indiranagar"
    )
    error = PreferenceValidationError(suggestions=[suggestion])
    mock_orchestrator.recommend.side_effect = error
    
    prefs = {
        "location": "UnknownArea",
        "budget": "medium"
    }
    response = client.post("/api/v1/recommendations", json=prefs)
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["message"] == "Try Indiranagar"
    assert len(data["detail"]["suggestions"]) == 1
    assert data["detail"]["suggestions"][0]["field"] == "location"


def test_recommendations_internal_server_error(client, mock_orchestrator):
    """Test unexpected exception handling."""
    mock_orchestrator.recommend.side_effect = Exception("Unexpected crash")
    
    prefs = {
        "location": "Indiranagar",
        "budget": "medium"
    }
    response = client.post("/api/v1/recommendations", json=prefs)
    
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "An unexpected error occurred"
