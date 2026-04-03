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

from app.config import MODEL_DIR, CURRENT_SEASON
from app.services.cricapi_utils import parse_score, extract_team_short
from app.services.weather import fetch_weather, VENUE_COORDS
from app.services.game_plan_live import recalculate_game_plan

logger = logging.getLogger("live_tracker")

CRICAPI_KEY = None  # Set from config on init

# Score cache — avoids hitting CricAPI on every user request
_score_cache: list = []
_score_cache_time: datetime = datetime.min.replace(tzinfo=timezone.utc)
SCORE_CACHE_TTL = timedelta(seconds=15)

# currentMatches cache — richer data but heavier endpoint
_current_matches_cache: dict = {}  # id -> match data
_current_matches_cache_time: datetime = datetime.min.replace(tzinfo=timezone.utc)
_CURRENT_MATCHES_TTL = timedelta(seconds=30)

# Match window cache — avoids opening a DB session on every poll
_match_window_cache: bool = True
_match_window_cache_time: datetime = datetime.min.replace(tzinfo=timezone.utc)
_MATCH_WINDOW_TTL = timedelta(seconds=60)

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

# Cache cricapi_id → DB match_id to avoid a SELECT per snapshot persist
_cricapi_to_db_id: dict = {}


def init_tracker(api_key: str):
    """Initialize tracker with API key."""
    global CRICAPI_KEY
    CRICAPI_KEY = api_key
    logger.info("Live tracker initialized")


def _is_match_window() -> bool:
    """Check if any IPL match could be live right now.

    Cached for 60 seconds to avoid opening a DB session on every poll.
    """
    global _match_window_cache, _match_window_cache_time

    now = datetime.now(timezone.utc)
    if (now - _match_window_cache_time) < _MATCH_WINDOW_TTL:
        return _match_window_cache

    from app.database import SessionLocal
    from app.models.models import Match

    try:
        db = SessionLocal()
        try:
            matches = db.query(Match).filter(
                Match.season == CURRENT_SEASON,
                Match.match_ended == False,
                Match.datetime_gmt.isnot(None),
            ).all()
        finally:
            db.close()

        if not matches:
            _match_window_cache = True
            _match_window_cache_time = now
            return True

        result = False
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
                result = True
                break

        _match_window_cache = result
        _match_window_cache_time = now
        return result
    except Exception:
        return True  # on error, allow polling


async def _fetch_current_matches() -> dict:
    """Fetch from currentMatches endpoint — has actual scores and venue data.

    Returns a dict keyed by match ID for quick lookup.
    Cached for 30 seconds to limit API usage.
    """
    global _current_matches_cache, _current_matches_cache_time

    now = datetime.now(timezone.utc)
    if _current_matches_cache and (now - _current_matches_cache_time) < _CURRENT_MATCHES_TTL:
        return _current_matches_cache

    if not CRICAPI_KEY:
        return _current_matches_cache

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.cricapi.com/v1/currentMatches",
                params={"apikey": CRICAPI_KEY, "offset": 0},
            )
            data = resp.json()
            if data.get("status") != "success":
                return _current_matches_cache

            result = {}
            for m in data.get("data", []):
                name = m.get("name", "")
                if "indian premier" in name.lower() or "ipl" in name.lower():
                    result[m["id"]] = m

            _current_matches_cache = result
            _current_matches_cache_time = now
            return result
    except Exception as e:
        logger.error(f"Error fetching currentMatches: {e}")
        return _current_matches_cache


def _scores_from_current_match(cm: dict, team1_short: str, team2_short: str) -> tuple:
    """Extract team scores from currentMatches score array.

    The score array contains entries like:
      {"r": 39, "w": 1, "o": 4, "inning": "Chennai Super Kings Inning 1"}
    We match innings to teams by checking if the team short name appears
    in the full team name from the inning string.
    """
    scores = cm.get("score", [])
    t1_score = {"runs": 0, "wickets": 0, "overs": 0.0}
    t2_score = {"runs": 0, "wickets": 0, "overs": 0.0}

    # Build full name -> short name mapping from the currentMatches data
    cm_teams = cm.get("teamInfo", [])
    team_name_map = {}  # lowercase full name fragment -> short name
    for ti in cm_teams:
        sn = ti.get("shortname", "")
        name = ti.get("name", "")
        if sn and name:
            team_name_map[name.lower()] = sn

    for s in scores:
        inning = s.get("inning", "").lower()
        r = s.get("r", 0)
        w = s.get("w", 0)
        o = float(s.get("o", 0))
        score_dict = {"runs": r, "wickets": w, "overs": o}

        # Match inning to team
        matched = False
        for full_name, short in team_name_map.items():
            if full_name in inning:
                if short == team1_short:
                    t1_score = score_dict
                elif short == team2_short:
                    t2_score = score_dict
                matched = True
                break

        # Fallback: check if team short name appears in inning text
        if not matched:
            if team1_short.lower() in inning:
                t1_score = score_dict
            elif team2_short.lower() in inning:
                t2_score = score_dict

    return t1_score, t2_score


