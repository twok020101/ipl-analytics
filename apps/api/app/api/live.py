"""
Live match tracking API endpoints.

Provides real-time match scores, ML win probability, and dynamic game plans.
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db
from app.services.live_tracker import (
    init_tracker,
    fetch_live_scores,
    fetch_match_playing11,
    build_live_match_state,
    predict_live_win_probability,
    poll_and_update,
    get_match_history,
    record_snapshot,
    _extract_venue_city,
)
from app.services.weather import fetch_weather
from app.services.game_plan_live import recalculate_game_plan
from app.services.match_sync import sync_results
from app.config import settings

router = APIRouter(prefix="/live", tags=["live"])

# Initialize tracker on import
if settings.CRICAPI_KEY:
    init_tracker(settings.CRICAPI_KEY)


@router.get("/scores")
async def get_live_scores():
    """Get all live IPL match scores with ML win predictions.

    Uses cricScore endpoint (1 API call for ALL matches).
    Each live match includes real-time win probability from XGBoost model.
    Syncing is handled by the daily background loop and the /live/sync endpoint.
    """
    matches = await fetch_live_scores()

    live_states = []
    upcoming = []
    results = []

    for m in matches:
        if m["match_state"] == "live":
            state = await build_live_match_state(m)
            # Record snapshot only if score changed since last one
            score = state.get("current_score")
            prev = get_match_history(m["id"])
            if score and (not prev or prev[-1].get("current_score") != score):
                record_snapshot(m["id"], state)
            live_states.append(state)
        elif m["match_state"] == "fixture":
            upcoming.append({
                "match_id": m["id"],
                "team1": m["team1"],
                "team2": m["team2"],
                "datetime_gmt": m["datetime_gmt"],
                "status": m["status"],
            })
        elif m["match_state"] == "result":
            results.append({
                "match_id": m["id"],
                "team1": m["team1"],
                "team2": m["team2"],
                "team1_score": m["team1_score"],
                "team2_score": m["team2_score"],
                "status": m["status"],
            })

    for state in live_states:
        mid = state.get("match_id")
        state["history"] = get_match_history(mid) if mid else []

    return {
        "live": live_states,
        "upcoming": upcoming[:5],
        "recent_results": results[:5],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


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
