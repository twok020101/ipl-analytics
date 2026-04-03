"""External data API routes — IPL 2026 fixtures, squads, players."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.external_api import (
    get_cached_data, get_fixtures, get_squads, get_team_squad,
    get_upcoming_fixtures, refresh_ipl2026_data, fetch_player_info
)

router = APIRouter(prefix="/external", tags=["external"])


@router.get("/ipl2026")
def get_ipl2026_data(db: Session = Depends(get_db)):
    """Get all cached IPL 2026 data."""
    data = get_cached_data(db)
    if not data:
        raise HTTPException(404, "IPL 2026 data not available. Call POST /external/refresh first.")
    return data


@router.get("/fixtures")
def list_fixtures(db: Session = Depends(get_db)):
    """Get IPL 2026 match fixtures."""
    return get_fixtures(db)


@router.get("/fixtures/upcoming")
def upcoming_fixtures(limit: int = 5, db: Session = Depends(get_db)):
    """Get upcoming IPL 2026 fixtures."""
    return get_upcoming_fixtures(db, limit)


@router.get("/squads")
def list_squads(db: Session = Depends(get_db)):
    """Get all IPL 2026 team squads."""
    squads = get_squads(db)
    if not squads:
        raise HTTPException(404, "Squad data not available. Call POST /external/refresh first.")
    return squads


@router.get("/squads/{team}")
def get_squad(team: str, db: Session = Depends(get_db)):
    """Get squad for a specific team (use short name: CSK, MI, etc.)."""
    squad = get_team_squad(db, team)
    if not squad:
        raise HTTPException(404, f"Squad for '{team}' not found")
    return squad


@router.post("/refresh")
async def refresh_data(db: Session = Depends(get_db)):
    """Refresh IPL 2026 data from CricAPI. Uses API quota."""
    result = await refresh_ipl2026_data(db)
    if "error" in result:
        raise HTTPException(502, result["error"])
    return {
        "status": "refreshed",
        "teams": len(result.get("squads", {})),
        "fixtures": len(result.get("fixtures", [])),
    }


@router.get("/player/{player_id}")
async def get_player(player_id: str):
    """Get player details from CricAPI."""
    info = await fetch_player_info(player_id)
    if not info:
        raise HTTPException(404, "Player not found or API unavailable")
    return info
