"""
Post-match analysis service — win probability curves and turning point detection.

Two modes:
  1. Historical matches (2008-2025): ball-by-ball replay through XGBoost model
  2. IPL 2026 matches: reconstruct from persisted LiveSnapshot records

Turning points are overs where win probability swings by >= TURNING_POINT_THRESHOLD.
"""

import logging
from typing import List, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Match, Delivery, Team, Player, LiveSnapshot, VenueStats
from app.services.cricapi_utils import resolve_batting_order
from app.services.live_tracker import predict_live_win_probability

logger = logging.getLogger("post_match")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TURNING_POINT_THRESHOLD = 10.0    # Minimum win-prob swing (%) to flag as turning point
SIGNIFICANT_WICKET_RUNS = 25      # Batter scored this many runs = "key dismissal"
BIG_OVER_RUNS = 15                # Runs in a single over to flag as "big over"


# ---------------------------------------------------------------------------
# Thin wrappers over the shared win-probability predictor in live_tracker
# ---------------------------------------------------------------------------

def _predict_1st_innings(
    runs: int, wickets: int, over: int,
    venue_avg: float = 165.0,
) -> float:
    """Batting-first team's win probability (0-100) via the shared XGBoost model."""
    result = predict_live_win_probability(
        innings=1, runs=runs, wickets=wickets, overs=float(over), venue_avg=venue_avg,
    )
    return result["batting_team_win_prob"]


def _predict_2nd_innings(
    runs: int, wickets: int, over: int, target: int,
) -> float:
    """Chasing team's win probability (0-100) via the shared XGBoost model."""
    result = predict_live_win_probability(
        innings=2, runs=runs, wickets=wickets, overs=float(over), target=target,
    )
    return result["batting_team_win_prob"]


# ---------------------------------------------------------------------------
# Turning point classification
# ---------------------------------------------------------------------------

def _classify_turning_point(
    prev_over_data: dict,
    curr_over_data: dict,
    swing: float,
) -> dict:
    """Classify what caused a turning point based on over-by-over deltas.

    Returns a dict with:
      - type: "big_over" | "wicket_cluster" | "key_dismissal" | "collapse" | "momentum_shift"
      - description: human-readable summary
    """
    runs_in_over = curr_over_data.get("runs_in_over", 0)
    wickets_in_over = curr_over_data.get("wickets_in_over", 0)
    key_wicket = curr_over_data.get("key_wicket", None)

    if wickets_in_over >= 2:
        return {
            "type": "wicket_cluster",
            "description": f"{wickets_in_over} wickets fell in this over",
        }
    elif key_wicket and key_wicket.get("runs", 0) >= SIGNIFICANT_WICKET_RUNS:
        return {
            "type": "key_dismissal",
            "description": f"Key wicket: {key_wicket['name']} ({key_wicket['runs']})",
        }
    elif runs_in_over >= BIG_OVER_RUNS:
        return {
            "type": "big_over",
            "description": f"{runs_in_over} runs scored in the over",
        }
    elif swing > 0:
        return {
            "type": "momentum_shift",
            "description": "Momentum shifted towards batting team",
        }
    else:
        return {
            "type": "momentum_shift",
            "description": "Momentum shifted towards bowling team",
        }


# ---------------------------------------------------------------------------
# Historical match analysis (ball-by-ball)
# ---------------------------------------------------------------------------

