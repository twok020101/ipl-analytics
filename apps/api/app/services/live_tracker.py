"""
Live Match Tracker — monitors IPL matches and updates game plans in real-time.

Timeline for each match:
  T-30min: Fetch toss result + playing 11
  T-0:     Match starts — begin polling live score
  Every 5 min: Fetch score, run ML models, update game plan
  Match end: Record final result, update standings

Uses:
  - cricScore endpoint for lightweight live scores (1 API call for ALL matches)
  - match_scorecard for playing 11 (1 call per match at toss time)
  - In-match XGBoost models for win probability
  - Strategy engine for dynamic game plan updates
"""

import json
import httpx
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Optional

import joblib
import numpy as np

from app.config import MODEL_DIR
from app.services.cricapi_utils import parse_score, extract_team_short
from app.services.weather import fetch_weather, VENUE_COORDS
from app.services.game_plan_live import recalculate_game_plan

logger = logging.getLogger("live_tracker")

CRICAPI_KEY = None  # Set from config on init

# Score cache — avoids hitting CricAPI on every user request
_score_cache: list = []
_score_cache_time: datetime = datetime.min.replace(tzinfo=timezone.utc)
SCORE_CACHE_TTL = timedelta(seconds=15)

# ML model cache (loaded once from disk)
_ml_models = None


def _get_ml_models():
    global _ml_models
    if _ml_models is None:
        model_path = MODEL_DIR / "live_win_probability.joblib"
        if model_path.exists():
            _ml_models = joblib.load(model_path)
    return _ml_models

# In-memory state for tracked matches
_tracked_matches: dict = {}


def init_tracker(api_key: str):
    """Initialize tracker with API key."""
    global CRICAPI_KEY
    CRICAPI_KEY = api_key
    logger.info("Live tracker initialized")


def _is_match_window() -> bool:
    """Check if any IPL match could be live right now.

    IPL matches start at 15:30 IST (10:00 UTC) or 19:30 IST (14:00 UTC)
    and last ~4 hours. Only poll CricAPI during these windows.
    """
    from app.database import SessionLocal
    from app.models.models import Match

    try:
        db = SessionLocal()
        try:
            matches = db.query(Match).filter(
                Match.season == "2026",
                Match.match_ended == False,
                Match.datetime_gmt.isnot(None),
            ).all()
        finally:
            db.close()

        if not matches:
            return True  # no data, assume yes

        now = datetime.now(timezone.utc)
        for m in matches:
            try:
                start = datetime.fromisoformat(m.datetime_gmt.replace("Z", "+00:00"))
                if not start.tzinfo:
                    start = start.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            window_start = start - timedelta(minutes=30)
            window_end = start + timedelta(hours=5)
            if window_start <= now <= window_end:
                return True

        return False
    except Exception:
        return True  # on error, allow polling


async def fetch_live_scores() -> list:
    """Fetch all live IPL scores from cricScore endpoint.

    Only calls CricAPI when a match could be live (based on fixture schedule).
    Cached for 30 seconds to prevent API flood from multiple users.
    """
    global _score_cache, _score_cache_time

    now = datetime.now(timezone.utc)

    # Don't hit the API outside match windows
    if not _is_match_window():
        return _score_cache
    if _score_cache and (now - _score_cache_time) < SCORE_CACHE_TTL:
        return _score_cache

    if not CRICAPI_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.cricapi.com/v1/cricScore",
                params={"apikey": CRICAPI_KEY},
            )
            data = resp.json()
            if data.get("status") != "success":
                logger.warning(f"cricScore failed: {data.get('reason')}")
                return _score_cache  # return stale cache on API failure

            ipl_matches = []
            for m in data.get("data", []):
                if "indian premier" in m.get("series", "").lower():
                    ipl_matches.append({
                        "id": m["id"],
                        "team1": extract_team_short(m.get("t1", "")),
                        "team2": extract_team_short(m.get("t2", "")),
                        "team1_full": m.get("t1", ""),
                        "team2_full": m.get("t2", ""),
                        "team1_score": parse_score(m.get("t1s", "")),
                        "team2_score": parse_score(m.get("t2s", "")),
                        "status": m.get("status", ""),
                        "match_state": m.get("ms", ""),
                        "datetime_gmt": m.get("dateTimeGMT", ""),
                    })

            _score_cache = ipl_matches
            _score_cache_time = now
            return ipl_matches
    except Exception as e:
        logger.error(f"Error fetching live scores: {e}")
        return _score_cache  # return stale cache on error


