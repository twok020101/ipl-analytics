"""Strategy recommendation API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.ml.strategy_engine import (
    select_playing_11,
    recommend_toss_decision,
    create_game_plan,
    live_game_plan_update,
    IPL_RULES,
)
from typing import List, Optional

router = APIRouter(prefix="/strategy", tags=["strategy"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class Playing11Request(BaseModel):
    team: str
    opposition: str
    venue_id: int
    season: str = "2026"
    unavailable_player_ids: list[int] = []


class TossDecisionRequest(BaseModel):
    team: str
    opposition: str
    venue_id: int


class GamePlanRequest(BaseModel):
    team: str
    playing_11: List[int]
    opposition: str
    opposition_11: List[int]
    venue_id: int
    batting_first: bool


class LiveUpdateRequest(BaseModel):
    team: str
    playing_11: List[int]
    opposition: str
    score: int
    wickets: int
    over: float
    is_batting: bool
    venue_id: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/rules")
def get_ipl_rules():
    """Get all IPL 2026 playing rules enforced by the strategy engine."""
    return {
        "rules": IPL_RULES,
        "summary": {
            "team_composition": [
                f"Playing XI must have exactly {IPL_RULES['PLAYING_XI_SIZE']} players",
                f"Maximum {IPL_RULES['MAX_OVERSEAS_IN_XI']} overseas players in XI",
                f"If impact player is overseas, starting XI can have max {IPL_RULES['MAX_OVERSEAS_IF_IMPACT_OVERSEAS']} overseas",
                "Must have at least 1 wicket-keeper",
                f"Must have at least {IPL_RULES['MIN_BOWLERS_NEEDED']} bowling options (to cover 20 overs at {IPL_RULES['MAX_OVERS_PER_BOWLER']} overs each)",
            ],
            "impact_player": [
                "1 impact player substitution per match",
                "5 substitute names declared 30 min before toss",
                "Can substitute: before innings, after wicket, at over completion, or when batter retires",
                "Replaced player exits permanently — cannot return",
            ],
            "bowling": [
                f"Each bowler can bowl maximum {IPL_RULES['MAX_OVERS_PER_BOWLER']} overs",
                f"Maximum {IPL_RULES['MAX_BOUNCERS_PER_OVER']} bouncers (short-pitched above shoulder) per over",
                "3rd bouncer = no-ball + free hit",
                "Above head height = automatic no-ball",
            ],
            "fielding": [
                f"Powerplay (overs {IPL_RULES['POWERPLAY_OVERS'][0]}-{IPL_RULES['POWERPLAY_OVERS'][1]}): max {IPL_RULES['PP_MAX_FIELDERS_OUTSIDE_CIRCLE']} fielders outside 30-yard circle",
                f"Overs 7-20: max {IPL_RULES['NORMAL_MAX_FIELDERS_OUTSIDE_CIRCLE']} fielders outside circle",
                f"Over-rate penalty: if 20th over not started in {IPL_RULES['OVER_RATE_TIME_LIMIT_MINUTES']} min, max {IPL_RULES['OVER_RATE_PENALTY_FIELDERS']} outside",
            ],
            "drs": [
                f"{IPL_RULES['DRS_REVIEWS_PER_INNINGS']} reviews per team per innings",
                f"{IPL_RULES['DRS_SIGNAL_TIME_SECONDS']} seconds to signal review",
                "Successful review / umpire's call = review retained",
                "Can review wides and no-balls (IPL-specific)",
            ],
            "strategic_timeout": [
                f"Timeout 1 (bowling team): after over {IPL_RULES['TIMEOUT_1_WINDOW'][0]}, before over {IPL_RULES['TIMEOUT_1_WINDOW'][1]+1}",
                f"Timeout 2 (batting team): after over {IPL_RULES['TIMEOUT_2_WINDOW'][0]}, before over {IPL_RULES['TIMEOUT_2_WINDOW'][1]+1}",
                f"Duration: {IPL_RULES['TIMEOUT_DURATION_SECONDS']} seconds (2 min 30 sec)",
            ],
            "super_over": [
                f"Each team bats {IPL_RULES['SUPER_OVER_BALLS']} balls",
                f"Each team selects {IPL_RULES['SUPER_OVER_BATTERS']} batters + 1 bowler",
                "Cannot reuse bowler from previous super over",
                "Unlimited super overs until winner decided",
            ],
        },
    }


@router.post("/playing-11")
def get_playing_11(req: Playing11Request, db: Session = Depends(get_db)):
    """Select optimal playing 11 + impact player from the squad."""
    try:
        result = select_playing_11(
            db,
            team_short_name=req.team,
            opposition_short_name=req.opposition,
            venue_id=req.venue_id,
            season=req.season,
            unavailable_player_ids=set(req.unavailable_player_ids) if req.unavailable_player_ids else None,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toss-decision")
def get_toss_decision(req: TossDecisionRequest, db: Session = Depends(get_db)):
    """Get bat/field recommendation with reasoning."""
    try:
        result = recommend_toss_decision(
            db,
            team_short_name=req.team,
            opposition_short_name=req.opposition,
            venue_id=req.venue_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game-plan")
def get_game_plan(req: GamePlanRequest, db: Session = Depends(get_db)):
    """Get full game plan: batting order + bowling plan + matchups."""
    if len(req.playing_11) != 11:
        raise HTTPException(status_code=400, detail="playing_11 must contain exactly 11 player IDs")
    if len(req.opposition_11) != 11:
        raise HTTPException(status_code=400, detail="opposition_11 must contain exactly 11 player IDs")
    try:
        result = create_game_plan(
            db,
            team_short_name=req.team,
            playing_11_ids=req.playing_11,
            opposition_short_name=req.opposition,
            opposition_11_ids=req.opposition_11,
            venue_id=req.venue_id,
            batting_first=req.batting_first,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/live-update")
def get_live_update(req: LiveUpdateRequest, db: Session = Depends(get_db)):
    """Get adjusted strategy based on current match situation."""
    if req.wickets < 0 or req.wickets > 10:
        raise HTTPException(status_code=400, detail="wickets must be between 0 and 10")
    if req.over < 0 or req.over > 20:
        raise HTTPException(status_code=400, detail="over must be between 0 and 20")
    try:
        result = live_game_plan_update(
            db,
            team_short_name=req.team,
            playing_11_ids=req.playing_11,
            opposition_short_name=req.opposition,
            current_score=req.score,
            current_wickets=req.wickets,
            current_over=req.over,
            is_batting=req.is_batting,
            venue_id=req.venue_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
