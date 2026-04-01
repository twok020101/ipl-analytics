"""Player API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db
from app.models.models import Player, PlayerSeasonBatting, PlayerSeasonBowling, Team
from app.services.stats import get_player_batting_stats, get_player_bowling_stats
from app.services.form import calculate_form_index

router = APIRouter(prefix="/players", tags=["players"])


@router.get("")
def list_players(
    search: str = Query(None, description="Search by name"),
    team: str = Query(None, description="Filter by team short name or ID"),
    role: str = Query(None, description="Filter by role"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Search and filter players."""
    q = db.query(Player)

    if search:
        q = q.filter(Player.name.ilike(f"%{search}%"))

    if role:
        q = q.filter(Player.role.ilike(f"%{role}%"))

    # Team filter via season batting records
    if team:
        team_obj = db.query(Team).filter(
            Team.short_name.ilike(team) | (Team.id == _try_int(team))
        ).first()
        if team_obj:
            player_ids = (
                db.query(PlayerSeasonBatting.player_id)
                .filter(PlayerSeasonBatting.team_id == team_obj.id)
                .distinct()
                .subquery()
            )
            q = q.filter(Player.id.in_(player_ids))

    total = q.count()
    players = q.order_by(Player.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
            }
            for p in players
        ],
    }


@router.get("/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_db)):
    """Get full player profile."""
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Career batting summary
    bat_stats = get_player_batting_stats(db, player_id)
    bowl_stats = get_player_bowling_stats(db, player_id)

    # Career totals
    total_runs = sum(s["runs"] for s in bat_stats)
    total_balls = sum(s["balls_faced"] for s in bat_stats)
    total_matches_bat = sum(s["matches"] for s in bat_stats)
    total_wickets = sum(s["wickets"] for s in bowl_stats)
    total_matches_bowl = sum(s["matches"] for s in bowl_stats)

    # Teams played for
    teams = (
        db.query(Team.name, Team.short_name)
        .join(PlayerSeasonBatting, PlayerSeasonBatting.team_id == Team.id)
        .filter(PlayerSeasonBatting.player_id == player_id)
        .distinct()
        .all()
    )

    return {
        "id": player.id,
        "name": player.name,
        "role": player.role,
        "batting_style": player.batting_style,
        "bowling_style": player.bowling_style,
        "teams": [{"name": t[0], "short_name": t[1]} for t in teams],
        "career_batting": {
            "matches": total_matches_bat,
            "runs": total_runs,
            "balls_faced": total_balls,
            "strike_rate": round(total_runs / total_balls * 100, 2) if total_balls > 0 else 0,
            "seasons": len(bat_stats),
        },
        "career_bowling": {
            "matches": total_matches_bowl,
            "wickets": total_wickets,
            "seasons": len(bowl_stats),
        },
    }


@router.get("/{player_id}/batting")
def get_player_batting(
    player_id: int,
    season: str = None,
    db: Session = Depends(get_db),
):
    """Get batting stats by season."""
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    stats = get_player_batting_stats(db, player_id, season)
    return {"player_id": player_id, "player_name": player.name, "batting": stats}


@router.get("/{player_id}/bowling")
def get_player_bowling(
    player_id: int,
    season: str = None,
    db: Session = Depends(get_db),
):
    """Get bowling stats by season."""
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    stats = get_player_bowling_stats(db, player_id, season)
    return {"player_id": player_id, "player_name": player.name, "bowling": stats}


@router.get("/{player_id}/form")
def get_player_form(
    player_id: int,
    role: str = Query("batter", description="batter or bowler"),
    db: Session = Depends(get_db),
):
    """Get player form index."""
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    form = calculate_form_index(db, player_id, role)
    return form


def _try_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return -1
