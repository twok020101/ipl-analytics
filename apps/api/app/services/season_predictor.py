"""
Season prediction engine — Monte Carlo simulation for IPL playoff qualification.

Simulates remaining matches N times using team-strength ratings derived from:
  - Current win percentage (most weight)
  - Net run rate (momentum indicator)
  - Recent form (last 5 matches)
  - Historical head-to-head record

Each simulation produces a final standings table. Across all simulations we
track how often each team finishes in the top 4 (playoff qualification).
"""

import random
import time
from typing import Dict, List, Tuple, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.models import Match, Team
from app.config import CURRENT_SEASON
from app.services.cricapi_utils import cricket_overs_to_decimal, resolve_batting_order

# ---------------------------------------------------------------------------
# Result cache — avoid re-running 10K simulations on every request.
# Invalidated when completed match count changes (i.e., after a match ends).
# ---------------------------------------------------------------------------

_cache: Dict[str, dict] = {}  # key: "{season}:{n_completed}" → result
_cache_time: Dict[str, float] = {}
CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_SIMULATIONS = 10_000          # Higher = more stable probabilities
PLAYOFF_SPOTS = 4                 # Top-4 qualify in IPL
HOME_ADVANTAGE = 0.03             # Slight boost for team1 (listed first = "home")
MIN_STRENGTH = 0.15               # Floor so weak teams still have upset potential
MAX_STRENGTH = 0.85               # Cap so strong teams aren't invincible
FORM_WINDOW = 5                   # Last N completed matches for form calculation


def _team_strength(
    wins: int,
    played: int,
    nrr: float,
    form_wins: int,
    form_played: int,
) -> float:
    """Compute a [0, 1] strength rating for a team.

    Components (weighted):
      - Win rate (50%): raw wins / played
      - NRR factor (20%): normalized run-rate advantage
      - Form factor (30%): recent win rate (last 5 matches)

    Returns a clamped value between MIN_STRENGTH and MAX_STRENGTH.
    """
    # Win rate component
    win_rate = wins / max(played, 1)

    # NRR component — normalize to roughly [0, 1] range
    # IPL NRR typically ranges from -2.0 to +2.0
    nrr_norm = 0.5 + (nrr / 4.0)
    nrr_norm = max(0.0, min(1.0, nrr_norm))

    # Form component — recent wins out of recent matches
    form_rate = form_wins / max(form_played, 1) if form_played > 0 else win_rate

    # Weighted combination
    strength = (0.50 * win_rate) + (0.20 * nrr_norm) + (0.30 * form_rate)
    return max(MIN_STRENGTH, min(MAX_STRENGTH, strength))


def _match_win_probability(
    strength_a: float,
    strength_b: float,
    h2h_wins_a: int,
    h2h_total: int,
) -> float:
    """Calculate probability that team A beats team B.

    Uses Bradley-Terry model scaled by strength ratings, with a small
    H2H adjustment for teams with significant history.
    """
    # Base probability from strength ratio (Bradley-Terry)
    prob = strength_a / (strength_a + strength_b)

    # H2H adjustment — only if enough history (3+ matches)
    if h2h_total >= 3:
        h2h_rate = h2h_wins_a / h2h_total
        # Blend in H2H at 15% weight
        prob = 0.85 * prob + 0.15 * h2h_rate

    # Small home advantage for team listed first
    prob += HOME_ADVANTAGE

    return max(0.05, min(0.95, prob))


