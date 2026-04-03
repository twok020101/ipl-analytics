"""Cron endpoints for Railway scheduled jobs."""

import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings

router = APIRouter(prefix="/cron", tags=["cron"])
logger = logging.getLogger("cron")


def verify_cron_secret(x_cron_secret: str = Header(None, alias="X-Cron-Secret")):
    """Validate cron secret if JWT_SECRET is configured."""
    if settings.JWT_SECRET and x_cron_secret != settings.JWT_SECRET:
        raise HTTPException(403, "Invalid cron secret")


@router.post("/refresh-squads")
async def refresh_squads(
    _: None = Depends(verify_cron_secret),
    db: Session = Depends(get_db),
):
    """Refresh IPL 2026 squad and fixture data from CricAPI."""
    if not settings.CRICAPI_KEY:
        return {"status": "skipped", "reason": "CRICAPI_KEY not configured"}

    from app.services.external_api import refresh_ipl2026_data

    try:
        result = await refresh_ipl2026_data(db)
        if "error" in result:
            logger.warning(f"Cron refresh failed: {result['error']}")
            return {"status": "error", "detail": result["error"]}

        teams_count = len(result.get("squads", {}))
        fixtures_count = len(result.get("fixtures", []))
        logger.info(f"Cron refresh OK: {teams_count} teams, {fixtures_count} fixtures")
        return {
            "status": "refreshed",
            "teams": teams_count,
            "fixtures": fixtures_count,
        }
    except Exception as e:
        logger.error(f"Cron refresh exception: {e}")
        return {"status": "error", "detail": str(e)}


@router.post("/sync-results")
async def sync_match_results(
    _: None = Depends(verify_cron_secret),
    db: Session = Depends(get_db),
):
    """Sync completed match results and player stats from CricAPI to database."""
    if not settings.CRICAPI_KEY:
        return {"status": "skipped", "reason": "CRICAPI_KEY not configured"}

    try:
        from app.services.match_sync import sync_results
        from app.services.scorecard_sync import sync_player_stats

        # Sync match results first (scores, winners)
        result = await sync_results(db)
        logger.info(f"Cron sync results: {result}")

        # Then sync per-player batting/bowling stats from scorecards
        stats_result = await sync_player_stats(db)
        logger.info(f"Cron player stats: {stats_result}")

        return {"status": "synced", "match_sync": result, "player_stats": stats_result}
    except Exception as e:
        logger.error(f"Cron sync exception: {e}")
        return {"status": "error", "detail": str(e)}


@router.post("/sync-player-stats")
async def sync_player_stats_endpoint(
    _: None = Depends(verify_cron_secret),
    db: Session = Depends(get_db),
):
    """Standalone endpoint to sync player batting/bowling stats from CricAPI scorecards.

    Fetches scorecards for all completed 2026 matches and aggregates
    per-player stats into PlayerSeasonBatting/Bowling tables.
    """
    if not settings.CRICAPI_KEY:
        return {"status": "skipped", "reason": "CRICAPI_KEY not configured"}

    try:
        from app.services.scorecard_sync import sync_player_stats

        result = await sync_player_stats(db)
        logger.info(f"Player stats sync: {result}")
        return result
    except Exception as e:
        logger.error(f"Player stats sync exception: {e}")
        return {"status": "error", "detail": str(e)}