def analyze_historical_match(db: Session, match_id: int) -> Optional[dict]:
    """Analyze a completed match using ball-by-ball delivery data.

    Replays every over through the XGBoost model to build the win probability
    curve, then identifies turning points where probability swings significantly.
    """
    match = db.get(Match, match_id)
    if not match or not match.winner_id:
        return None

    # Get venue average score for 1st innings model
    venue_avg = 165.0
    if match.venue_id:
        vs = db.query(VenueStats).filter(VenueStats.venue_id == match.venue_id).first()
        if vs and vs.avg_first_innings_score:
            venue_avg = vs.avg_first_innings_score

    # Load all referenced teams in one query
    team_ids = {match.team1_id, match.team2_id, match.winner_id}
    teams = {t.id: t for t in db.query(Team).filter(Team.id.in_(team_ids)).all()}
    team1 = teams.get(match.team1_id)
    team2 = teams.get(match.team2_id)
    winner = teams.get(match.winner_id)

    # Get all deliveries sorted by innings, over, ball
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.match_id == match_id)
        .order_by(Delivery.innings, Delivery.over_num, Delivery.ball_num)
        .all()
    )

    if not deliveries:
        return None

    bat_first_id, bat_second_id = resolve_batting_order(
        match.toss_winner_id, match.toss_decision, match.team1_id, match.team2_id,
    )

    bat_first = db.get(Team, bat_first_id)
    bat_second = db.get(Team, bat_second_id)

    # Pre-load all dismissed player names in one query to avoid N+1
    dismissed_ids = {d.player_out_id for d in deliveries if d.player_out_id}
    player_map: Dict[int, str] = {}
    if dismissed_ids:
        for p in db.query(Player).filter(Player.id.in_(dismissed_ids)).all():
            player_map[p.id] = p.name

    # Build over-by-over data for each innings
    curve_points: List[dict] = []  # The full win probability curve
    turning_points: List[dict] = []

    # Track per-over stats
    first_innings_total = 0

    for innings_num in [1, 2]:
        inn_deliveries = [d for d in deliveries if d.innings == innings_num]
        if not inn_deliveries:
            continue

        prev_prob = 50.0
        current_over = -1
        over_runs = 0
        over_wickets = 0
        over_key_wicket = None
        prev_delivery = None
        batter_runs: Dict[int, int] = {}  # track batter contributions

        for d in inn_deliveries:
            # Track individual batter runs for key wicket detection
            if d.batter_id:
                batter_runs[d.batter_id] = batter_runs.get(d.batter_id, 0) + (d.runs_batter or 0)

            # Process on over change
            if d.over_num != current_over:
                if current_over >= 0:
                    # Use previous delivery's cumulative state
                    ref_d = prev_delivery if prev_delivery else d
                    cum_runs = ref_d.team_runs or 0
                    cum_wickets = ref_d.team_wickets or 0

                    if innings_num == 1:
                        prob = _predict_1st_innings(cum_runs, cum_wickets, current_over + 1, venue_avg)
                        # prob is batting-first win prob
                    else:
                        target = first_innings_total + 1
                        prob = _predict_2nd_innings(cum_runs, cum_wickets, current_over + 1, target)
                        # prob is chasing team's win prob → invert to get bat-first team's prob
                        prob = 100 - prob

                    point = {
                        "innings": innings_num,
                        "over": current_over + 1,
                        "runs": cum_runs,
                        "wickets": cum_wickets,
                        "bat_first_win_prob": round(prob, 1),
                        "bat_second_win_prob": round(100 - prob, 1),
                        "runs_in_over": over_runs,
                        "wickets_in_over": over_wickets,
                    }
                    curve_points.append(point)

                    # Detect turning point
                    swing = prob - prev_prob
                    if abs(swing) >= TURNING_POINT_THRESHOLD:
                        over_data = {
                            "runs_in_over": over_runs,
                            "wickets_in_over": over_wickets,
                            "key_wicket": over_key_wicket,
                        }
                        classification = _classify_turning_point({}, over_data, swing)
                        turning_points.append({
                            **point,
                            "swing": round(swing, 1),
                            "favours": bat_first.short_name if swing > 0 else bat_second.short_name,
                            **classification,
                        })

                    prev_prob = prob

                # Reset for new over
                current_over = d.over_num
                over_runs = 0
                over_wickets = 0
                over_key_wicket = None

            over_runs += d.runs_total or 0
            if d.wicket_kind:
                over_wickets += 1
                # Check if this is a key wicket (set batter with 25+ runs dismissed)
                if d.player_out_id and batter_runs.get(d.player_out_id, 0) >= SIGNIFICANT_WICKET_RUNS:
                    over_key_wicket = {
                        "name": player_map.get(d.player_out_id, "Unknown"),
                        "runs": batter_runs.get(d.player_out_id, 0),
                    }
            prev_delivery = d

        # Process final over of this innings
        if current_over >= 0 and inn_deliveries:
            last_d = inn_deliveries[-1]
            cum_runs = last_d.team_runs or 0
            cum_wickets = last_d.team_wickets or 0

            if innings_num == 1:
                prob = _predict_1st_innings(cum_runs, cum_wickets, current_over + 1, venue_avg)
                first_innings_total = cum_runs
            else:
                target = first_innings_total + 1
                prob = _predict_2nd_innings(cum_runs, cum_wickets, current_over + 1, target)
                prob = 100 - prob

            point = {
                "innings": innings_num,
                "over": current_over + 1,
                "runs": cum_runs,
                "wickets": cum_wickets,
                "bat_first_win_prob": round(prob, 1),
                "bat_second_win_prob": round(100 - prob, 1),
                "runs_in_over": over_runs,
                "wickets_in_over": over_wickets,
            }
            curve_points.append(point)

            swing = prob - prev_prob
            if abs(swing) >= TURNING_POINT_THRESHOLD:
                over_data = {
                    "runs_in_over": over_runs,
                    "wickets_in_over": over_wickets,
                    "key_wicket": over_key_wicket,
                }
                classification = _classify_turning_point({}, over_data, swing)
                turning_points.append({
                    **point,
                    "swing": round(swing, 1),
                    "favours": bat_first.short_name if swing > 0 else bat_second.short_name,
                    **classification,
                })

    # Sort turning points by magnitude of swing
    turning_points.sort(key=lambda t: abs(t["swing"]), reverse=True)

    return {
        "match_id": match_id,
        "season": match.season,
        "date": str(match.date) if match.date else None,
        "bat_first": {"id": bat_first.id, "name": bat_first.name, "short_name": bat_first.short_name},
        "bat_second": {"id": bat_second.id, "name": bat_second.name, "short_name": bat_second.short_name},
        "winner": {"id": winner.id, "name": winner.name, "short_name": winner.short_name},
        "result": match.status_text or f"{winner.name} won by {match.win_margin} {match.win_type}",
        "first_innings_score": first_innings_total,
        "curve": curve_points,
        "turning_points": turning_points,
        "total_overs": len(curve_points),
        "data_source": "ball_by_ball",
    }


