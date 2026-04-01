"""On-the-fly stats computation from the database."""

from sqlalchemy import func, and_, or_, case
from sqlalchemy.orm import Session

from typing import List, Optional

from app.models.models import (
    Team,
    Player,
    Match,
    Delivery,
    PlayerSeasonBatting,
    PlayerSeasonBowling,
    BatterVsBowler,
    Venue,
    VenueStats,
)


def get_team_stats(db: Session, team_id: int, season: Optional[str] = None) -> dict:
    """Return aggregate stats for a team, optionally filtered by season."""
    q = db.query(Match).filter(
        or_(Match.team1_id == team_id, Match.team2_id == team_id)
    )
    if season:
        q = q.filter(Match.season == season)

    matches = q.all()
    total = len(matches)
    wins = sum(1 for m in matches if m.winner_id == team_id)
    losses = total - wins

    # Toss stats
    toss_wins = sum(1 for m in matches if m.toss_winner_id == team_id)

    # Average scores when batting first / second
    bat_first_scores = []
    bat_second_scores = []
    for m in matches:
        if m.team1_id == team_id and m.first_innings_score is not None:
            bat_first_scores.append(m.first_innings_score)
        if m.team2_id == team_id and m.second_innings_score is not None:
            bat_second_scores.append(m.second_innings_score)

    # Recent form (last 5)
    recent = sorted(matches, key=lambda m: m.date or m.id, reverse=True)[:5]
    recent_form = ["W" if m.winner_id == team_id else "L" for m in recent]

    # Top performers: top run scorers
    team = db.query(Team).get(team_id)

    return {
        "team_id": team_id,
        "team_name": team.name if team else None,
        "matches": total,
        "wins": wins,
        "losses": losses,
        "win_pct": round(wins / total * 100, 1) if total > 0 else 0.0,
        "toss_wins": toss_wins,
        "avg_bat_first_score": round(sum(bat_first_scores) / len(bat_first_scores), 1) if bat_first_scores else 0,
        "avg_bat_second_score": round(sum(bat_second_scores) / len(bat_second_scores), 1) if bat_second_scores else 0,
        "recent_form": recent_form,
    }


def get_player_batting_stats(
    db: Session, player_id: int, season: Optional[str] = None
) -> List[dict]:
    """Return batting stats per season for a player."""
    q = db.query(PlayerSeasonBatting).filter(
        PlayerSeasonBatting.player_id == player_id
    )
    if season:
        q = q.filter(PlayerSeasonBatting.season == season)

    rows = q.order_by(PlayerSeasonBatting.season).all()
    return [
        {
            "season": r.season,
            "matches": r.matches,
            "innings": r.innings,
            "runs": r.runs,
            "balls_faced": r.balls_faced,
            "fours": r.fours,
            "sixes": r.sixes,
            "strike_rate": r.strike_rate,
            "average": r.average,
            "highest_score": r.highest_score,
            "fifties": r.fifties,
            "hundreds": r.hundreds,
            "not_outs": r.not_outs,
        }
        for r in rows
    ]


def get_player_bowling_stats(
    db: Session, player_id: int, season: Optional[str] = None
) -> List[dict]:
    """Return bowling stats per season for a player."""
    q = db.query(PlayerSeasonBowling).filter(
        PlayerSeasonBowling.player_id == player_id
    )
    if season:
        q = q.filter(PlayerSeasonBowling.season == season)

    rows = q.order_by(PlayerSeasonBowling.season).all()
    return [
        {
            "season": r.season,
            "matches": r.matches,
            "innings": r.innings,
            "overs_bowled": r.overs_bowled,
            "runs_conceded": r.runs_conceded,
            "wickets": r.wickets,
            "economy": r.economy,
            "average": r.average,
            "best_figures": r.best_figures,
            "four_wickets": r.four_wickets,
            "five_wickets": r.five_wickets,
        }
        for r in rows
    ]


def get_venue_stats(db: Session, venue_id: int) -> Optional[dict]:
    """Return venue stats."""
    vs = db.query(VenueStats).filter(VenueStats.venue_id == venue_id).first()
    if not vs:
        return None
    venue = db.query(Venue).get(venue_id)
    return {
        "venue_id": venue_id,
        "venue_name": venue.name if venue else None,
        "city": venue.city if venue else None,
        "matches_played": vs.matches_played,
        "avg_first_innings_score": vs.avg_first_innings_score,
        "avg_second_innings_score": vs.avg_second_innings_score,
        "bat_first_win_pct": vs.bat_first_win_pct,
        "highest_score": vs.highest_score,
        "lowest_score": vs.lowest_score,
    }


def get_head_to_head(db: Session, team1_id: int, team2_id: int) -> dict:
    """Return head-to-head stats between two teams."""
    matches = (
        db.query(Match)
        .filter(
            or_(
                and_(Match.team1_id == team1_id, Match.team2_id == team2_id),
                and_(Match.team1_id == team2_id, Match.team2_id == team1_id),
            )
        )
        .all()
    )

    total = len(matches)
    t1_wins = sum(1 for m in matches if m.winner_id == team1_id)
    t2_wins = sum(1 for m in matches if m.winner_id == team2_id)
    no_result = total - t1_wins - t2_wins

    team1 = db.query(Team).get(team1_id)
    team2 = db.query(Team).get(team2_id)

    # Recent matches
    recent = sorted(matches, key=lambda m: m.date or m.id, reverse=True)[:5]
    recent_results = []
    for m in recent:
        winner = db.query(Team).get(m.winner_id) if m.winner_id else None
        recent_results.append(
            {
                "date": str(m.date) if m.date else None,
                "season": m.season,
                "winner": winner.name if winner else "No Result",
                "margin": f"{m.win_margin} {m.win_type}" if m.win_margin else None,
            }
        )

    return {
        "team1": {"id": team1_id, "name": team1.name if team1 else None},
        "team2": {"id": team2_id, "name": team2.name if team2 else None},
        "total_matches": total,
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "no_result": no_result,
        "recent_matches": recent_results,
    }


def get_batter_vs_bowler(db: Session, batter_id: int, bowler_id: int) -> Optional[dict]:
    """Return batter vs bowler matchup stats."""
    record = (
        db.query(BatterVsBowler)
        .filter(
            BatterVsBowler.batter_id == batter_id,
            BatterVsBowler.bowler_id == bowler_id,
        )
        .first()
    )

    if not record:
        return None

    batter = db.query(Player).get(batter_id)
    bowler = db.query(Player).get(bowler_id)

    sr = (record.runs / record.balls * 100) if record.balls > 0 else 0.0

    return {
        "batter": {"id": batter_id, "name": batter.name if batter else None},
        "bowler": {"id": bowler_id, "name": bowler.name if bowler else None},
        "balls": record.balls,
        "runs": record.runs,
        "dismissals": record.dismissals,
        "dots": record.dots,
        "fours": record.fours,
        "sixes": record.sixes,
        "strike_rate": round(sr, 2),
        "average": round(record.runs / record.dismissals, 2) if record.dismissals > 0 else None,
    }
