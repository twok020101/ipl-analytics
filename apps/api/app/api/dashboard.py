"""Dashboard stats endpoint — global and team-scoped views.

The /dashboard/stats endpoint returns global stats for all users.
The /dashboard/my-team endpoint returns team-specific analysis scoped
to the user's organization's linked IPL team.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_auth, get_current_user
from app.config import CURRENT_SEASON
from app.models.models import (
    Match,
    Player,
    Team,
    Venue,
    User,
    Organization,
    SquadMember,
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
        .group_by(PlayerSeasonBatting.player_id, Player.name)
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
        .group_by(PlayerSeasonBowling.player_id, Player.name)
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


@router.get("/my-team")
def get_my_team_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Team-scoped dashboard for the user's org-linked IPL team.

    Returns:
      - Team info and current season record
      - Squad members for IPL 2026
      - Upcoming matches for this team
      - Recent results involving this team
      - Top performers from the team's squad
    """
    # Resolve org → team
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="No organization linked to your account")

    org = db.get(Organization, user.organization_id)
    if not org or not org.team_id:
        raise HTTPException(status_code=400, detail="Your organization is not linked to an IPL team. Ask your admin to link one.")

    team = db.get(Team, org.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Linked team not found")

    # Current season record
    season_matches = db.query(Match).filter(
        Match.season == CURRENT_SEASON,
        or_(Match.team1_id == team.id, Match.team2_id == team.id),
    ).all()

    wins = sum(1 for m in season_matches if m.winner_id == team.id)
    losses = sum(1 for m in season_matches if m.winner_id and m.winner_id != team.id)

    # Pre-load all opponent teams in one query to avoid N+1
    opponent_ids = {m.team1_id for m in season_matches} | {m.team2_id for m in season_matches}
    opponent_ids.discard(team.id)
    team_cache = {t.id: t for t in db.query(Team).filter(Team.id.in_(opponent_ids)).all()}

    def _opponent_name(m: Match) -> str:
        opp_id = m.team2_id if m.team1_id == team.id else m.team1_id
        opp = team_cache.get(opp_id)
        return opp.short_name if opp else "?"

    upcoming = [
        {
            "match_id": m.id,
            "opponent": _opponent_name(m),
            "date": str(m.date) if m.date else None,
            "venue": m.venue.name if m.venue else None,
        }
        for m in season_matches
        if not m.winner_id and m.team1_id and m.team2_id
    ][:5]

    recent_results = [
        {
            "match_id": m.id,
            "opponent": _opponent_name(m),
            "result": "Won" if m.winner_id == team.id else "Lost",
            "margin": f"{m.win_margin} {m.win_type}" if m.win_margin else None,
            "date": str(m.date) if m.date else None,
        }
        for m in sorted(season_matches, key=lambda m: m.date or "", reverse=True)
        if m.winner_id
    ][:5]

    # Squad for current season
    squad_members = db.query(SquadMember, Player).join(
        Player, SquadMember.player_id == Player.id
    ).filter(
        SquadMember.team_id == team.id,
        SquadMember.season == CURRENT_SEASON,
    ).all()

    squad = [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role,
            "is_captain": sm.is_captain,
            "country": p.country,
        }
        for sm, p in squad_members
    ]

    # Top performers from squad
    squad_ids = [p.id for _, p in squad_members]
    top_batters = (
        db.query(Player.name, PlayerSeasonBatting.runs, PlayerSeasonBatting.strike_rate)
        .join(Player, PlayerSeasonBatting.player_id == Player.id)
        .filter(
            PlayerSeasonBatting.player_id.in_(squad_ids),
            PlayerSeasonBatting.season == CURRENT_SEASON,
        )
        .order_by(PlayerSeasonBatting.runs.desc())
        .limit(5)
        .all()
    ) if squad_ids else []

    top_bowlers = (
        db.query(Player.name, PlayerSeasonBowling.wickets, PlayerSeasonBowling.economy)
        .join(Player, PlayerSeasonBowling.player_id == Player.id)
        .filter(
            PlayerSeasonBowling.player_id.in_(squad_ids),
            PlayerSeasonBowling.season == CURRENT_SEASON,
        )
        .order_by(PlayerSeasonBowling.wickets.desc())
        .limit(5)
        .all()
    ) if squad_ids else []

    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "short_name": team.short_name,
        },
        "season_record": {
            "played": wins + losses,
            "won": wins,
            "lost": losses,
            "points": wins * 2,
        },
        "squad": squad,
        "squad_size": len(squad),
        "upcoming_matches": upcoming,
        "recent_results": recent_results,
        "top_batters": [
            {"name": r.name, "runs": r.runs, "strike_rate": round(r.strike_rate, 1) if r.strike_rate else 0}
            for r in top_batters
        ],
        "top_bowlers": [
            {"name": r.name, "wickets": r.wickets, "economy": round(r.economy, 2) if r.economy else 0}
            for r in top_bowlers
        ],
    }
