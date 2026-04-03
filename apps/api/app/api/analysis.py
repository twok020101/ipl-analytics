"""
Comprehensive match analysis API endpoint.

Returns a complete analysis object for a match between two IPL teams at a venue,
including head-to-head, player stats, matchup matrix, venue analysis, toss
recommendation, and win prediction.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, case, and_, or_
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.squad_service import get_squad_data, get_player_meta, get_squad_player_names
from app.models.models import (
    Team,
    Player,
    SquadMember,
    Match,
    Delivery,
    PlayerSeasonBatting,
    PlayerSeasonBowling,
    BatterVsBowler,
    Venue,
    VenueStats,
)
from app.services.stats import get_head_to_head, get_venue_stats, get_batter_vs_bowler
from app.services.gemini import fetch_player_news
from app.ml.strategy_engine import select_playing_11, recommend_toss_decision

router = APIRouter(tags=["analysis"])

# Phase boundaries (0-indexed over numbers)
POWERPLAY = (0, 5)
MIDDLE = (6, 14)
DEATH = (15, 19)


class MatchAnalysisRequest(BaseModel):
    team1: str
    team2: str
    venue_id: int


UNAVAILABLE_STATUSES = frozenset({"injured", "ruled_out"})


def _name_to_id_map(db: Session, team_short: str) -> dict[str, int]:
    """Map player name (lowercase) -> DB player_id from squad_members."""
    members = (
        db.query(SquadMember)
        .join(Player, SquadMember.player_id == Player.id)
        .join(Team, SquadMember.team_id == Team.id)
        .filter(SquadMember.season == "2026", Team.short_name == team_short)
        .all()
    )
    return {m.player.name.lower(): m.player_id for m in members}


# -----------------------------------------------------------------------
# Helper: phase strike rate / economy
# -----------------------------------------------------------------------

def _phase_sr(db: Session, batter_id: int, over_start: int, over_end: int) -> Optional[float]:
    r = db.query(
        func.sum(Delivery.runs_batter).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
    ).filter(
        Delivery.batter_id == batter_id,
        Delivery.over_num >= over_start,
        Delivery.over_num <= over_end,
    ).first()
    if r and r.balls and r.balls > 0:
        return round(float(r.runs) / float(r.balls) * 100, 1)
    return None


def _phase_econ(db: Session, bowler_id: int, over_start: int, over_end: int) -> Optional[float]:
    r = db.query(
        func.sum(Delivery.runs_total).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
    ).filter(
        Delivery.bowler_id == bowler_id,
        Delivery.over_num >= over_start,
        Delivery.over_num <= over_end,
    ).first()
    if r and r.balls and r.balls > 0:
        return round(float(r.runs) / (float(r.balls) / 6.0), 2)
    return None


# -----------------------------------------------------------------------
# Player career stats (aggregated from season tables)
# -----------------------------------------------------------------------

def _career_batting(db: Session, player_id: int) -> dict:
    rows = db.query(PlayerSeasonBatting).filter(
        PlayerSeasonBatting.player_id == player_id
    ).all()
    if not rows:
        return {"matches": 0, "runs": 0, "avg": 0, "sr": 0, "50s": 0, "100s": 0}
    total_matches = sum(r.matches for r in rows)
    total_runs = sum(r.runs for r in rows)
    total_balls = sum(r.balls_faced for r in rows)
    total_innings = sum(r.innings for r in rows)
    total_not_outs = sum(r.not_outs for r in rows)
    total_50s = sum(r.fifties for r in rows)
    total_100s = sum(r.hundreds for r in rows)
    dismissals = total_innings - total_not_outs
    avg = round(total_runs / max(dismissals, 1), 2)
    sr = round(total_runs / max(total_balls, 1) * 100, 2)
    return {
        "matches": total_matches,
        "runs": total_runs,
        "avg": avg,
        "sr": sr,
        "50s": total_50s,
        "100s": total_100s,
    }


def _career_bowling(db: Session, player_id: int) -> dict:
    rows = db.query(PlayerSeasonBowling).filter(
        PlayerSeasonBowling.player_id == player_id
    ).all()
    if not rows:
        return {"matches": 0, "wickets": 0, "economy": 0, "avg": 0, "sr": 0}
    total_matches = sum(r.matches for r in rows)
    total_wickets = sum(r.wickets for r in rows)
    total_runs = sum(r.runs_conceded for r in rows)
    total_overs = sum(r.overs_bowled for r in rows)
    total_balls = total_overs * 6 if total_overs else 0
    economy = round(total_runs / max(total_overs, 0.1), 2)
    avg = round(total_runs / max(total_wickets, 1), 2)
    sr = round(total_balls / max(total_wickets, 1), 1)
    return {
        "matches": total_matches,
        "wickets": total_wickets,
        "economy": economy,
        "avg": avg,
        "sr": sr,
    }


# -----------------------------------------------------------------------
# Opposition-specific stats
# -----------------------------------------------------------------------

def _batting_vs_opposition(db: Session, batter_id: int, opp_team_id: int) -> dict:
    """Batting stats against a specific opposition team."""
    opp_match_ids = db.query(Match.id).filter(
        or_(Match.team1_id == opp_team_id, Match.team2_id == opp_team_id)
    ).subquery()
    r = db.query(
        func.sum(Delivery.runs_batter).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
        func.count(case((Delivery.wicket_kind != None, Delivery.id))).label("dismissals"),
        func.count(func.distinct(Delivery.match_id)).label("matches"),
    ).filter(
        Delivery.batter_id == batter_id,
        Delivery.match_id.in_(db.query(opp_match_ids.c.id)),
    ).first()
    runs = r.runs or 0 if r else 0
    balls = r.balls or 0 if r else 0
    matches = r.matches or 0 if r else 0
    dismissals = r.dismissals or 0 if r else 0
    avg = round(runs / max(dismissals, 1), 2)
    sr = round(runs / max(balls, 1) * 100, 2)

    # Top dismissers from this opposition
    dismissals_by = []
    if dismissals > 0:
        top_bowlers = db.query(
            Delivery.bowler_id,
            func.count(Delivery.id).label("times"),
        ).filter(
            Delivery.batter_id == batter_id,
            Delivery.match_id.in_(db.query(opp_match_ids.c.id)),
            Delivery.wicket_kind != None,
            Delivery.player_out_id == batter_id,
        ).group_by(Delivery.bowler_id).order_by(
            func.count(Delivery.id).desc()
        ).limit(3).all()
        for row in top_bowlers:
            bowler = db.get(Player, row.bowler_id)
            dismissals_by.append({
                "bowler": bowler.name if bowler else f"Player {row.bowler_id}",
                "times": row.times,
            })

    return {
        "matches": matches,
        "runs": runs,
        "avg": avg,
        "sr": sr,
        "dismissals_by": dismissals_by,
    }


def _bowling_vs_opposition(db: Session, bowler_id: int, opp_team_id: int) -> dict:
    opp_match_ids = db.query(Match.id).filter(
        or_(Match.team1_id == opp_team_id, Match.team2_id == opp_team_id)
    ).subquery()
    r = db.query(
        func.sum(Delivery.runs_total).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
        func.count(case((Delivery.wicket_kind != None, Delivery.id))).label("wickets"),
    ).filter(
        Delivery.bowler_id == bowler_id,
        Delivery.match_id.in_(db.query(opp_match_ids.c.id)),
    ).first()
    runs = r.runs or 0 if r else 0
    balls = r.balls or 0 if r else 0
    wickets = r.wickets or 0 if r else 0
    economy = round(runs / max(balls / 6.0, 0.1), 2) if balls > 0 else 0
    return {"wickets": wickets, "economy": economy}


# -----------------------------------------------------------------------
# Venue-specific player stats
# -----------------------------------------------------------------------

def _batting_at_venue(db: Session, batter_id: int, venue_id: int) -> dict:
    match_ids = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()
    r = db.query(
        func.sum(Delivery.runs_batter).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
        func.count(case((Delivery.wicket_kind != None, Delivery.id))).label("dismissals"),
        func.count(func.distinct(Delivery.match_id)).label("matches"),
    ).filter(
        Delivery.batter_id == batter_id,
        Delivery.match_id.in_(db.query(match_ids.c.id)),
    ).first()
    runs = r.runs or 0 if r else 0
    balls = r.balls or 0 if r else 0
    matches = r.matches or 0 if r else 0
    dismissals = r.dismissals or 0 if r else 0
    return {
        "matches": matches,
        "runs": runs,
        "avg": round(runs / max(dismissals, 1), 2),
        "sr": round(runs / max(balls, 1) * 100, 2),
    }


def _bowling_at_venue(db: Session, bowler_id: int, venue_id: int) -> dict:
    match_ids = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()
    r = db.query(
        func.sum(Delivery.runs_total).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
        func.count(case((Delivery.wicket_kind != None, Delivery.id))).label("wickets"),
    ).filter(
        Delivery.bowler_id == bowler_id,
        Delivery.match_id.in_(db.query(match_ids.c.id)),
    ).first()
    runs = r.runs or 0 if r else 0
    balls = r.balls or 0 if r else 0
    wickets = r.wickets or 0 if r else 0
    economy = round(runs / max(balls / 6.0, 0.1), 2) if balls > 0 else 0
    return {"wickets": wickets, "economy": economy}


# -----------------------------------------------------------------------
# Recent form
# -----------------------------------------------------------------------

def _recent_scores(db: Session, batter_id: int, limit: int = 5) -> List[int]:
    """Last N innings scores for a batter."""
    subq = db.query(
        Delivery.match_id,
        func.sum(Delivery.runs_batter).label("score"),
    ).filter(
        Delivery.batter_id == batter_id,
    ).group_by(Delivery.match_id).subquery()

    rows = db.query(subq.c.match_id, subq.c.score).join(
        Match, Match.id == subq.c.match_id
    ).order_by(Match.date.desc()).limit(limit).all()

    return [int(r.score) for r in rows]


# -----------------------------------------------------------------------
# Strengths / Weaknesses derivation
# -----------------------------------------------------------------------

def _batter_strengths_weaknesses(
    phase_sr: dict, vs_opp: dict, career: dict
) -> tuple:
    strengths = []
    weaknesses = []

    pp_sr = phase_sr.get("powerplay")
    mid_sr = phase_sr.get("middle")
    death_sr = phase_sr.get("death")

    if pp_sr and pp_sr > 140:
        strengths.append("Explosive in powerplay")
    if death_sr and death_sr > 150:
        strengths.append("Explosive in death overs")
    if mid_sr and mid_sr > 130:
        strengths.append("Aggressive in middle overs")
    if career.get("avg", 0) > 35:
        strengths.append("Consistent run-scorer")
    if career.get("sr", 0) > 140:
        strengths.append("High strike rate player")

    if pp_sr and pp_sr < 100:
        weaknesses.append("Slow starter in powerplay")
    if death_sr and death_sr < 110:
        weaknesses.append("Struggles in death overs")
    if vs_opp.get("sr", 0) > 0 and vs_opp["sr"] < 100 and vs_opp.get("matches", 0) >= 3:
        weaknesses.append(f"Struggles against this opposition (SR {vs_opp['sr']})")
    for d in vs_opp.get("dismissals_by", []):
        if d["times"] >= 3:
            weaknesses.append(f"Vulnerable to {d['bowler']} ({d['times']} dismissals)")

    return strengths[:3], weaknesses[:3]


def _bowler_strengths_weaknesses(
    phase_econ: dict, career: dict, vs_opp: dict
) -> tuple:
    strengths = []
    weaknesses = []

    pp_econ = phase_econ.get("powerplay")
    mid_econ = phase_econ.get("middle")
    death_econ = phase_econ.get("death")

    if pp_econ and pp_econ < 7.0:
        strengths.append("Excellent in powerplay")
    if mid_econ and mid_econ < 6.5:
        strengths.append("Restrictive in middle overs")
    if death_econ and death_econ < 8.5:
        strengths.append("Effective death bowler")
    if career.get("economy", 0) > 0 and career["economy"] < 7.5:
        strengths.append("Economical bowler")
    if career.get("wickets", 0) > 0 and career.get("matches", 0) > 0:
        wpm = career["wickets"] / career["matches"]
        if wpm > 1.5:
            strengths.append("Consistent wicket-taker")

    if death_econ and death_econ > 10:
        weaknesses.append("Expensive in death overs")
    if pp_econ and pp_econ > 9:
        weaknesses.append("Leaky in powerplay")
    if vs_opp.get("economy", 0) > 9 and vs_opp.get("wickets", 0) < 2:
        weaknesses.append("Struggles against this opposition")

    return strengths[:3], weaknesses[:3]


# -----------------------------------------------------------------------
# Venue phase analysis
# -----------------------------------------------------------------------

def _venue_phase_stats(db: Session, venue_id: int) -> dict:
    from sqlalchemy import Integer as SAInteger
    match_ids = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()
    phases = {"powerplay": POWERPLAY, "middle": MIDDLE, "death": DEATH}
    result = {}
    for phase_name, (os, oe) in phases.items():
        r = db.query(
            func.sum(Delivery.runs_total).label("total_runs"),
            func.count(case((Delivery.wicket_kind != None, Delivery.id))).label("total_wickets"),
            func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("total_balls"),
        ).filter(
            Delivery.match_id.in_(db.query(match_ids.c.id)),
            Delivery.over_num >= os,
            Delivery.over_num <= oe,
        ).first()

        # Count distinct innings using match_id * 10 + innings
        innings_q = db.query(
            func.count(func.distinct(
                func.cast(Delivery.match_id, SAInteger) * 10 + Delivery.innings
            ))
        ).filter(
            Delivery.match_id.in_(db.query(match_ids.c.id)),
            Delivery.over_num >= os,
            Delivery.over_num <= oe,
        ).scalar() or 1

        total_runs = r.total_runs or 0 if r else 0
        total_wickets = r.total_wickets or 0 if r else 0
        total_balls = r.total_balls or 0 if r else 0
        avg_runs = round(total_runs / max(innings_q, 1), 1)
        avg_wickets = round(total_wickets / max(innings_q, 1), 1)
        avg_rr = round(total_runs / max(total_balls / 6.0, 0.1), 1) if total_balls > 0 else 0

        result[phase_name] = {
            "avg_runs": avg_runs,
            "avg_wickets": avg_wickets,
            "avg_rr": avg_rr,
        }
    return result


def _venue_pace_spin_pct(db: Session, venue_id: int) -> tuple:
    match_ids = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()
    pace = db.query(func.count(Delivery.id)).join(
        Player, Delivery.bowler_id == Player.id
    ).filter(
        Delivery.match_id.in_(db.query(match_ids.c.id)),
        Delivery.wicket_kind != None,
        or_(Player.bowling_style.like("%fast%"), Player.bowling_style.like("%medium%")),
    ).scalar() or 0

    spin = db.query(func.count(Delivery.id)).join(
        Player, Delivery.bowler_id == Player.id
    ).filter(
        Delivery.match_id.in_(db.query(match_ids.c.id)),
        Delivery.wicket_kind != None,
        or_(
            Player.bowling_style.like("%spin%"),
            Player.bowling_style.like("%leg%"),
            Player.bowling_style.like("%off%"),
            Player.bowling_style.like("%orthodox%"),
        ),
    ).scalar() or 0

    total = pace + spin
    return (
        round(pace / max(total, 1) * 100, 1),
        round(spin / max(total, 1) * 100, 1),
    )


def _venue_toss_stats(db: Session, venue_id: int) -> float:
    """Percentage of toss winners who chose to bat first."""
    matches = db.query(Match).filter(
        Match.venue_id == venue_id,
        Match.toss_decision != None,
    ).all()
    if not matches:
        return 50.0
    bat_first = sum(1 for m in matches if m.toss_decision == "bat")
    return round(bat_first / len(matches) * 100, 1)


# -----------------------------------------------------------------------
# Matchup matrix
# -----------------------------------------------------------------------

def _build_matchup_matrix(
    db: Session,
    batters: List[dict],
    bowlers: List[dict],
) -> List[dict]:
    matrix = []
    for bat in batters[:6]:  # top 6 batters
        for bowl in bowlers[:6]:  # top 6 bowlers
            record = db.query(BatterVsBowler).filter(
                BatterVsBowler.batter_id == bat["player_id"],
                BatterVsBowler.bowler_id == bowl["player_id"],
            ).first()
            if record and record.balls >= 6:
                sr = round(record.runs / record.balls * 100, 1) if record.balls > 0 else 0
                threat = "low"
                if record.dismissals >= 2 and sr < 110:
                    threat = "high"
                elif record.dismissals >= 1 or sr < 100:
                    threat = "medium"
                matrix.append({
                    "batter": bat["name"],
                    "batter_id": bat["player_id"],
                    "bowler": bowl["name"],
                    "bowler_id": bowl["player_id"],
                    "balls": record.balls,
                    "runs": record.runs,
                    "sr": sr,
                    "dismissals": record.dismissals,
                    "dots": record.dots,
                    "boundaries": record.fours + record.sixes,
                    "threat_level": threat,
                })
    return matrix


# -----------------------------------------------------------------------
# Win prediction (simplified model)
# -----------------------------------------------------------------------

def _predict_winner(
    h2h: dict,
    team1_id: int, team2_id: int,
    venue_stats: Optional[dict],
    toss_rec: dict,
    db: Session,
) -> dict:
    # Base: 50-50
    t1_score = 50.0
    factors = []

    # H2H factor
    total = h2h.get("total_matches", 0)
    if total > 5:
        t1_wins = h2h.get("team1_wins", 0)
        t2_wins = h2h.get("team2_wins", 0)
        t1_h2h_pct = t1_wins / max(total, 1) * 100
        diff = (t1_h2h_pct - 50) * 0.3
        t1_score += diff
        if abs(diff) > 3:
            winner = "team1" if diff > 0 else "team2"
            factors.append(f"Head-to-head record favors {'Team 1' if diff > 0 else 'Team 2'} ({t1_wins}-{t2_wins})")

    # Recent form
    team1_q = db.query(Match).filter(
        or_(Match.team1_id == team1_id, Match.team2_id == team1_id),
        Match.winner_id != None,
    ).order_by(Match.date.desc()).limit(5).all()
    t1_recent_wins = sum(1 for m in team1_q if m.winner_id == team1_id)

    team2_q = db.query(Match).filter(
        or_(Match.team1_id == team2_id, Match.team2_id == team2_id),
        Match.winner_id != None,
    ).order_by(Match.date.desc()).limit(5).all()
    t2_recent_wins = sum(1 for m in team2_q if m.winner_id == team2_id)

    form_diff = (t1_recent_wins - t2_recent_wins) * 2.5
    t1_score += form_diff
    if abs(form_diff) > 3:
        factors.append(f"Recent form: Team 1 won {t1_recent_wins}/5, Team 2 won {t2_recent_wins}/5")

    # Venue factor
    if venue_stats and venue_stats.get("bat_first_win_pct", 50) != 50:
        factors.append(f"Venue bat-first win rate: {venue_stats['bat_first_win_pct']}%")

    t1_score = max(20, min(80, t1_score))
    t2_score = 100 - t1_score

    if not factors:
        factors.append("Both teams are evenly matched")

    return {
        "team1_prob": round(t1_score, 1),
        "team2_prob": round(t2_score, 1),
        "key_factors": factors,
    }


# -----------------------------------------------------------------------
# Main team analysis builder
# -----------------------------------------------------------------------

def _build_team_analysis(
    db: Session,
    team_short: str,
    opp_short: str,
    opp_team_id: int,
    venue_id: int,
    name_meta: dict,
    unavailable_player_ids: set[int] | None = None,
) -> dict:
    squad_data = get_squad_data(db)
    if team_short not in squad_data:
        return {"error": f"Team {team_short} not found"}

    # Get playing 11
    xi_result = select_playing_11(db, team_short, opp_short, venue_id, unavailable_player_ids=unavailable_player_ids)
    playing_11 = xi_result.get("playing_11", [])
    impact_bat = xi_result.get("impact_player_batting")
    impact_bowl = xi_result.get("impact_player_bowling")

    # Squad composition
    comp = {"wk": 0, "batters": 0, "allrounders": 0, "bowlers": 0, "overseas": 0}
    for p in playing_11:
        role = (p.get("role") or "").lower()
        country = p.get("country", "India")
        if "wk" in role:
            comp["wk"] += 1
        elif role in ("batsman", "batter"):
            comp["batters"] += 1
        elif "allrounder" in role:
            comp["allrounders"] += 1
        elif "bowler" in role:
            comp["bowlers"] += 1
        if country not in ("India", "india", "", None):
            comp["overseas"] += 1

    # Build detailed batter profiles
    top_batters = []
    top_bowlers = []

    for p in playing_11:
        pid = p["player_id"]
        role = (p.get("role") or "").lower()
        is_batter = "wk" in role or role in ("batsman", "batter") or "batting allrounder" in role
        is_bowler = "bowler" in role or "bowling allrounder" in role

        if is_batter:
            career = _career_batting(db, pid)
            vs_opp = _batting_vs_opposition(db, pid, opp_team_id)
            at_venue = _batting_at_venue(db, pid, venue_id)
            pp_sr = _phase_sr(db, pid, POWERPLAY[0], POWERPLAY[1])
            mid_sr = _phase_sr(db, pid, MIDDLE[0], MIDDLE[1])
            death_sr_val = _phase_sr(db, pid, DEATH[0], DEATH[1])
            recent = _recent_scores(db, pid)
            form_index = round(sum(recent) / max(len(recent), 1), 1) if recent else 0

            phase_data = {"powerplay": pp_sr, "middle": mid_sr, "death": death_sr_val}
            strengths, weaknesses = _batter_strengths_weaknesses(phase_data, vs_opp, career)

            top_batters.append({
                "name": p["name"],
                "player_id": pid,
                "role": p.get("role", ""),
                "career": career,
                "vs_opposition": vs_opp,
                "at_venue": at_venue,
                "phase_sr": phase_data,
                "recent_form": {"last_5_scores": recent, "form_index": form_index},
                "strengths": strengths,
                "weaknesses": weaknesses,
            })

        if is_bowler:
            career = _career_bowling(db, pid)
            vs_opp = _bowling_vs_opposition(db, pid, opp_team_id)
            at_venue = _bowling_at_venue(db, pid, venue_id)
            pp_econ = _phase_econ(db, pid, POWERPLAY[0], POWERPLAY[1])
            mid_econ = _phase_econ(db, pid, MIDDLE[0], MIDDLE[1])
            death_econ = _phase_econ(db, pid, DEATH[0], DEATH[1])

            phase_data = {"powerplay": pp_econ, "middle": mid_econ, "death": death_econ}
            strengths, weaknesses = _bowler_strengths_weaknesses(phase_data, career, vs_opp)

            player_obj = db.get(Player, pid)
            top_bowlers.append({
                "name": p["name"],
                "player_id": pid,
                "role": p.get("role", ""),
                "bowling_style": player_obj.bowling_style if player_obj else "",
                "career": career,
                "vs_opposition": vs_opp,
                "at_venue": at_venue,
                "phase_economy": phase_data,
                "strengths": strengths,
                "weaknesses": weaknesses,
            })

    return {
        "playing_11": playing_11,
        "impact_player_batting": impact_bat,
        "impact_player_bowling": impact_bowl,
        "squad_composition": comp,
        "top_batters": top_batters,
        "top_bowlers": top_bowlers,
    }


# -----------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------

@router.post("/analysis/match")
def match_analysis(req: MatchAnalysisRequest, db: Session = Depends(get_db)):
    """
    Comprehensive match analysis endpoint.

    Returns everything the frontend needs: head-to-head, team analyses,
    matchup matrix, venue analysis, toss recommendation, and win prediction.
    """
    squad_data = get_squad_data(db)
    name_meta = get_player_meta(db)

    # Resolve teams
    t1_info = squad_data.get(req.team1)
    t2_info = squad_data.get(req.team2)
    if not t1_info or not t2_info:
        available = list(squad_data.keys())
        return {"error": f"Team not found. Available: {available}"}

    team1_id = t1_info["team_id"]
    team2_id = t2_info["team_id"]

    team1 = db.get(Team, team1_id)
    team2 = db.get(Team, team2_id)
    venue = db.get(Venue, req.venue_id)

    if not team1 or not team2:
        return {"error": "Team not found in database"}

    # --- Fetch latest news for both teams (injuries, fitness, conditions) ---
    t1_player_names = get_squad_player_names(db, req.team1)
    t2_player_names = get_squad_player_names(db, req.team2)

    team1_news = fetch_player_news(team1.name, t1_player_names)
    team2_news = fetch_player_news(team2.name, t2_player_names)

    t1_name_id = _name_to_id_map(db, req.team1)
    t2_name_id = _name_to_id_map(db, req.team2)

    # Build set of unavailable player IDs (injured/ruled_out) per team
    t1_unavailable_ids: set[int] = set()
    t2_unavailable_ids: set[int] = set()
    for news, name_id, unavail in [
        (team1_news, t1_name_id, t1_unavailable_ids),
        (team2_news, t2_name_id, t2_unavailable_ids),
    ]:
        for update in news.get("player_updates", []):
            if update.get("status") in UNAVAILABLE_STATUSES:
                pid = name_id.get(update["name"].lower())
                if pid is not None:
                    unavail.add(pid)

    # --- Head to head ---
    h2h_raw = get_head_to_head(db, team1_id, team2_id)
    recent_5_winners = []
    for rm in h2h_raw.get("recent_matches", []):
        w = rm.get("winner", "")
        if w == team1.name:
            recent_5_winners.append(req.team1)
        elif w == team2.name:
            recent_5_winners.append(req.team2)
        else:
            recent_5_winners.append("no_result")

    head_to_head = {
        "total_matches": h2h_raw.get("total_matches", 0),
        "team1_wins": h2h_raw.get("team1_wins", 0),
        "team2_wins": h2h_raw.get("team2_wins", 0),
        "recent_5": recent_5_winners,
    }

    # --- Venue stats ---
    v_stats = get_venue_stats(db, req.venue_id)
    pace_pct, spin_pct = _venue_pace_spin_pct(db, req.venue_id)
    phase_avgs = _venue_phase_stats(db, req.venue_id)
    toss_bat_pct = _venue_toss_stats(db, req.venue_id)

    venue_analysis = {
        "avg_first_innings": round(v_stats["avg_first_innings_score"], 1) if v_stats else 160,
        "avg_second_innings": round(v_stats["avg_second_innings_score"], 1) if v_stats else 150,
        "bat_first_win_pct": round(v_stats["bat_first_win_pct"], 1) if v_stats else 50,
        "pace_wickets_pct": pace_pct,
        "spin_wickets_pct": spin_pct,
        "phase_averages": phase_avgs,
        "toss_bat_first_pct": toss_bat_pct,
        "highest_score": v_stats["highest_score"] if v_stats else 0,
        "lowest_score": v_stats["lowest_score"] if v_stats else 0,
    }

    # --- Team analyses ---
    team1_analysis = _build_team_analysis(db, req.team1, req.team2, team2_id, req.venue_id, name_meta, t1_unavailable_ids)
    team2_analysis = _build_team_analysis(db, req.team2, req.team1, team1_id, req.venue_id, name_meta, t2_unavailable_ids)

    # --- Matchup matrix ---
    t1_batters = team1_analysis.get("top_batters", [])
    t1_bowlers = team1_analysis.get("top_bowlers", [])
    t2_batters = team2_analysis.get("top_batters", [])
    t2_bowlers = team2_analysis.get("top_bowlers", [])

    matchup_matrix = {
        "team1_batters_vs_team2_bowlers": _build_matchup_matrix(db, t1_batters, t2_bowlers),
        "team2_batters_vs_team1_bowlers": _build_matchup_matrix(db, t2_batters, t1_bowlers),
    }

    # --- Toss recommendation ---
    toss1 = recommend_toss_decision(db, req.team1, req.team2, req.venue_id)
    toss2 = recommend_toss_decision(db, req.team2, req.team1, req.venue_id)

    toss_recommendation = {
        "team1": {
            "decision": toss1.get("recommendation", "bat"),
            "confidence": toss1.get("confidence", 50),
            "reasoning": toss1.get("reasoning", []),
        },
        "team2": {
            "decision": toss2.get("recommendation", "bat"),
            "confidence": toss2.get("confidence", 50),
            "reasoning": toss2.get("reasoning", []),
        },
    }

    # --- Prediction ---
    prediction = _predict_winner(head_to_head, team1_id, team2_id, v_stats, toss1, db)

    return {
        "team1": {"name": team1.name, "short_name": req.team1},
        "team2": {"name": team2.name, "short_name": req.team2},
        "venue": {
            "name": venue.name if venue else f"Venue {req.venue_id}",
            "city": venue.city if venue else None,
            "stats": venue_analysis,
        },
        "head_to_head": head_to_head,
        "team1_news": team1_news,
        "team2_news": team2_news,
        "team1_analysis": team1_analysis,
        "team2_analysis": team2_analysis,
        "matchup_matrix": matchup_matrix,
        "venue_analysis": venue_analysis,
        "toss_recommendation": toss_recommendation,
        "prediction": prediction,
    }
