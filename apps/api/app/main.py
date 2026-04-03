"""FastAPI application entry point."""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

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
from app.api.visualizations import router as viz_router
from app.api.cron import router as cron_router

DB_PATH = Path(__file__).resolve().parents[1] / "ipl_analytics.db"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://ipl.thetwok.in")


def _run_schema_migrations():
    """Add new columns to existing tables for DBs created before this version."""
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(engine)
    dialect = engine.dialect.name
    is_pg = dialect == "postgresql"

    def _get_cols(table):
        try:
            return {c["name"] for c in inspector.get_columns(table)}
        except Exception:
            return set()

    match_cols = _get_cols("matches")
    player_cols = _get_cols("players")
    team_cols = _get_cols("teams")

    stmts = []

    # matches
    if match_cols:
        if "cricapi_id" not in match_cols:
            stmts.append("ALTER TABLE matches ADD COLUMN cricapi_id VARCHAR(50) UNIQUE" if is_pg
                         else "ALTER TABLE matches ADD COLUMN cricapi_id TEXT UNIQUE")
        if "datetime_gmt" not in match_cols:
            stmts.append("ALTER TABLE matches ADD COLUMN datetime_gmt VARCHAR(50)")
        if "match_started" not in match_cols:
            stmts.append("ALTER TABLE matches ADD COLUMN match_started BOOLEAN DEFAULT FALSE")
        if "match_ended" not in match_cols:
            stmts.append("ALTER TABLE matches ADD COLUMN match_ended BOOLEAN DEFAULT FALSE")
        if "status_text" not in match_cols:
            stmts.append("ALTER TABLE matches ADD COLUMN status_text VARCHAR(300)")

    # players
    if player_cols:
        if "country" not in player_cols:
            stmts.append("ALTER TABLE players ADD COLUMN country VARCHAR(100)")
        if "player_img" not in player_cols:
            stmts.append("ALTER TABLE players ADD COLUMN player_img VARCHAR(500)")

    # teams
    if team_cols:
        if "img" not in team_cols:
            stmts.append("ALTER TABLE teams ADD COLUMN img VARCHAR(500)")

    # organizations — add team_id for multi-team dashboard scoping
    org_cols = _get_cols("organizations")
    if org_cols:
        if "team_id" not in org_cols:
            stmts.append("ALTER TABLE organizations ADD COLUMN team_id INTEGER REFERENCES teams(id)")

    if stmts:
        with engine.begin() as conn:
            for s in stmts:
                conn.execute(text(s))
        print(f"Schema migrations: {len(stmts)} columns added")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure DB exists, run ingestion if needed."""
    if settings.DATABASE_URL.startswith("postgresql"):
        Base.metadata.create_all(engine)
        _run_schema_migrations()
        print("PostgreSQL database ready.")
    elif not DB_PATH.exists():
        print("Database not found. Running initial data ingestion ...")
        from app.ingestion.load_csv import run_ingestion

        run_ingestion()
        print("Data ingestion complete.")
    else:
        # Ensure tables exist
        Base.metadata.create_all(engine)
        _run_schema_migrations()
        print(f"Database loaded from {DB_PATH}")

    # Start background match sync task (daily at 2 AM IST)
    sync_task = asyncio.create_task(_match_sync_loop())

    # Start WebSocket live score broadcaster (polls CricAPI, pushes to WS clients)
    from app.services.ws_manager import manager as ws_manager
    await ws_manager.start_polling()

    yield

    # Shutdown
    await ws_manager.stop_polling()
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

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

app.add_middleware(NoCacheMiddleware)

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
app.include_router(viz_router, prefix="/api/v1")
app.include_router(cron_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# WebSocket endpoint — real-time live score push
# ---------------------------------------------------------------------------

@app.websocket("/ws/live")
async def websocket_live_scores(ws: WebSocket):
    """WebSocket endpoint for real-time live score updates.

    Clients connect here and receive JSON payloads every ~30 seconds with:
      - Live match states (scores, win probability, game plans)
      - Upcoming fixtures
      - Recent results

    Connection is kept alive with the polling loop in ws_manager.
    Auto-reconnect should be handled client-side.
    """
    from app.services.ws_manager import manager as ws_manager

    await ws_manager.connect(ws)
    try:
        # Keep connection open — listen for client messages (e.g., ping)
        while True:
            data = await ws.receive_text()
            # Client can send "ping" to keep alive; we respond with "pong"
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    if settings.DATABASE_URL.startswith("postgresql"):
        db_status = "connected"
    else:
        db_status = "connected" if DB_PATH.exists() else "missing"
    return {
        "status": "healthy",
        "database": db_status,
        "version": "1.0.0",
    }
