"""Season and standings API routes, including playoff prediction."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.deps import get_db, require_viewer
from app.models.models import Match, Team, Delivery, User
from app.services.season_predictor import predict_season
from app.services.cricapi_utils import cricket_overs_to_decimal, resolve_batting_order
from typing import Dict

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("")
def list_seasons(db: Session = Depends(get_db)):
    """List all IPL seasons."""
    seasons = (
        db.query(
            Match.season,
            func.count(Match.id).label("matches"),
            func.min(Match.date).label("start_date"),
            func.max(Match.date).label("end_date"),
        )
        .group_by(Match.season)
        .order_by(Match.season)
        .all()
    )

    return [
        {
            "season": s.season,
            "matches": s.matches,
            "start_date": str(s.start_date) if s.start_date else None,
            "end_date": str(s.end_date) if s.end_date else None,
        }
        for s in seasons
    ]


def _apply_nrr(standings: dict, bat_first: int, bat_second: int,
               inn1_runs: float, inn1_overs: float, inn2_runs: float, inn2_overs: float):
    """Accumulate NRR runs/overs for both teams from a single match."""
    standings[bat_first]["for_runs"] += inn1_runs
    standings[bat_first]["for_overs"] += inn1_overs
    standings[bat_first]["against_runs"] += inn2_runs
    standings[bat_first]["against_overs"] += inn2_overs
    standings[bat_second]["for_runs"] += inn2_runs
    standings[bat_second]["for_overs"] += inn2_overs
    standings[bat_second]["against_runs"] += inn1_runs
    standings[bat_second]["against_overs"] += inn1_overs


@router.get("/{season}/standings")
def get_standings(season: str, db: Session = Depends(get_db)):
    """Get points table / standings for a season with proper NRR."""
    matches = db.query(Match).filter(Match.season == season).all()
    if not matches:
        raise HTTPException(status_code=404, detail=f"No matches found for season '{season}'")

    # Pre-load all teams in this season in one query (avoids N+1)
    all_team_ids = {tid for m in matches for tid in [m.team1_id, m.team2_id] if tid}
    team_cache = {t.id: t for t in db.query(Team).filter(Team.id.in_(all_team_ids)).all()}

    # Batch-fetch ball-by-ball innings data for all matches (avoids 2 queries per match)
    match_ids = [m.id for m in matches]
    innings_rows = (
        db.query(
            Delivery.match_id,
            Delivery.innings,
            func.max(Delivery.team_runs).label("runs"),
            func.count(Delivery.id).label("balls"),
        )
        .filter(Delivery.match_id.in_(match_ids), Delivery.valid_ball == True)
        .group_by(Delivery.match_id, Delivery.innings)
        .all()
    ) if match_ids else []
    # Build lookup: match_id → {innings_num: (runs, overs)}
    innings_by_match: Dict[int, Dict[int, tuple]] = {}
    for row in innings_rows:
        innings_by_match.setdefault(row.match_id, {})[row.innings] = (
            row.runs, row.balls / 6.0,
        )

    # Initialize standings
    standings: Dict[int, dict] = {}
    for tid in all_team_ids:
        team = team_cache.get(tid)
        standings[tid] = {
            "team_id": tid,
            "team_name": team.name if team else "Unknown",
            "short_name": team.short_name if team else "?",
            "played": 0, "won": 0, "lost": 0, "no_result": 0,
            "points": 0, "nrr": 0.0,
            "for_runs": 0, "for_overs": 0.0,
            "against_runs": 0, "against_overs": 0.0,
        }

    for m in matches:
        if not m.team1_id or not m.team2_id:
            continue
        if m.winner_id is None and m.first_innings_score is None:
            continue

        standings[m.team1_id]["played"] += 1
        standings[m.team2_id]["played"] += 1

        if m.winner_id:
            loser_id = m.team2_id if m.winner_id == m.team1_id else m.team1_id
            standings[m.winner_id]["won"] += 1
            standings[m.winner_id]["points"] += 2
            standings[loser_id]["lost"] += 1
        else:
            standings[m.team1_id]["no_result"] += 1
            standings[m.team1_id]["points"] += 1
            standings[m.team2_id]["no_result"] += 1
            standings[m.team2_id]["points"] += 1

        # NRR: try batch-loaded deliveries first, then stored scores, then estimate
        inn_data = innings_by_match.get(m.id, {})
        if 1 in inn_data and 2 in inn_data:
            inn1_runs, inn1_overs = inn_data[1]
            inn2_runs, inn2_overs = inn_data[2]
            _apply_nrr(standings, m.team1_id, m.team2_id, inn1_runs, inn1_overs, inn2_runs, inn2_overs)

        elif m.first_innings_score and m.second_innings_score:
            inn1_runs = m.first_innings_score
            inn2_runs = m.second_innings_score
            inn1_overs = cricket_overs_to_decimal(m.first_innings_overs) if m.first_innings_overs else 20.0
            inn2_overs = cricket_overs_to_decimal(m.second_innings_overs) if m.second_innings_overs else 20.0

            if inn2_overs == 20.0 and m.win_type == "wickets" and m.win_margin:
                inn2_overs = max(10.0, 20.0 - m.win_margin * 0.5)

            bf, bs = resolve_batting_order(m.toss_winner_id, m.toss_decision, m.team1_id, m.team2_id)
            _apply_nrr(standings, bf, bs, inn1_runs, inn1_overs, inn2_runs, inn2_overs)

        elif m.winner_id and m.win_margin and m.win_type:
            avg_score = 165
            if m.win_type == "runs":
                inn1_runs = avg_score + m.win_margin // 2
                inn2_runs = avg_score - m.win_margin // 2
                inn1_overs = inn2_overs = 20.0
            else:
                inn1_runs = avg_score
                inn2_runs = avg_score + 1
                inn1_overs = 20.0
                inn2_overs = max(10.0, 20.0 - m.win_margin * 0.5)

            bf, bs = resolve_batting_order(m.toss_winner_id, m.toss_decision, m.team1_id, m.team2_id)
            _apply_nrr(standings, bf, bs, inn1_runs, inn1_overs, inn2_runs, inn2_overs)

    # Calculate NRR: (runs scored / overs faced) - (runs conceded / overs bowled)
    for tid, s in standings.items():
        for_rr = s["for_runs"] / s["for_overs"] if s["for_overs"] > 0 else 0
        against_rr = s["against_runs"] / s["against_overs"] if s["against_overs"] > 0 else 0
        s["nrr"] = round(for_rr - against_rr, 3)

    # Sort by points desc, then NRR desc
    sorted_standings = sorted(
        standings.values(),
        key=lambda x: (x["points"], x["nrr"]),
        reverse=True,
    )

    for i, s in enumerate(sorted_standings):
        s["position"] = i + 1
        del s["for_runs"]
        del s["for_overs"]
        del s["against_runs"]
        del s["against_overs"]

    return {
        "season": season,
        "standings": sorted_standings,
    }


@router.get("/{season}/predictions")
def get_season_predictions(
    season: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_viewer),
):
    """Monte Carlo playoff qualification predictions for a season.

    Simulates remaining matches 10,000 times using team strength ratings
    (win rate, NRR, form, H2H) to estimate each team's probability of
    finishing in the top 4, top 2, or winning the title.
    """
    result = predict_season(db, season)
    if not result["predictions"]:
        raise HTTPException(status_code=404, detail=f"No data for season '{season}'")
    return result
