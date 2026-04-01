"""Dashboard stats endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.models import (
    Match,
    Player,
    Venue,
    PlayerSeasonBatting,
    PlayerSeasonBowling,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Return high-level dashboard statistics."""

    total_matches = db.query(func.count(Match.id)).scalar() or 0
    total_players = db.query(func.count(Player.id)).scalar() or 0
    total_venues = db.query(func.count(Venue.id)).scalar() or 0
    total_seasons = db.query(func.count(func.distinct(Match.season))).scalar() or 0

    # Top 5 run scorers across all seasons
    top_batters = (
        db.query(
            Player.name,
            func.sum(PlayerSeasonBatting.runs).label("total_runs"),
            func.sum(PlayerSeasonBatting.matches).label("total_matches"),
        )
        .join(Player, PlayerSeasonBatting.player_id == Player.id)
        .group_by(PlayerSeasonBatting.player_id)
        .order_by(func.sum(PlayerSeasonBatting.runs).desc())
        .limit(5)
        .all()
    )

    top_run_scorers = [
        {"name": row.name, "runs": int(row.total_runs), "matches": int(row.total_matches)}
        for row in top_batters
    ]

    # Top 5 wicket takers across all seasons
    top_bowlers = (
        db.query(
            Player.name,
            func.sum(PlayerSeasonBowling.wickets).label("total_wickets"),
            func.sum(PlayerSeasonBowling.matches).label("total_matches"),
        )
        .join(Player, PlayerSeasonBowling.player_id == Player.id)
        .group_by(PlayerSeasonBowling.player_id)
        .order_by(func.sum(PlayerSeasonBowling.wickets).desc())
        .limit(5)
        .all()
    )

    top_wicket_takers = [
        {"name": row.name, "wickets": int(row.total_wickets), "matches": int(row.total_matches)}
        for row in top_bowlers
    ]

    return {
        "total_matches": total_matches,
        "total_players": total_players,
        "total_venues": total_venues,
        "total_seasons": total_seasons,
        "top_run_scorers": top_run_scorers,
        "top_wicket_takers": top_wicket_takers,
    }
