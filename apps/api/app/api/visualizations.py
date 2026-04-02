"""Visualization data API routes — partnerships, run distribution, wicket types."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db
from app.models.models import Match, Delivery, Player, Team, PlayerSeasonBatting
from app.services.stats import get_player_batting_stats, get_player_bowling_stats
from app.services.form import calculate_form_index

router = APIRouter(prefix="/viz", tags=["visualizations"])


@router.get("/partnerships/{match_id}")
def get_partnerships(
    match_id: int,
    innings: int = Query(1, ge=1, le=2),
    db: Session = Depends(get_db),
):
    """Get batting partnerships for a match innings."""
    match = db.query(Match).get(match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    deliveries = (
        db.query(Delivery)
        .filter(Delivery.match_id == match_id, Delivery.innings == innings)
        .order_by(Delivery.over_num, Delivery.ball_num)
        .all()
    )

    if not deliveries:
        return {"match_id": match_id, "innings": innings, "partnerships": []}

    # Batch-load all players referenced in this innings
    player_ids = {d.batter_id for d in deliveries} | {d.non_striker_id for d in deliveries}
    player_map = {p.id: p.name for p in db.query(Player).filter(Player.id.in_(player_ids)).all()}

    partnerships = []
    current_pair = None
    current_runs = 0
    current_balls = 0

    for d in deliveries:
        pair = tuple(sorted([d.batter_id, d.non_striker_id]))
        if pair != current_pair:
            if current_pair is not None:
                partnerships.append({
                    "batter1": {"id": current_pair[0], "name": player_map.get(current_pair[0], "Unknown")},
                    "batter2": {"id": current_pair[1], "name": player_map.get(current_pair[1], "Unknown")},
                    "runs": current_runs,
                    "balls": current_balls,
                })
            current_pair = pair
            current_runs = 0
            current_balls = 0
        current_runs += d.runs_total
        if d.valid_ball:
            current_balls += 1

    if current_pair is not None:
        partnerships.append({
            "batter1": {"id": current_pair[0], "name": player_map.get(current_pair[0], "Unknown")},
            "batter2": {"id": current_pair[1], "name": player_map.get(current_pair[1], "Unknown")},
            "runs": current_runs,
            "balls": current_balls,
        })

    return {"match_id": match_id, "innings": innings, "partnerships": partnerships}


@router.get("/run-distribution/{player_id}")
def get_run_distribution(
    player_id: int,
    season: str = Query(None),
    db: Session = Depends(get_db),
):
    """Get run scoring distribution for a batter — dots, 1s, 2s, 3s, 4s, 6s."""
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")

    q = db.query(
        Delivery.runs_batter,
        func.count().label("count"),
    ).filter(
        Delivery.batter_id == player_id,
        Delivery.valid_ball == True,
    )

    if season:
        q = q.join(Match, Match.id == Delivery.match_id).filter(Match.season == season)

    q = q.group_by(Delivery.runs_batter)
    rows = q.all()

    distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 6: 0}
    for runs_batter, count in rows:
        if runs_batter in distribution:
            distribution[runs_batter] += count
        elif runs_batter == 5:
            distribution[4] += count
        elif runs_batter >= 6:
            distribution[6] += count

    total = sum(distribution.values())
    zones = [
        {"label": "Dots", "value": distribution[0], "runs": 0, "pct": round(distribution[0] / total * 100, 1) if total else 0},
        {"label": "Singles", "value": distribution[1], "runs": 1, "pct": round(distribution[1] / total * 100, 1) if total else 0},
        {"label": "Doubles", "value": distribution[2], "runs": 2, "pct": round(distribution[2] / total * 100, 1) if total else 0},
        {"label": "Triples", "value": distribution[3], "runs": 3, "pct": round(distribution[3] / total * 100, 1) if total else 0},
        {"label": "Fours", "value": distribution[4], "runs": 4, "pct": round(distribution[4] / total * 100, 1) if total else 0},
        {"label": "Sixes", "value": distribution[6], "runs": 6, "pct": round(distribution[6] / total * 100, 1) if total else 0},
    ]

    return {
        "player_id": player_id,
        "player_name": player.name,
        "total_balls": total,
        "distribution": zones,
    }


@router.get("/wicket-types/{player_id}")
def get_wicket_types(
    player_id: int,
    mode: Literal["batter", "bowler"] = Query("batter"),
    season: str = Query(None),
    db: Session = Depends(get_db),
):
    """Get wicket/dismissal type breakdown for a player."""
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")

    filter_col = Delivery.bowler_id if mode == "bowler" else Delivery.player_out_id
    q = db.query(
        Delivery.wicket_kind,
        func.count().label("count"),
    ).filter(
        filter_col == player_id,
        Delivery.wicket_kind.isnot(None),
        Delivery.wicket_kind != "",
    )

    if season:
        q = q.join(Match, Match.id == Delivery.match_id).filter(Match.season == season)

    q = q.group_by(Delivery.wicket_kind)
    rows = q.all()

    total = sum(count for _, count in rows)
    types = [
        {
            "type": kind,
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
        }
        for kind, count in sorted(rows, key=lambda x: -x[1])
    ]

    return {
        "player_id": player_id,
        "player_name": player.name,
        "mode": mode,
        "total": total,
        "wicket_types": types,
    }


def _build_player_compare_stats(db: Session, player: Player) -> dict:
    """Build comprehensive stats for a player comparison."""
    player_id = player.id
    bat = get_player_batting_stats(db, player_id)
    bowl = get_player_bowling_stats(db, player_id)

    total_runs = sum(s["runs"] for s in bat)
    total_balls = sum(s["balls_faced"] for s in bat)
    total_innings = sum(s["innings"] for s in bat)
    total_matches = sum(s["matches"] for s in bat)
    total_fours = sum(s["fours"] for s in bat)
    total_sixes = sum(s["sixes"] for s in bat)
    total_fifties = sum(s["fifties"] for s in bat)
    total_hundreds = sum(s["hundreds"] for s in bat)
    total_not_outs = sum(s["not_outs"] for s in bat)
    highest = max((s["highest_score"] for s in bat), default=0)

    total_wickets = sum(s["wickets"] for s in bowl)
    total_bowl_innings = sum(s["innings"] for s in bowl)
    total_overs = sum(s["overs_bowled"] for s in bowl)
    total_runs_conceded = sum(s["runs_conceded"] for s in bowl)
    total_4w = sum(s["four_wickets"] for s in bowl)
    total_5w = sum(s["five_wickets"] for s in bowl)

    teams = (
        db.query(Team.name, Team.short_name)
        .join(PlayerSeasonBatting, PlayerSeasonBatting.team_id == Team.id)
        .filter(PlayerSeasonBatting.player_id == player_id)
        .distinct()
        .all()
    )

    form = calculate_form_index(db, player_id, "batter")

    return {
        "id": player.id,
        "name": player.name,
        "role": player.role,
        "batting_style": player.batting_style,
        "bowling_style": player.bowling_style,
        "teams": [{"name": t[0], "short_name": t[1]} for t in teams],
        "batting": {
            "matches": total_matches,
            "innings": total_innings,
            "runs": total_runs,
            "balls_faced": total_balls,
            "strike_rate": round(total_runs / total_balls * 100, 2) if total_balls > 0 else 0,
            "average": round(total_runs / (total_innings - total_not_outs), 2) if (total_innings - total_not_outs) > 0 else 0,
            "fours": total_fours,
            "sixes": total_sixes,
            "fifties": total_fifties,
            "hundreds": total_hundreds,
            "highest_score": highest,
        },
        "bowling": {
            "innings": total_bowl_innings,
            "wickets": total_wickets,
            "overs": total_overs,
            "runs_conceded": total_runs_conceded,
            "economy": round(total_runs_conceded / total_overs, 2) if total_overs > 0 else 0,
            "average": round(total_runs_conceded / total_wickets, 2) if total_wickets > 0 else 0,
            "four_wickets": total_4w,
            "five_wickets": total_5w,
        },
        "form_index": form.get("form_index", 0) if isinstance(form, dict) else 0,
        "form_trend": form.get("trend", "stable") if isinstance(form, dict) else "stable",
    }


@router.get("/player-compare")
def compare_players(
    player1: int = Query(..., description="Player 1 ID"),
    player2: int = Query(..., description="Player 2 ID"),
    db: Session = Depends(get_db),
):
    """Compare two players side-by-side with career stats."""
    p1 = db.query(Player).get(player1)
    p2 = db.query(Player).get(player2)
    if not p1:
        raise HTTPException(404, f"Player {player1} not found")
    if not p2:
        raise HTTPException(404, f"Player {player2} not found")

    return {
        "player1": _build_player_compare_stats(db, p1),
        "player2": _build_player_compare_stats(db, p2),
    }