async def fetch_match_playing11(match_id: str) -> dict:
    """Fetch playing 11 for a match (after toss)."""
    if not CRICAPI_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.cricapi.com/v1/match_scorecard",
                params={"apikey": CRICAPI_KEY, "id": match_id},
            )
            data = resp.json()
            if data.get("status") != "success":
                return {}

            match_data = data["data"]
            result = {
                "toss_winner": match_data.get("tossWinner", ""),
                "toss_choice": match_data.get("tossChoice", ""),
                "playing_11": {},
            }

            # Extract playing 11 from scorecard batting entries
            for inn in match_data.get("scorecard", []):
                team = inn.get("inning", "")
                players = []
                for b in inn.get("batting", []):
                    name = b.get("batsman", {}).get("name", "")
                    if name:
                        players.append(name)
                for b in inn.get("bowling", []):
                    name = b.get("bowler", {}).get("name", "")
                    if name and name not in players:
                        players.append(name)
                if team:
                    result["playing_11"][team] = players

            return result
    except Exception as e:
        logger.error(f"Error fetching playing 11: {e}")
        return {}


def predict_live_win_probability(
    innings: int,
    runs: int,
    wickets: int,
    overs: float,
    target: int = 0,
    venue_avg: float = 165.0,
) -> dict:
    """Use ML model to predict win probability from current match state."""
    models = _get_ml_models()
    if models is None:
        return _heuristic_probability(innings, runs, wickets, overs, target, venue_avg)

    if innings == 1:
        model = models["model_1st_innings"]
        over_num = int(overs)
        run_rate = runs / max(overs, 0.1)
        wickets_remaining = 10 - wickets
        overs_remaining = 19 - over_num
        projected = runs / max(overs / 20.0, 0.05)
        above_par = (projected - venue_avg) / max(venue_avg, 1)

        features = np.array([[runs, wickets, over_num, run_rate, wickets_remaining,
                              overs_remaining, projected, venue_avg, above_par]], dtype=np.float32)
        prob = float(model.predict_proba(features)[0][1])  # batting first wins

        return {
            "batting_team_win_prob": round(prob * 100, 1),
            "bowling_team_win_prob": round((1 - prob) * 100, 1),
            "model": "xgboost_1st_innings",
            "projected_score": round(projected),
            "run_rate": round(run_rate, 2),
        }
    else:
        model = models["model_2nd_innings"]
        over_num = int(overs)
        remaining_runs = target - runs + 1
        remaining_overs = max(20 - over_num - 1, 0.1)
        required_rate = remaining_runs / remaining_overs
        current_rate = runs / max(overs, 0.1)
        wickets_remaining = 10 - wickets

        features = np.array([[runs, wickets, over_num, target, remaining_runs,
                              required_rate, current_rate, wickets_remaining]], dtype=np.float32)
        prob = float(model.predict_proba(features)[0][1])  # chasing team wins

        return {
            "batting_team_win_prob": round(prob * 100, 1),
            "bowling_team_win_prob": round((1 - prob) * 100, 1),
            "model": "xgboost_2nd_innings",
            "required_rate": round(required_rate, 2),
            "current_rate": round(current_rate, 2),
            "runs_needed": max(remaining_runs, 0),
            "balls_remaining": max(int(remaining_overs * 6), 0),
        }


def _heuristic_probability(innings, runs, wickets, overs, target, venue_avg):
    """Fallback when ML model not available."""
    if innings == 1:
        projected = runs / max(overs / 20.0, 0.05)
        prob = 0.5 + (projected - venue_avg) / (venue_avg * 2)
        prob = max(0.1, min(0.9, prob))
    else:
        if target <= 0:
            return {"batting_team_win_prob": 50.0, "bowling_team_win_prob": 50.0, "model": "heuristic"}
        remaining = target - runs + 1
        remaining_overs = max(20 - overs, 0.1)
        req_rate = remaining / remaining_overs
        wickets_left = 10 - wickets
        prob = max(0.05, min(0.95, 0.5 + (wickets_left * 0.05) - (req_rate - 8) * 0.08))

    return {
        "batting_team_win_prob": round(prob * 100, 1),
        "bowling_team_win_prob": round((1 - prob) * 100, 1),
        "model": "heuristic",
    }


def _extract_venue_city(match: dict) -> Optional[str]:
    """Try to extract venue city from match status or team names."""
    status = match.get("status", "")
    # Use VENUE_COORDS keys as the canonical city list
    for city in VENUE_COORDS:
        if city.lower() in status.lower():
            return city
    return None


