"""Head-to-head API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.models import Team, Player
from app.services.stats import get_head_to_head, get_batter_vs_bowler

router = APIRouter(prefix="/h2h", tags=["head-to-head"])


@router.get("/teams")
def team_head_to_head(
    team1: str = Query(..., description="Team 1 short name or ID"),
    team2: str = Query(..., description="Team 2 short name or ID"),
    db: Session = Depends(get_db),
):
    """Get head-to-head stats between two teams."""
    t1 = _find_team(db, team1)
    t2 = _find_team(db, team2)

    if not t1:
        raise HTTPException(status_code=404, detail=f"Team '{team1}' not found")
    if not t2:
        raise HTTPException(status_code=404, detail=f"Team '{team2}' not found")

    return get_head_to_head(db, t1.id, t2.id)


@router.get("/players")
def player_matchup(
    batter: int = Query(..., description="Batter player ID"),
    bowler: int = Query(..., description="Bowler player ID"),
    db: Session = Depends(get_db),
):
    """Get batter vs bowler matchup stats."""
    batter_player = db.query(Player).get(batter)
    if not batter_player:
        raise HTTPException(status_code=404, detail="Batter not found")

    bowler_player = db.query(Player).get(bowler)
    if not bowler_player:
        raise HTTPException(status_code=404, detail="Bowler not found")

    result = get_batter_vs_bowler(db, batter, bowler)
    if not result:
        return {
            "batter": {"id": batter, "name": batter_player.name},
            "bowler": {"id": bowler, "name": bowler_player.name},
            "balls": 0,
            "runs": 0,
            "dismissals": 0,
            "message": "No matchup data available",
        }

    return result


def _find_team(db: Session, identifier: str) -> Optional[Team]:
    try:
        team_id = int(identifier)
        team = db.query(Team).get(team_id)
        if team:
            return team
    except (ValueError, TypeError):
        pass

    return db.query(Team).filter(Team.short_name.ilike(identifier)).first()
