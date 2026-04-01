"""Season and standings API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.deps import get_db
from app.models.models import Match, Team, Delivery
from typing import Dict

router = APIRouter(prefix="/seasons", tags=["seasons"])


def _cricket_overs_to_decimal(overs: float) -> float:
    """Convert cricket overs notation to decimal.
    19.4 means 19 overs and 4 balls = 19 + 4/6 = 19.667 overs.
    """
    whole = int(overs)
    balls = round((overs - whole) * 10)  # .4 -> 4 balls
    return whole + balls / 6.0


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


def _compute_innings_from_deliveries(db: Session, match_id: int):
    """Compute per-innings runs and overs from ball-by-ball deliveries.
    Returns list of dicts: [{team_id, runs, overs, wickets}, ...]
    """
    # Get runs, valid balls, and wickets per innings
    innings_data = (
        db.query(
            Delivery.innings,
            func.max(Delivery.team_runs).label("runs"),
            func.sum(
                func.cast(Delivery.valid_ball == True, db.bind.dialect.type_descriptor(type(1)) if hasattr(db.bind, 'dialect') else None) if False else
                Delivery.valid_ball
            ).label("balls"),
            func.max(Delivery.team_wickets).label("wickets"),
        )
        .filter(Delivery.match_id == match_id)
        .group_by(Delivery.innings)
        .order_by(Delivery.innings)
        .all()
    )
    return innings_data


def _get_innings_totals(db: Session, match_id: int):
    """Get (runs, overs) for each innings from deliveries table.

    Returns: [(inn1_runs, inn1_overs), (inn2_runs, inn2_overs)] or None
    NRR uses overs = balls/6 for the team that batted.
    If a team is all out or completes 20 overs, overs = 20.
    If a team chases successfully, overs = actual balls faced / 6.
    """
    # Count valid balls and max team_runs per innings
    results = []
    for inn in [1, 2]:
        row = db.query(
            func.max(Delivery.team_runs).label("runs"),
            func.count(Delivery.id).label("total_deliveries"),
        ).filter(
            Delivery.match_id == match_id,
            Delivery.innings == inn,
            Delivery.valid_ball == True,
        ).first()

        if not row or row.runs is None:
            return None

        runs = row.runs
        balls = row.total_deliveries
        overs = balls / 6.0
        results.append((runs, overs))

    return results if len(results) == 2 else None


@router.get("/{season}/standings")
def get_standings(season: str, db: Session = Depends(get_db)):
    """Get points table / standings for a season with proper NRR."""
    matches = db.query(Match).filter(Match.season == season).all()
    if not matches:
        raise HTTPException(status_code=404, detail=f"No matches found for season '{season}'")

    # Initialize standings for all teams in this season
    standings: Dict[int, dict] = {}

    for m in matches:
        for tid in [m.team1_id, m.team2_id]:
            if tid and tid not in standings:
                team = db.query(Team).get(tid)
                standings[tid] = {
                    "team_id": tid,
                    "team_name": team.name if team else "Unknown",
                    "short_name": team.short_name if team else "?",
                    "played": 0,
                    "won": 0,
                    "lost": 0,
                    "no_result": 0,
                    "points": 0,
                    "nrr": 0.0,
                    "for_runs": 0,
                    "for_overs": 0.0,
                    "against_runs": 0,
                    "against_overs": 0.0,
                }

    for m in matches:
        if not m.team1_id or not m.team2_id:
            continue

        # Skip unplayed matches
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

        # NRR calculation
        # Try deliveries first (most accurate — gives actual balls faced)
        innings = _get_innings_totals(db, m.id)

        if innings:
            inn1_runs, inn1_overs = innings[0]
            inn2_runs, inn2_overs = innings[1]

            # team1 batted first (innings 1), team2 batted second (innings 2)
            # Team1: scored inn1_runs in inn1_overs, conceded inn2_runs in inn2_overs
            standings[m.team1_id]["for_runs"] += inn1_runs
            standings[m.team1_id]["for_overs"] += inn1_overs
            standings[m.team1_id]["against_runs"] += inn2_runs
            standings[m.team1_id]["against_overs"] += inn2_overs

            # Team2: scored inn2_runs in inn2_overs, conceded inn1_runs in inn1_overs
            standings[m.team2_id]["for_runs"] += inn2_runs
            standings[m.team2_id]["for_overs"] += inn2_overs
            standings[m.team2_id]["against_runs"] += inn1_runs
            standings[m.team2_id]["against_overs"] += inn1_overs

        elif m.first_innings_score and m.second_innings_score:
            # Use stored scores — use actual overs if available
            inn1_runs = m.first_innings_score
            inn2_runs = m.second_innings_score
            # Overs stored as cricket format (19.4 = 19 overs 4 balls)
            # Convert to decimal overs for NRR: 19.4 -> 19 + 4/6 = 19.667
            raw1 = getattr(m, 'first_innings_overs', None)
            raw2 = getattr(m, 'second_innings_overs', None)
            inn1_overs = _cricket_overs_to_decimal(raw1) if raw1 else 20.0
            inn2_overs = _cricket_overs_to_decimal(raw2) if raw2 else 20.0

            if inn2_overs == 20.0 and m.win_type == "wickets" and m.win_margin:
                inn2_overs = max(10.0, 20.0 - m.win_margin * 0.5)

            # Determine batting-first team from toss
            if m.toss_winner_id and m.toss_decision:
                if m.toss_decision == "bat":
                    bat_first_id = m.toss_winner_id
                    bat_second_id = m.team2_id if m.toss_winner_id == m.team1_id else m.team1_id
                else:  # chose to bowl/field
                    bat_second_id = m.toss_winner_id
                    bat_first_id = m.team2_id if m.toss_winner_id == m.team1_id else m.team1_id
            else:
                bat_first_id = m.team1_id
                bat_second_id = m.team2_id

            standings[bat_first_id]["for_runs"] += inn1_runs
            standings[bat_first_id]["for_overs"] += inn1_overs
            standings[bat_first_id]["against_runs"] += inn2_runs
            standings[bat_first_id]["against_overs"] += inn2_overs

            standings[bat_second_id]["for_runs"] += inn2_runs
            standings[bat_second_id]["for_overs"] += inn2_overs
            standings[bat_second_id]["against_runs"] += inn1_runs
            standings[bat_second_id]["against_overs"] += inn1_overs

        elif m.winner_id and m.win_margin and m.win_type:
            # Minimal fallback for 2026 matches: estimate from result string
            # "Won by X runs" → batting first team scored more, assume ~165 avg
            # "Won by X wickets" → chasing team won
            avg_score = 165
            if m.win_type == "runs":
                inn1_runs = avg_score + m.win_margin // 2
                inn2_runs = avg_score - m.win_margin // 2
                inn1_overs = 20.0
                inn2_overs = 20.0
            else:  # wickets
                inn1_runs = avg_score
                inn2_runs = avg_score + 1  # chased successfully
                inn1_overs = 20.0
                inn2_overs = max(10.0, 20.0 - m.win_margin * 0.5)

            # Determine who batted first — if we have toss data use it
            if m.toss_winner_id and m.toss_decision:
                if m.toss_decision == "bat":
                    bat_first_id = m.toss_winner_id
                    bat_second_id = m.team2_id if m.toss_winner_id == m.team1_id else m.team1_id
                else:
                    bat_second_id = m.toss_winner_id
                    bat_first_id = m.team2_id if m.toss_winner_id == m.team1_id else m.team1_id
            else:
                bat_first_id = m.team1_id
                bat_second_id = m.team2_id

            standings[bat_first_id]["for_runs"] += inn1_runs
            standings[bat_first_id]["for_overs"] += inn1_overs
            standings[bat_first_id]["against_runs"] += inn2_runs
            standings[bat_first_id]["against_overs"] += inn2_overs

            standings[bat_second_id]["for_runs"] += inn2_runs
            standings[bat_second_id]["for_overs"] += inn2_overs
            standings[bat_second_id]["against_runs"] += inn1_runs
            standings[bat_second_id]["against_overs"] += inn1_overs

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