async def build_live_match_state(match: dict, include_weather: bool = True) -> dict:
    """Build comprehensive live match state from cricScore data.

    cricScore lists teams in fixture order (not batting order).
    We determine batting order from:
    - Which team has a completed innings (10 wickets or 20 overs)
    - The status text (e.g., "DC need 58 runs in 53 balls")
    """
    t1 = match["team1_score"]
    t2 = match["team2_score"]
    state = match["match_state"]
    status = match["status"]

    result = {
        "match_id": match["id"],
        "team1": match["team1"],
        "team2": match["team2"],
        "status": status,
        "state": state,
    }

    # Fetch weather for the venue city
    weather = None
    if include_weather and state == "live":
        city = _extract_venue_city(match)
        if city:
            weather = await fetch_weather(city)
            result["weather"] = weather

    if state == "live":
        # Determine batting order from scores
        # The team whose innings is complete (10 wkts or 20 overs) batted first
        t1_complete = t1["wickets"] >= 10 or t1["overs"] >= 20
        t2_complete = t2["wickets"] >= 10 or t2["overs"] >= 20

        if t2_complete and not t1_complete:
            # Team2 innings complete, team1 is chasing
            bat_first_team = match["team2"]
            bat_first_score = t2
            chase_team = match["team1"]
            chase_score = t1
        elif t1_complete and not t2_complete:
            # Team1 innings complete, team2 is chasing
            bat_first_team = match["team1"]
            bat_first_score = t1
            chase_team = match["team2"]
            chase_score = t2
        elif t1["overs"] > 0 and t2["overs"] == 0:
            # Only team1 has batted -- 1st innings
            result["innings"] = 1
            result["batting_team"] = match["team1"]
            result["bowling_team"] = match["team2"]
            result["current_score"] = t1

            win_prob = predict_live_win_probability(
                innings=1, runs=t1["runs"], wickets=t1["wickets"], overs=t1["overs"],
            )
            result["win_probability"] = {
                match["team1"]: win_prob["batting_team_win_prob"],
                match["team2"]: win_prob["bowling_team_win_prob"],
            }
            result["prediction_details"] = win_prob

            # Add game plan
            game_plan = recalculate_game_plan(
                innings=1, runs=t1["runs"], wickets=t1["wickets"],
                overs=t1["overs"], weather=weather, win_prob=win_prob,
            )
            result["game_plan"] = game_plan
            return result
        elif t2["overs"] > 0 and t1["overs"] == 0:
            # Only team2 has batted -- 1st innings
            result["innings"] = 1
            result["batting_team"] = match["team2"]
            result["bowling_team"] = match["team1"]
            result["current_score"] = t2

            win_prob = predict_live_win_probability(
                innings=1, runs=t2["runs"], wickets=t2["wickets"], overs=t2["overs"],
            )
            result["win_probability"] = {
                match["team2"]: win_prob["batting_team_win_prob"],
                match["team1"]: win_prob["bowling_team_win_prob"],
            }
            result["prediction_details"] = win_prob

            # Add game plan
            game_plan = recalculate_game_plan(
                innings=1, runs=t2["runs"], wickets=t2["wickets"],
                overs=t2["overs"], weather=weather, win_prob=win_prob,
            )
            result["game_plan"] = game_plan
            return result
        elif t1["overs"] == 0 and t2["overs"] == 0:
            # Match just started, no balls bowled yet — treat as early 1st innings
            result["innings"] = 1
            result["batting_team"] = match["team1"]
            result["bowling_team"] = match["team2"]
            result["current_score"] = t1
            return result
        else:
            # Both have scores -- the one with more overs/wickets batted first
            if t1["overs"] > t2["overs"]:
                bat_first_team, bat_first_score = match["team1"], t1
                chase_team, chase_score = match["team2"], t2
            else:
                bat_first_team, bat_first_score = match["team2"], t2
                chase_team, chase_score = match["team1"], t1

        # 2nd innings in progress
        target = bat_first_score["runs"] + 1
        result["innings"] = 2
        result["batting_team"] = chase_team
        result["bowling_team"] = bat_first_team
        result["current_score"] = chase_score
        result["target"] = target
        result["first_innings_score"] = bat_first_score

        win_prob = predict_live_win_probability(
            innings=2, runs=chase_score["runs"], wickets=chase_score["wickets"],
            overs=chase_score["overs"], target=target,
        )
        result["win_probability"] = {
            chase_team: win_prob["batting_team_win_prob"],
            bat_first_team: win_prob["bowling_team_win_prob"],
        }
        result["prediction_details"] = win_prob

        # Add game plan for 2nd innings
        game_plan = recalculate_game_plan(
            innings=2, runs=chase_score["runs"], wickets=chase_score["wickets"],
            overs=chase_score["overs"], target=target, weather=weather, win_prob=win_prob,
        )
        result["game_plan"] = game_plan

    elif state == "result":
        result["final_scores"] = {
            match["team1"]: t1,
            match["team2"]: t2,
        }

    return result


# Store match history for game plan evolution
_match_history: dict = {}  # match_id -> deque of snapshots (max 60)


def record_snapshot(match_id: str, state: dict):
    """Record a score snapshot for tracking game plan changes."""
    if match_id not in _match_history:
        _match_history[match_id] = deque(maxlen=60)
    _match_history[match_id].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **state,
    })


def get_match_history(match_id: str) -> list:
    """Get all snapshots for a match."""
    return list(_match_history.get(match_id, []))


async def poll_and_update() -> list:
    """Main polling function — fetch scores and update all live matches.

    Call this every 5 minutes during match hours.
    Returns list of live match states with ML predictions.
    """
    matches = await fetch_live_scores()
    live_states = []

    for m in matches:
        if m["match_state"] == "live":
            state = await build_live_match_state(m)
            record_snapshot(m["id"], state)
            live_states.append(state)

    return live_states
