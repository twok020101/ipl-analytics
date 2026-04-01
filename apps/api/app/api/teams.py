"""Team API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db
from app.models.models import Team, Player, PlayerSeasonBatting, Match
from app.services.stats import get_team_stats

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("")
def list_teams(
    active_only: bool = Query(False, description="Only return active teams"),
    db: Session = Depends(get_db),
):
    """List all IPL teams."""
    q = db.query(Team)
    if active_only:
        q = q.filter(Team.is_active == True)
    teams = q.order_by(Team.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "short_name": t.short_name,
            "is_active": t.is_active,
            "slug": t.short_name.lower() if t.short_name else str(t.id),
        }
        for t in teams
    ]


@router.get("/{slug}")
def get_team(slug: str, season: str = None, db: Session = Depends(get_db)):
    """Get team profile with stats. Slug can be short_name (e.g., CSK) or team ID."""
    team = db.query(Team).filter(
        or_(
            Team.short_name.ilike(slug),
            Team.id == _try_int(slug),
        )
    ).first()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    stats = get_team_stats(db, team.id, season)

    # Get seasons played
    seasons = (
        db.query(Match.season)
        .filter(or_(Match.team1_id == team.id, Match.team2_id == team.id))
        .distinct()
        .all()
    )

    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name,
        "is_active": team.is_active,
        "seasons": sorted([s[0] for s in seasons if s[0]]),
        "stats": stats,
    }


@router.get("/{slug}/players")
def get_team_players(slug: str, season: str = None, db: Session = Depends(get_db)):
    """Get players who have played for a team."""
    team = db.query(Team).filter(
        or_(
            Team.short_name.ilike(slug),
            Team.id == _try_int(slug),
        )
    ).first()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    q = db.query(PlayerSeasonBatting).filter(PlayerSeasonBatting.team_id == team.id)
    if season:
        q = q.filter(PlayerSeasonBatting.season == season)

    bat_records = q.all()
    player_ids = list({r.player_id for r in bat_records})

    players = db.query(Player).filter(Player.id.in_(player_ids)).all()

    result = []
    for p in players:
        # Get latest season stats
        latest_bat = (
            db.query(PlayerSeasonBatting)
            .filter(
                PlayerSeasonBatting.player_id == p.id,
                PlayerSeasonBatting.team_id == team.id,
            )
            .order_by(PlayerSeasonBatting.season.desc())
            .first()
        )
        result.append({
            "id": p.id,
            "name": p.name,
            "role": p.role,
            "latest_season": latest_bat.season if latest_bat else None,
            "runs": latest_bat.runs if latest_bat else 0,
            "matches": latest_bat.matches if latest_bat else 0,
            "strike_rate": latest_bat.strike_rate if latest_bat else 0,
        })

    result.sort(key=lambda x: x["runs"], reverse=True)
    return result


def _try_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return -1
