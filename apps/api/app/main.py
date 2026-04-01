"""FastAPI application entry point."""

import os
import asyncio
import logging
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
from app.api.live import router as live_router

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

    # Start background match sync task (every 5 minutes)
    sync_task = asyncio.create_task(_match_sync_loop())

    yield

    # Shutdown
    sync_task.cancel()


async def _match_sync_loop():
    """Background loop: sync match results daily at 2:00 AM IST."""
    from datetime import datetime, timezone, timedelta

    IST = timezone(timedelta(hours=5, minutes=30))
    logger = logging.getLogger("match_sync_loop")
    logger.info("Daily match sync scheduled for 2:00 AM IST")

    while True:
        try:
            # Calculate seconds until next 2:00 AM IST
            now = datetime.now(IST)
            target = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info(f"Next sync in {wait/3600:.1f} hours (at {target.strftime('%Y-%m-%d %H:%M IST')})")
            await asyncio.sleep(wait)

            # Only sync if CRICAPI key is available
            if not settings.CRICAPI_KEY:
                continue

            from app.services.match_sync import sync_results
            from app.database import SessionLocal

            db = SessionLocal()
            try:
                result = await sync_results(db)
                if result.get("db_updated"):
                    logger.info(f"Auto-sync: {result['db_updated']}")
            except Exception as e:
                logger.warning(f"Auto-sync error: {e}")
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Match sync loop stopped")
            break
        except Exception as e:
            logger.warning(f"Sync loop error: {e}")
            await asyncio.sleep(60)
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
app.include_router(live_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    db_exists = DB_PATH.exists()
    return {
        "status": "healthy",
        "database": "connected" if db_exists else "missing",
        "version": "1.0.0",
    }