def predict_season(db: Session, season: str = CURRENT_SEASON) -> dict:
    """Run Monte Carlo simulation for IPL season playoff predictions.

    Returns:
        {
            "season": "2026",
            "simulations": 10000,
            "predictions": [
                {
                    "team_id": 1,
                    "team_name": "Chennai Super Kings",
                    "short_name": "CSK",
                    "current_played": 5,
                    "current_won": 3,
                    "current_points": 6,
                    "current_nrr": 0.452,
                    "playoff_pct": 72.3,
                    "avg_final_points": 14.2,
                    "avg_final_position": 3.1,
                    "top_2_pct": 41.5,
                    "winner_pct": 12.8,
                },
                ...
            ],
            "remaining_matches": 50,
        }
    """
    # -----------------------------------------------------------------------
    # 1. Load current standings data
    # -----------------------------------------------------------------------
    teams = db.query(Team).filter(Team.is_active == True).all()
    team_map = {t.id: t for t in teams}

    # Get all season matches
    all_matches = db.query(Match).filter(Match.season == season).all()

    # Separate completed vs remaining
    completed = [m for m in all_matches if m.winner_id is not None]
    remaining = [
        m for m in all_matches
        if m.winner_id is None and m.team1_id and m.team2_id
    ]

    if not remaining:
        return {"season": season, "simulations": 0, "predictions": [], "remaining_matches": 0}

    # Check cache — keyed by season + completed count (invalidates after each match)
    cache_key = f"{season}:{len(completed)}"
    now = time.time()
    if cache_key in _cache and (now - _cache_time.get(cache_key, 0)) < CACHE_TTL:
        return _cache[cache_key]

    # Build current standings
    standings: Dict[int, dict] = {}
    for t in teams:
        standings[t.id] = {
            "wins": 0, "losses": 0, "no_result": 0, "played": 0,
            "points": 0, "nrr": 0.0,
            "for_runs": 0, "for_overs": 0.0,
            "against_runs": 0, "against_overs": 0.0,
        }

    for m in completed:
        if m.team1_id not in standings or m.team2_id not in standings:
            continue
        standings[m.team1_id]["played"] += 1
        standings[m.team2_id]["played"] += 1
        if m.winner_id:
            loser_id = m.team2_id if m.winner_id == m.team1_id else m.team1_id
            standings[m.winner_id]["wins"] += 1
            standings[m.winner_id]["points"] += 2
            standings[loser_id]["losses"] += 1

        # NRR from stored scores
        if m.first_innings_score and m.second_innings_score:
            inn1_r = m.first_innings_score
            inn2_r = m.second_innings_score
            inn1_o = cricket_overs_to_decimal(m.first_innings_overs or 20.0)
            inn2_o = cricket_overs_to_decimal(m.second_innings_overs or 20.0)

            bat_first, bat_second = resolve_batting_order(
                m.toss_winner_id, m.toss_decision, m.team1_id, m.team2_id,
            )

            standings[bat_first]["for_runs"] += inn1_r
            standings[bat_first]["for_overs"] += inn1_o
            standings[bat_first]["against_runs"] += inn2_r
            standings[bat_first]["against_overs"] += inn2_o
            standings[bat_second]["for_runs"] += inn2_r
            standings[bat_second]["for_overs"] += inn2_o
            standings[bat_second]["against_runs"] += inn1_r
            standings[bat_second]["against_overs"] += inn1_o

    # Calculate NRR for each team
    for tid, s in standings.items():
        fr = s["for_runs"] / s["for_overs"] if s["for_overs"] > 0 else 0
        ar = s["against_runs"] / s["against_overs"] if s["against_overs"] > 0 else 0
        s["nrr"] = round(fr - ar, 3)

    # -----------------------------------------------------------------------
    # 2. Compute team strengths
    # -----------------------------------------------------------------------

    # Recent form: last FORM_WINDOW completed matches per team
    form_data: Dict[int, Tuple[int, int]] = {}  # team_id -> (wins, played)
    sorted_completed = sorted(completed, key=lambda m: m.date or "", reverse=True)
    for tid in standings:
        form_wins = 0
        form_played = 0
        for m in sorted_completed:
            if form_played >= FORM_WINDOW:
                break
            if m.team1_id == tid or m.team2_id == tid:
                form_played += 1
                if m.winner_id == tid:
                    form_wins += 1
        form_data[tid] = (form_wins, form_played)

    strengths: Dict[int, float] = {}
    for tid, s in standings.items():
        fw, fp = form_data.get(tid, (0, 0))
        strengths[tid] = _team_strength(s["wins"], s["played"], s["nrr"], fw, fp)

    # Head-to-head records
    h2h: Dict[Tuple[int, int], Tuple[int, int]] = {}  # (a, b) -> (a_wins, total)
    for m in completed:
        if not m.winner_id:
            continue
        a, b = min(m.team1_id, m.team2_id), max(m.team1_id, m.team2_id)
        key = (a, b)
        if key not in h2h:
            h2h[key] = [0, 0]
        h2h[key][1] += 1
        if m.winner_id == a:
            h2h[key][0] += 1

    # -----------------------------------------------------------------------
    # 3. Monte Carlo simulation
    # -----------------------------------------------------------------------

    # Track results across simulations
    qualify_count: Dict[int, int] = {tid: 0 for tid in standings}
    top2_count: Dict[int, int] = {tid: 0 for tid in standings}
    winner_count: Dict[int, int] = {tid: 0 for tid in standings}
    total_points: Dict[int, int] = {tid: 0 for tid in standings}
    total_position: Dict[int, int] = {tid: 0 for tid in standings}

    for _ in range(NUM_SIMULATIONS):
        # Copy current standings points
        sim_points = {tid: s["points"] for tid, s in standings.items()}
        sim_nrr = {tid: s["nrr"] for tid, s in standings.items()}

        # Simulate each remaining match
        for m in remaining:
            t1, t2 = m.team1_id, m.team2_id
            if t1 not in strengths or t2 not in strengths:
                continue

            # Get H2H data
            a, b = min(t1, t2), max(t1, t2)
            h2h_a_wins, h2h_total = h2h.get((a, b), (0, 0))
            # Flip if t1 is not the min
            if t1 == a:
                h_wins = h2h_a_wins
            else:
                h_wins = h2h_total - h2h_a_wins

            prob_t1 = _match_win_probability(strengths[t1], strengths[t2], h_wins, h2h_total)

            if random.random() < prob_t1:
                sim_points[t1] += 2
                # Small NRR bump for simulation variety
                sim_nrr[t1] += random.uniform(0.01, 0.15)
                sim_nrr[t2] -= random.uniform(0.01, 0.15)
            else:
                sim_points[t2] += 2
                sim_nrr[t2] += random.uniform(0.01, 0.15)
                sim_nrr[t1] -= random.uniform(0.01, 0.15)

        # Sort by points then NRR
        final = sorted(
            sim_points.keys(),
            key=lambda tid: (sim_points[tid], sim_nrr[tid]),
            reverse=True,
        )

        for pos, tid in enumerate(final):
            total_points[tid] += sim_points[tid]
            total_position[tid] += (pos + 1)
            if pos < PLAYOFF_SPOTS:
                qualify_count[tid] += 1
            if pos < 2:
                top2_count[tid] += 1
            if pos == 0:
                winner_count[tid] += 1

    # -----------------------------------------------------------------------
    # 4. Build response
    # -----------------------------------------------------------------------

    predictions = []
    for tid, s in standings.items():
        team = team_map.get(tid)
        if not team:
            continue
        predictions.append({
            "team_id": tid,
            "team_name": team.name,
            "short_name": team.short_name,
            "current_played": s["played"],
            "current_won": s["wins"],
            "current_lost": s["losses"],
            "current_points": s["points"],
            "current_nrr": s["nrr"],
            "strength_rating": round(strengths.get(tid, 0.5), 3),
            "playoff_pct": round(qualify_count[tid] / NUM_SIMULATIONS * 100, 1),
            "top_2_pct": round(top2_count[tid] / NUM_SIMULATIONS * 100, 1),
            "winner_pct": round(winner_count[tid] / NUM_SIMULATIONS * 100, 1),
            "avg_final_points": round(total_points[tid] / NUM_SIMULATIONS, 1),
            "avg_final_position": round(total_position[tid] / NUM_SIMULATIONS, 1),
        })

    # Sort by playoff probability descending
    predictions.sort(key=lambda x: x["playoff_pct"], reverse=True)

    result = {
        "season": season,
        "simulations": NUM_SIMULATIONS,
        "predictions": predictions,
        "remaining_matches": len(remaining),
        "completed_matches": len(completed),
    }

    # Cache result — invalidated when a new match completes
    _cache[cache_key] = result
    _cache_time[cache_key] = now

    return result
