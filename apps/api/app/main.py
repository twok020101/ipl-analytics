"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.config import settings
from app.api.teams import router as teams_router
from app.api.players import router as players_router
from app.api.venues import router as venues_router
from app.api.headtohead import router as h2h_router
from app.api.predictions import router as predictions_router
from app.api.strategy import router as strategy_router
from app.api.ai_insights import router as ai_router
from app.api.season import router as season_router
from app.api.dashboard import router as dashboard_router
from app.api.external import router as external_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router

DB_PATH = Path(__file__).resolve().parents[1] / "ipl_analytics.db"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://ipl.thetwok.in")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure DB exists, run ingestion if needed."""
    if settings.DATABASE_URL.startswith("postgresql"):
        # PostgreSQL: drop and recreate auth tables if schema changed, then create all
        from app.models.models import User, Organization
        User.__table__.drop(engine, checkfirst=True)
        Organization.__table__.drop(engine, checkfirst=True)
        Base.metadata.create_all(engine)
        print("PostgreSQL database ready.")
    elif not DB_PATH.exists():
        print("Database not found. Running initial data ingestion ...")
        from app.ingestion.load_csv import run_ingestion

        run_ingestion()
        print("Data ingestion complete.")
    else:
        # Ensure tables exist
        Base.metadata.create_all(engine)
        print(f"Database loaded from {DB_PATH}")

    yield

    # Shutdown
    print("Shutting down.")


app = FastAPI(
    title="IPL Cricket Analytics API",
    description="Comprehensive IPL cricket analytics platform with ML predictions and AI insights.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "https://ipl.thetwok.in",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(teams_router, prefix="/api/v1")
app.include_router(players_router, prefix="/api/v1")
app.include_router(venues_router, prefix="/api/v1")
app.include_router(h2h_router, prefix="/api/v1")
app.include_router(predictions_router, prefix="/api/v1")
app.include_router(strategy_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(season_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(external_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    db_exists = DB_PATH.exists()
    return {
        "status": "healthy",
        "database": "connected" if db_exists else "missing",
        "version": "1.0.0",
    }
