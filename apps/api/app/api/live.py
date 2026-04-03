"""
Live match tracking API endpoints.

Provides real-time match scores, ML win probability, and dynamic game plans.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_viewer
from app.models.models import User
from app.services.post_match import analyze_match
from app.services.live_tracker import (
    init_tracker,
    fetch_live_scores,
    fetch_match_playing11,
    build_live_match_state,
    build_scores_payload,
    predict_live_win_probability,
    poll_and_update,
    get_match_history,
    record_snapshot,
)
from app.services.match_sync import sync_results
from app.config import settings

router = APIRouter(prefix="/live", tags=["live"])

# Initialize tracker on import
if settings.CRICAPI_KEY:
    init_tracker(settings.CRICAPI_KEY)


@router.get("/scores")
async def get_live_scores():
    """Get all live IPL match scores with ML win predictions.

    Uses the shared build_scores_payload() which categorizes matches into
    live/upcoming/result, runs ML models, and records snapshots.
    """
    return await build_scores_payload()


@router.get("/match/{match_id}")
async def get_live_match(match_id: str):
    """Get detailed live state for a specific match with playing 11."""
    matches = await fetch_live_scores()
    target_match = next((m for m in matches if m["id"] == match_id), None)

    if not target_match:
        return {"error": "Match not found in live feed"}

    state = await build_live_match_state(target_match)

    # Try to get playing 11 if match is live
    if target_match["match_state"] == "live":
        p11 = await fetch_match_playing11(match_id)
        if p11:
            state["toss"] = {
                "winner": p11.get("toss_winner"),
                "choice": p11.get("toss_choice"),
            }
            state["playing_11"] = p11.get("playing_11", {})

    state["history"] = get_match_history(match_id)
    return state


@router.get("/match/{match_id}/gameplan")
async def get_match_game_plan(match_id: str):
    """Get current game plan with weather for a live match."""
    matches = await fetch_live_scores()
    target_match = next((m for m in matches if m["id"] == match_id), None)

    if not target_match:
        return {"error": "Match not found in live feed"}

    if target_match["match_state"] != "live":
        return {"error": "Match is not live", "state": target_match["match_state"]}

    state = await build_live_match_state(target_match)

    return {
        "match_id": match_id,
        "team1": state.get("team1"),
        "team2": state.get("team2"),
        "innings": state.get("innings"),
        "batting_team": state.get("batting_team"),
        "bowling_team": state.get("bowling_team"),
        "current_score": state.get("current_score"),
        "game_plan": state.get("game_plan"),
        "weather": state.get("weather"),
        "win_probability": state.get("win_probability"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/match/{match_id}/history")
async def get_match_score_history(match_id: str):
    """Get score progression history for a match (snapshots every 5 min)."""
    return {
        "match_id": match_id,
        "snapshots": get_match_history(match_id),
    }


class WinProbRequest(BaseModel):
    innings: int  # 1 or 2
    runs: int
    wickets: int
    overs: float
    target: int = 0  # required for 2nd innings
    venue_avg: float = 165.0

@router.post("/predict")
async def predict_win_prob(req: WinProbRequest):
    """Calculate win probability from current match state using ML model.

    Works for both innings:
    - 1st innings: predicts batting-first team's win probability
    - 2nd innings: predicts chasing team's win probability (requires target)
    """
    result = predict_live_win_probability(
        innings=req.innings,
        runs=req.runs,
        wickets=req.wickets,
        overs=req.overs,
        target=req.target,
        venue_avg=req.venue_avg,
    )
    return result


@router.post("/poll")
async def trigger_poll(db: Session = Depends(get_db)):
    """Manually trigger a score poll, sync results, and update.

    In production, this is called by a cron job every 5 minutes
    during match hours (13:30-23:30 IST).
    """
    # First sync any completed match results to DB + cache
    sync = await sync_results(db)

    # Then poll live matches
    states = await poll_and_update()
    return {
        "polled_at": datetime.now(timezone.utc).isoformat(),
        "live_matches": len(states),
        "states": states,
        "sync": sync,
    }


@router.post("/sync")
async def sync_match_results(db: Session = Depends(get_db)):
    """Sync completed match results from CricAPI to database and fixture cache.

    Updates: match winners, scores, overs, toss data, fixture status.
    Call this after a match ends to update standings and fixtures.
    """
    result = await sync_results(db)
    return result


# ---------------------------------------------------------------------------
# Post-match analysis
# ---------------------------------------------------------------------------

@router.get("/analysis/{match_id}")
def get_post_match_analysis(
    match_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_viewer),
):
    """Post-match analysis with win probability curve and turning points.

    For historical matches (2008-2025): ball-by-ball replay through XGBoost.
    For IPL 2026 matches: over-by-over reconstruction from live snapshots.

    Returns:
      - curve: over-by-over win probability data points
      - turning_points: moments where win prob swung >= 10%
      - match metadata (teams, winner, scores)
    """
    result = analyze_match(db, match_id)
    if not result:
        return {"error": "Match not found or no data available"}
    return result