# ---------------------------------------------------------------------------
# IPL 2026 match analysis (from LiveSnapshot records)
# ---------------------------------------------------------------------------

def analyze_2026_match(db: Session, match_id: int) -> Optional[dict]:
    """Analyze an IPL 2026 match using persisted LiveSnapshot records.

    Provides over-by-over granularity (from polling) rather than ball-by-ball,
    but still shows the win probability curve and turning points.
    """
    match = db.get(Match, match_id)
    if not match or not match.winner_id:
        return None

    snapshots = (
        db.query(LiveSnapshot)
        .filter(LiveSnapshot.match_id == match_id)
        .order_by(LiveSnapshot.timestamp)
        .all()
    )

    if not snapshots:
        return None

    # Load teams in one query and resolve batting order from toss
    team_ids = {match.team1_id, match.team2_id, match.winner_id}
    teams = {t.id: t for t in db.query(Team).filter(Team.id.in_(team_ids)).all()}
    bat_first_id, bat_second_id = resolve_batting_order(
        match.toss_winner_id, match.toss_decision, match.team1_id, match.team2_id,
    )
    team1 = teams.get(bat_first_id)
    team2 = teams.get(bat_second_id)
    winner = teams.get(match.winner_id)

    curve_points = []
    turning_points = []
    prev_prob = 50.0

    for snap in snapshots:
        prob = snap.win_prob_batting if snap.win_prob_batting is not None else 50.0
        # Normalize to bat-first team's perspective
        if snap.innings == 2:
            prob = 100 - prob  # Invert chasing team's prob

        point = {
            "innings": snap.innings,
            "over": snap.overs,
            "runs": snap.runs,
            "wickets": snap.wickets,
            "bat_first_win_prob": round(prob, 1),
            "bat_second_win_prob": round(100 - prob, 1),
            "timestamp": snap.timestamp.isoformat() if snap.timestamp else None,
        }
        curve_points.append(point)

        # Detect turning points
        swing = prob - prev_prob
        if abs(swing) >= TURNING_POINT_THRESHOLD:
            turning_points.append({
                **point,
                "swing": round(swing, 1),
                "favours": snap.batting_team if swing > 0 else snap.bowling_team,
                "type": "momentum_shift",
                "description": f"Win probability shifted by {abs(swing):.1f}%",
            })
        prev_prob = prob

    turning_points.sort(key=lambda t: abs(t["swing"]), reverse=True)

    return {
        "match_id": match_id,
        "season": match.season,
        "date": str(match.date) if match.date else None,
        "bat_first": {"id": team1.id, "name": team1.name, "short_name": team1.short_name},
        "bat_second": {"id": team2.id, "name": team2.name, "short_name": team2.short_name},
        "winner": {"id": winner.id, "name": winner.name, "short_name": winner.short_name},
        "result": match.status_text or f"{winner.name} won",
        "first_innings_score": match.first_innings_score,
        "curve": curve_points,
        "turning_points": turning_points,
        "total_overs": len(curve_points),
        "data_source": "live_snapshots",
    }


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def analyze_match(db: Session, match_id: int) -> Optional[dict]:
    """Analyze any completed match — automatically selects data source.

    Historical matches (with ball-by-ball data) get full delivery-level analysis.
    IPL 2026 matches use LiveSnapshot records for over-by-over analysis.
    """
    match = db.get(Match, match_id)
    if not match:
        return None

    # Check if ball-by-ball data exists
    delivery_count = db.query(func.count(Delivery.id)).filter(
        Delivery.match_id == match_id
    ).scalar()

    if delivery_count:
        return analyze_historical_match(db, match_id)

    return analyze_2026_match(db, match_id)
