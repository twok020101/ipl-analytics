"""AI-powered insights API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.models import Team, Player, Venue
from app.services.stats import (
    get_team_stats,
    get_venue_stats,
    get_head_to_head,
    get_player_batting_stats,
    get_player_bowling_stats,
    get_batter_vs_bowler,
)
from typing import List, Optional

from app.services.gemini import (
    generate_match_preview,
    generate_player_report,
    chat_analytics,
)

router = APIRouter(prefix="/ai", tags=["ai-insights"])


class MatchPreviewRequest(BaseModel):
    team1_id: int
    team2_id: int
    venue_id: Optional[int] = None


class PlayerReportRequest(BaseModel):
    player_id: int
    opposition_bowler_ids: Optional[List[int]] = None
    season: Optional[str] = None


class ChatRequest(BaseModel):
    question: str
    context: Optional[dict] = None


@router.post("/match-preview")
def match_preview(req: MatchPreviewRequest, db: Session = Depends(get_db)):
    """Generate AI-powered match preview."""
    team1 = db.query(Team).get(req.team1_id)
    team2 = db.query(Team).get(req.team2_id)
    if not team1 or not team2:
        raise HTTPException(status_code=404, detail="Team not found")

    team1_stats = get_team_stats(db, req.team1_id)
    team2_stats = get_team_stats(db, req.team2_id)
    venue_stats = get_venue_stats(db, req.venue_id) if req.venue_id else None
    h2h_stats = get_head_to_head(db, req.team1_id, req.team2_id)

    preview = generate_match_preview(team1_stats, team2_stats, venue_stats, h2h_stats)

    return {
        "team1": {"id": team1.id, "name": team1.name},
        "team2": {"id": team2.id, "name": team2.name},
        "preview": preview,
        "data": {
            "team1_stats": team1_stats,
            "team2_stats": team2_stats,
            "venue_stats": venue_stats,
            "h2h": h2h_stats,
        },
    }


@router.post("/player-report")
def player_report(req: PlayerReportRequest, db: Session = Depends(get_db)):
    """Generate AI-powered scouting report."""
    player = db.query(Player).get(req.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    batting = get_player_batting_stats(db, req.player_id, req.season)
    bowling = get_player_bowling_stats(db, req.player_id, req.season)

    player_stats = {
        "name": player.name,
        "role": player.role,
        "batting": batting,
        "bowling": bowling,
    }

    matchup_data = None
    if req.opposition_bowler_ids:
        matchups = []
        for bid in req.opposition_bowler_ids:
            m = get_batter_vs_bowler(db, req.player_id, bid)
            if m:
                matchups.append(m)
        if matchups:
            matchup_data = {"matchups": matchups}

    report = generate_player_report(player_stats, matchup_data)

    return {
        "player": {"id": player.id, "name": player.name},
        "report": report,
        "stats": player_stats,
    }


@router.post("/chat")
def ai_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Chat with AI analytics assistant."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Build context from any referenced entities
    context = req.context or {}

    answer = chat_analytics(req.question, context)

    return {
        "question": req.question,
        "answer": answer,
    }