async def fetch_live_scores() -> list:
    """Fetch all live IPL scores from cricScore + currentMatches endpoints.

    cricScore is lightweight (1 call for all matches) but often returns
    empty scores. currentMatches has actual ball-by-ball scores and venue
    data. We use cricScore for match listing and enrich with currentMatches.
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
                return _score_cache

            ipl_matches = []
            has_live = False
            for m in data.get("data", []):
                if "indian premier" in m.get("series", "").lower():
                    match_data = {
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
                        "venue": None,
                    }
                    if m.get("ms") == "live":
                        has_live = True
                    ipl_matches.append(match_data)

            # Enrich with currentMatches data (has actual scores + venue)
            if has_live:
                cm_data = await _fetch_current_matches()
                for match in ipl_matches:
                    cm = cm_data.get(match["id"])
                    if not cm:
                        continue

                    # Always grab venue from currentMatches
                    match["venue"] = cm.get("venue")

                    # Update scores from currentMatches if cricScore had empty ones
                    if match["match_state"] in ("live", "result"):
                        t1s, t2s = _scores_from_current_match(
                            cm, match["team1"], match["team2"],
                        )
                        # Use currentMatches scores if they have actual data
                        if t1s["runs"] > 0 or t1s["wickets"] > 0 or t1s["overs"] > 0:
                            match["team1_score"] = t1s
                        if t2s["runs"] > 0 or t2s["wickets"] > 0 or t2s["overs"] > 0:
                            match["team2_score"] = t2s

            _score_cache = ipl_matches
            _score_cache_time = now
            return ipl_matches
    except Exception as e:
        logger.error(f"Error fetching live scores: {e}")
        return _score_cache


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
    """Extract venue city from match data.

    Checks (in order):
    1. venue field (from currentMatches enrichment, e.g. "MA Chidambaram Stadium, Chennai")
    2. status text (e.g. "... at Chennai")
    """
    # Check venue string first (most reliable — from currentMatches)
    venue = match.get("venue") or ""
    for city in VENUE_COORDS:
        if city.lower() in venue.lower():
            return city

    # Fallback: check status text
    status = match.get("status", "")
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
    """Record a score snapshot in-memory and persist to DB for post-match analysis.

    In-memory deque is used for quick access during live matches.
    DB persistence (LiveSnapshot) enables post-match win probability replay.
    """
    now = datetime.now(timezone.utc)

    # In-memory cache for live access
    if match_id not in _match_history:
        _match_history[match_id] = deque(maxlen=60)
    _match_history[match_id].append({
        "timestamp": now.isoformat(),
        **state,
    })

    # Persist to database for post-match analysis
    _persist_snapshot_to_db(match_id, state, now)


def _persist_snapshot_to_db(match_id: str, state: dict, timestamp: datetime):
    """Save snapshot to LiveSnapshot table for post-match win prob curves.

    Uses _cricapi_to_db_id cache to avoid a SELECT on every snapshot.
    """
    try:
        from app.database import SessionLocal
        from app.models.models import LiveSnapshot, Match

        # Resolve DB match_id, using cache to avoid repeated SELECTs
        db_match_id = _cricapi_to_db_id.get(match_id)

        db = SessionLocal()
        try:
            if not db_match_id:
                db_match = db.query(Match).filter(Match.cricapi_id == match_id).first()
                if not db_match:
                    return
                db_match_id = db_match.id
                _cricapi_to_db_id[match_id] = db_match_id

            innings = state.get("innings")
            score = state.get("current_score", {})
            win_prob = state.get("win_probability", {})
            batting_team = state.get("batting_team")
            bowling_team = state.get("bowling_team")

            if innings is None:
                return

            snapshot = LiveSnapshot(
                match_id=db_match_id,
                cricapi_match_id=match_id,
                timestamp=timestamp,
                innings=innings,
                batting_team=batting_team,
                bowling_team=bowling_team,
                runs=score.get("runs", 0),
                wickets=score.get("wickets", 0),
                overs=score.get("overs", 0.0),
                target=state.get("target"),
                win_prob_batting=win_prob.get(batting_team),
                win_prob_bowling=win_prob.get(bowling_team),
            )
            db.add(snapshot)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.debug(f"Snapshot persist failed: {e}")
        finally:
            db.close()
    except Exception:
        pass  # Don't let persistence failures break live tracking


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


async def build_scores_payload() -> dict:
    """Build the full live scores payload used by both REST and WebSocket.

    Returns a dict with live, upcoming, recent_results, and fetched_at fields.
    Shared between GET /live/scores and the WS manager's poll loop to
    avoid duplicating the match-categorization logic.
    """
    matches = await fetch_live_scores()

    live_states = []
    upcoming = []
    results = []

    for m in matches:
        if m["match_state"] == "live":
            state = await build_live_match_state(m)
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
