from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.data.repository import RestaurantRepository
from app.services.orchestrator import RecommendationOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global orchestrator instance initialized on startup
orchestrator: RecommendationOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    global orchestrator
    logger.info("Starting up FastAPI application...")
    
    # Initialize the repository and load the dataset
    repository = RestaurantRepository()
    try:
        repository.load()
        logger.info(f"Dataset loaded successfully with {len(repository.get_all())} records.")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        # In a real production app, we might fail fast here.
        # But we let it proceed to serve the error via health check.
    
    # Initialize the orchestrator
    orchestrator = RecommendationOrchestrator(repository=repository)
    logger.info("RecommendationOrchestrator initialized.")
    
    yield
    
    # Teardown
    logger.info("Shutting down FastAPI application...")


app = FastAPI(
    title="Zomato AI Recommender API",
    description="API for the Zomato AI Restaurant Recommendation system",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS — allow all origins since this is a public read-only API.
# This avoids issues with Vercel preview URLs, trailing slashes, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix="/api/v1")
