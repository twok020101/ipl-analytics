"""
Match Strategy Engine for IPL Analytics.

Provides intelligent team selection, toss decision, game plan creation,
and live in-match strategy adjustments based on historical ball-by-ball data.

All strategies respect official IPL 2026 playing rules.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, cast, Integer, Float

from app.models.models import (
    Team,
    Player,
    Venue,
    Match,
    Delivery,
    PlayerSeasonBatting,
    PlayerSeasonBowling,
    BatterVsBowler,
    VenueStats,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# ---------------------------------------------------------------------------
# IPL 2026 Official Rules
# ---------------------------------------------------------------------------
# Sources: BCCI IPL Playing Conditions, cricketcounsel.com, timesofsports.com

IPL_RULES = {
    # Team Composition
    "PLAYING_XI_SIZE": 11,
    "MAX_SQUAD_SIZE": 25,
    "MAX_OVERSEAS_IN_XI": 4,                # Max 4 overseas players on field at any time
    "MAX_OVERSEAS_IN_SQUAD": 8,             # Max 8 overseas in 25-man squad
    "MAX_OVERSEAS_IF_IMPACT_OVERSEAS": 3,   # If impact player is overseas, XI must have only 3

    # Impact Player Rule
    "IMPACT_PLAYER_ENABLED": True,
    "IMPACT_SUBSTITUTES_DECLARED": 5,       # 5 substitute names declared 30 min before toss
    "MAX_IMPACT_PLAYERS_PER_MATCH": 1,      # Only 1 substitution per match
    # Substitution timing: before innings, after wicket, at over completion, batter retires
    # Replaced player exits permanently, cannot return

    # Bowling Restrictions
    "MAX_OVERS_PER_BOWLER": 4,              # Each bowler can bowl maximum 4 overs
    "TOTAL_OVERS": 20,                      # T20 format
    "MIN_BOWLERS_NEEDED": 5,                # Need at least 5 bowlers to cover 20 overs (5 × 4 = 20)
    "MAX_BOUNCERS_PER_OVER": 2,             # Max 2 short-pitched above shoulder per over
    # 3rd bouncer = no-ball + free hit
    # Above head height = automatic no-ball regardless of count

    # Fielding Restrictions
    "POWERPLAY_OVERS": (1, 6),              # Overs 1-6
    "PP_MAX_FIELDERS_OUTSIDE_CIRCLE": 2,    # Max 2 outside 30-yard circle in powerplay
    "NORMAL_MAX_FIELDERS_OUTSIDE_CIRCLE": 5, # Max 5 outside circle in overs 7-20
    "OVER_RATE_PENALTY_FIELDERS": 4,        # If 20th over not started in 90 min, max 4 outside
    "OVER_RATE_TIME_LIMIT_MINUTES": 90,     # Must start 20th over within 90 minutes

    # Strategic Timeout
    "TIMEOUT_1_WINDOW": (6, 9),             # After over 6, before over 10 — bowling team
    "TIMEOUT_2_WINDOW": (13, 16),           # After over 13, before over 17 — batting team
    "TIMEOUT_DURATION_SECONDS": 150,        # 2 minutes 30 seconds

    # DRS
    "DRS_REVIEWS_PER_INNINGS": 2,           # 2 reviews per team per innings
    "DRS_SIGNAL_TIME_SECONDS": 15,          # 15 seconds to signal review
    # Successful review / umpire's call = review retained
    # Can review wides and no-balls (IPL-specific since 2023)

    # Super Over (tiebreaker)
    "SUPER_OVER_BALLS": 6,                  # 1 over = 6 balls
    "SUPER_OVER_BATTERS": 3,                # Each team selects 3 batters
    "SUPER_OVER_BOWLER_REUSE": False,       # Cannot reuse bowler from previous super over
    # Unlimited super overs until winner decided

    # Phases (for strategy)
    "PHASE_POWERPLAY": (0, 5),              # Overs 0-5 (0-indexed: actual overs 1-6)
    "PHASE_MIDDLE": (6, 14),                # Overs 6-14 (actual overs 7-15)
    "PHASE_DEATH": (15, 19),                # Overs 15-19 (actual overs 16-20)
}

# Convenience aliases
MAX_OVERSEAS = IPL_RULES["MAX_OVERSEAS_IN_XI"]
MAX_OVERS_PER_BOWLER = IPL_RULES["MAX_OVERS_PER_BOWLER"]
MIN_BOWLERS = IPL_RULES["MIN_BOWLERS_NEEDED"]
PLAYING_XI_SIZE = IPL_RULES["PLAYING_XI_SIZE"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_squad_data() -> dict:
    """Load team_squads_2026.json mapping team short_name -> player_ids."""
    path = DATA_DIR / "team_squads_2026.json"
    with open(path) as f:
        return json.load(f)


def _load_ipl2026_data() -> dict:
    """Load ipl2026.json with full player metadata (country, role, etc.)."""
    path = DATA_DIR / "ipl2026.json"
    with open(path) as f:
        return json.load(f)


def _build_name_to_meta() -> Dict[str, dict]:
    """Build a mapping from player name -> {country, role, ...} from ipl2026.json."""
    data = _load_ipl2026_data()
    mapping: Dict[str, dict] = {}
    for _team_key, team_data in data.get("squads", {}).items():
        for p in team_data.get("players", []):
            mapping[p["name"]] = {
                "country": p.get("country", "India"),
                "role": p.get("role", "Unknown"),
                "batting_style": p.get("battingStyle", ""),
                "bowling_style": p.get("bowlingStyle", ""),
            }
    return mapping


def _is_overseas(country: str) -> bool:
    return country not in ("India", "india", "", None)


def _is_wicketkeeper(role: str) -> bool:
    return role and "WK" in role.upper()


def _is_bowler(role: str) -> bool:
    if not role:
        return False
    r = role.lower()
    return "bowler" in r or "bowling allrounder" in r


def _is_batting_allrounder(role: str) -> bool:
    if not role:
        return False
    return "batting allrounder" in role.lower()


def _is_bowling_allrounder(role: str) -> bool:
    if not role:
        return False
    return "bowling allrounder" in role.lower()


def _is_pure_batsman(role: str) -> bool:
    if not role:
        return False
    r = role.lower()
    return r == "batsman" or r == "batter"


def _is_pure_bowler(role: str) -> bool:
    if not role:
        return False
    r = role.lower()
    return r == "bowler"


def _can_bowl(role: str, bowling_style: str) -> bool:
    """Check if a player can realistically contribute as a bowling option."""
    if not role:
        return False
    r = role.lower()
    if "bowler" in r or "bowling allrounder" in r:
        return True
    if "batting allrounder" in r:
        return True
    return False


def _can_bowl_parttime(role: str, bowling_style: str) -> bool:
    """Check if a player can bowl even part-time (includes batsmen with bowling style)."""
    if _can_bowl(role, bowling_style):
        return True
    if bowling_style and bowling_style.strip() and "unknown" not in bowling_style.lower():
        return True
    return False


def _phase_economy(db: Session, bowler_id: int, over_start: int, over_end: int) -> Optional[float]:
    """Calculate economy rate for a bowler in a specific phase."""
    result = db.query(
        func.sum(Delivery.runs_total).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
    ).filter(
        Delivery.bowler_id == bowler_id,
        Delivery.over_num >= over_start,
        Delivery.over_num <= over_end,
    ).first()
    if result and result.balls and result.balls > 0:
        return float(result.runs) / (float(result.balls) / 6.0)
    return None


def _phase_batting_sr(db: Session, batter_id: int, over_start: int, over_end: int) -> Optional[float]:
    """Calculate strike rate for a batter in a specific phase."""
    result = db.query(
        func.sum(Delivery.runs_batter).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
    ).filter(
        Delivery.batter_id == batter_id,
        Delivery.over_num >= over_start,
        Delivery.over_num <= over_end,
    ).first()
    if result and result.balls and result.balls > 0:
        return float(result.runs) / float(result.balls) * 100.0
    return None


def _venue_phase_avg(db: Session, venue_id: int, over_start: int, over_end: int) -> Optional[float]:
    """Average runs scored per innings in a phase at a venue."""
    # Get match_ids at this venue
    match_ids_q = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()
    result = db.query(
        func.sum(Delivery.runs_total).label("total_runs"),
        func.count(func.distinct(
            func.cast(Delivery.match_id, Integer).op("*")(10).op("+")(Delivery.innings)
        )).label("innings_count"),
    ).filter(
        Delivery.match_id.in_(db.query(match_ids_q.c.id)),
        Delivery.over_num >= over_start,
        Delivery.over_num <= over_end,
    ).first()
    if result and result.innings_count and result.innings_count > 0:
        return float(result.total_runs) / float(result.innings_count)
    return None


def _player_venue_score(db: Session, player_id: int, venue_id: int) -> dict:
    """Get a player's batting and bowling performance at a specific venue."""
    match_ids_q = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()

    # Batting at venue
    bat_result = db.query(
        func.sum(Delivery.runs_batter).label("runs"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
        func.count(case((Delivery.wicket_kind != None, 1))).label("dismissals"),
    ).filter(
        Delivery.batter_id == player_id,
        Delivery.match_id.in_(db.query(match_ids_q.c.id)),
    ).first()

    bat_runs = bat_result.runs or 0 if bat_result else 0
    bat_balls = bat_result.balls or 0 if bat_result else 0
    bat_sr = (bat_runs / bat_balls * 100) if bat_balls > 0 else 0

    # Bowling at venue
    bowl_result = db.query(
        func.sum(Delivery.runs_total).label("runs_conceded"),
        func.sum(case((Delivery.valid_ball == True, 1), else_=0)).label("balls"),
        func.count(case((Delivery.wicket_kind != None, 1))).label("wickets"),
    ).filter(
        Delivery.bowler_id == player_id,
        Delivery.match_id.in_(db.query(match_ids_q.c.id)),
    ).first()

    bowl_runs = bowl_result.runs_conceded or 0 if bowl_result else 0
    bowl_balls = bowl_result.balls or 0 if bowl_result else 0
    bowl_wickets = bowl_result.wickets or 0 if bowl_result else 0
    bowl_econ = (bowl_runs / (bowl_balls / 6.0)) if bowl_balls > 0 else 0

    return {
        "bat_runs": bat_runs,
        "bat_balls": bat_balls,
        "bat_sr": round(bat_sr, 1),
        "bowl_runs": bowl_runs,
        "bowl_balls": bowl_balls,
        "bowl_wickets": bowl_wickets,
        "bowl_econ": round(bowl_econ, 2),
    }


def _get_batting_stats(db: Session, player_id: int, seasons: int = 3) -> dict:
    """Get batting stats from last N seasons."""
    stats = (
        db.query(PlayerSeasonBatting)
        .filter(PlayerSeasonBatting.player_id == player_id)
        .order_by(PlayerSeasonBatting.season.desc())
        .limit(seasons)
        .all()
    )
    if not stats:
        return {"avg": 0, "sr": 0, "runs_per_inn": 0, "innings": 0, "seasons": 0}

    total_runs = sum(s.runs for s in stats)
    total_innings = sum(s.innings for s in stats)
    total_balls = sum(s.balls_faced for s in stats)

    # Weight recent seasons higher
    weighted_avg = 0
    weighted_sr = 0
    total_weight = 0
    for i, s in enumerate(stats):
        weight = seasons - i  # most recent = highest weight
        weighted_avg += s.average * weight
        weighted_sr += s.strike_rate * weight
        total_weight += weight

    if total_weight > 0:
        weighted_avg /= total_weight
        weighted_sr /= total_weight

    return {
        "avg": round(weighted_avg, 2),
        "sr": round(weighted_sr, 2),
        "runs_per_inn": round(total_runs / max(total_innings, 1), 2),
        "innings": total_innings,
        "seasons": len(stats),
        "total_runs": total_runs,
    }


def _get_bowling_stats(db: Session, player_id: int, seasons: int = 3) -> dict:
    """Get bowling stats from last N seasons."""
    stats = (
        db.query(PlayerSeasonBowling)
        .filter(PlayerSeasonBowling.player_id == player_id)
        .order_by(PlayerSeasonBowling.season.desc())
        .limit(seasons)
        .all()
    )
    if not stats:
        return {"economy": 99, "wickets_per_match": 0, "wickets": 0, "matches": 0, "seasons": 0}

    total_wickets = sum(s.wickets for s in stats)
    total_matches = sum(s.matches for s in stats)

    weighted_econ = 0
    total_weight = 0
    for i, s in enumerate(stats):
        weight = seasons - i
        weighted_econ += s.economy * weight
        total_weight += weight

    if total_weight > 0:
        weighted_econ /= total_weight

    return {
        "economy": round(weighted_econ, 2),
        "wickets_per_match": round(total_wickets / max(total_matches, 1), 2),
        "wickets": total_wickets,
        "matches": total_matches,
        "seasons": len(stats),
    }


def _matchup_score_vs_team(db: Session, player_id: int, opposition_player_ids: List[int], as_batter: bool) -> float:
    """
    Compute average matchup advantage for a player against opposition.
    Returns a factor: >1 means advantage, <1 means disadvantage.
    """
    if not opposition_player_ids:
        return 1.0

    if as_batter:
        matchups = db.query(BatterVsBowler).filter(
            BatterVsBowler.batter_id == player_id,
            BatterVsBowler.bowler_id.in_(opposition_player_ids),
        ).all()
    else:
        matchups = db.query(BatterVsBowler).filter(
            BatterVsBowler.bowler_id == player_id,
            BatterVsBowler.batter_id.in_(opposition_player_ids),
        ).all()

    if not matchups:
        return 1.0

    total_balls = sum(m.balls for m in matchups)
    total_runs = sum(m.runs for m in matchups)
    total_dismissals = sum(m.dismissals for m in matchups)

    if total_balls < 6:
        return 1.0

    sr = (total_runs / total_balls) * 100 if total_balls > 0 else 0

    if as_batter:
        # Good batting = high SR
        return min(max(sr / 130.0, 0.5), 1.5)
    else:
        # Good bowling = low SR conceded + dismissals
        dismiss_rate = total_dismissals / (total_balls / 6.0)
        econ = total_runs / (total_balls / 6.0)
        # Better economy and more wickets = higher score
        bowl_factor = (8.0 / max(econ, 4.0)) * (1 + dismiss_rate * 0.3)
        return min(max(bowl_factor, 0.5), 1.5)


# ---------------------------------------------------------------------------
# 1. Select Playing 11
# ---------------------------------------------------------------------------

def select_playing_11(
    db: Session,
    team_short_name: str,
    opposition_short_name: str,
    venue_id: int,
    season: str = "2026",
) -> dict:
    """
    Selects optimal playing 11 + impact player from the 25-26 man squad.

    Constraints:
    - 1-2 WK-Batsman
    - Minimum 5 bowling options
    - Maximum 4 overseas players
    - At least 5 specialist batters (incl WK), at least 4 specialist bowlers
    """
    squad_data = _load_squad_data()
    name_meta = _build_name_to_meta()

    if team_short_name not in squad_data:
        return {"error": f"Team {team_short_name} not found in squad data"}

    team_info = squad_data[team_short_name]
    player_ids = team_info["player_ids"]

    # Get opposition player IDs for matchup analysis
    opp_player_ids = []
    if opposition_short_name in squad_data:
        opp_player_ids = squad_data[opposition_short_name]["player_ids"]

    # Build player profiles with scores
    player_profiles = []
    for pid in player_ids:
        player = db.get(Player, pid)
        if not player:
            continue

        meta = name_meta.get(player.name, {})
        country = meta.get("country", "India")
        role = player.role or meta.get("role", "Unknown")
        batting_style = player.batting_style or meta.get("batting_style", "")
        bowling_style = player.bowling_style or meta.get("bowling_style", "")

        # Get stats
        bat_stats = _get_batting_stats(db, pid)
        bowl_stats = _get_bowling_stats(db, pid)
        venue_perf = _player_venue_score(db, pid, venue_id)

        # Matchup factor
        bat_matchup = _matchup_score_vs_team(db, pid, opp_player_ids, as_batter=True)
        bowl_matchup = _matchup_score_vs_team(db, pid, opp_player_ids, as_batter=False)

        # Compute composite score
        has_bat_data = bat_stats["innings"] > 0
        has_bowl_data = bowl_stats["matches"] > 0 and bowl_stats["economy"] < 50

        bat_score = 0
        if has_bat_data:
            bat_score = (
                bat_stats["avg"] * 0.4
                + bat_stats["sr"] * 0.3
                + bat_stats["runs_per_inn"] * 0.3
            ) * bat_matchup
            # Venue bonus
            if venue_perf["bat_balls"] >= 12:
                venue_bat_factor = min(venue_perf["bat_sr"] / 130.0, 1.3)
                bat_score *= venue_bat_factor

        bowl_score = 0
        if has_bowl_data:
            bowl_score = (
                max(0, (10 - bowl_stats["economy"])) * 10
                + bowl_stats["wickets_per_match"] * 20
            ) * bowl_matchup
            # Venue bonus
            if venue_perf["bowl_balls"] >= 12:
                venue_bowl_factor = min(8.0 / max(venue_perf["bowl_econ"], 4.0), 1.3)
                bowl_score *= venue_bowl_factor

        # Role-based fallback for players with no historical data
        # This ensures proper team composition even when data is sparse
        if not has_bat_data and not has_bowl_data:
            if _is_pure_batsman(role) or _is_wicketkeeper(role):
                bat_score = 35.0  # Decent assumed batting baseline
                bowl_score = 0.0
            elif _is_pure_bowler(role):
                bat_score = 2.0
                bowl_score = 30.0  # Decent assumed bowling baseline
            elif _is_bowling_allrounder(role):
                bat_score = 10.0
                bowl_score = 25.0
            elif _is_batting_allrounder(role):
                bat_score = 28.0
                bowl_score = 12.0
            else:
                bat_score = 15.0
                bowl_score = 15.0

        # Combined score based on role
        if _is_pure_batsman(role) or _is_wicketkeeper(role):
            composite = bat_score * 0.85 + bowl_score * 0.15
        elif _is_pure_bowler(role):
            composite = bat_score * 0.15 + bowl_score * 0.85
        elif _is_bowling_allrounder(role):
            composite = bat_score * 0.35 + bowl_score * 0.65
        elif _is_batting_allrounder(role):
            composite = bat_score * 0.65 + bowl_score * 0.35
        else:
            composite = bat_score * 0.5 + bowl_score * 0.5

        # Recent form bonus: if they have recent season data, small boost
        if bat_stats["seasons"] >= 2 or bowl_stats["seasons"] >= 2:
            composite *= 1.05

        # Experience bonus for players with more innings
        if bat_stats["innings"] > 50 or bowl_stats["matches"] > 40:
            composite *= 1.03

        reasoning_parts = []
        if bat_stats["innings"] > 0:
            reasoning_parts.append(f"Bat avg {bat_stats['avg']}, SR {bat_stats['sr']}")
        if bowl_stats["matches"] > 0 and bowl_stats["economy"] < 50:
            reasoning_parts.append(f"Bowl econ {bowl_stats['economy']}, wpm {bowl_stats['wickets_per_match']}")
        if venue_perf["bat_balls"] >= 12 or venue_perf["bowl_balls"] >= 12:
            reasoning_parts.append(f"Venue: {venue_perf['bat_runs']}r/{venue_perf['bat_balls']}b bat, {venue_perf['bowl_wickets']}w bowl")
        if bat_matchup != 1.0:
            reasoning_parts.append(f"Bat matchup factor {bat_matchup:.2f}")
        if bowl_matchup != 1.0:
            reasoning_parts.append(f"Bowl matchup factor {bowl_matchup:.2f}")
        if not reasoning_parts:
            reasoning_parts.append("Limited historical data; selected on role-based estimate")

        player_profiles.append({
            "player_id": pid,
            "name": player.name,
            "role": role,
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "country": country,
            "is_overseas": _is_overseas(country),
            "is_wk": _is_wicketkeeper(role),
            "can_bowl": _can_bowl(role, bowling_style),
            "is_pure_bowler": _is_pure_bowler(role),
            "is_pure_batsman": _is_pure_batsman(role) or _is_wicketkeeper(role),
            "score": round(composite, 2),
            "bat_score": round(bat_score, 2),
            "bowl_score": round(bowl_score, 2),
            "reasoning": "; ".join(reasoning_parts),
        })

    # Sort by composite score descending
    player_profiles.sort(key=lambda x: x["score"], reverse=True)

    # --- Selection algorithm with constraints ---
    selected: List[dict] = []
    remaining = list(player_profiles)

    overseas_count = 0
    wk_count = 0
    bowling_options = 0
    batters_count = 0  # includes WK
    bowlers_count = 0  # pure bowlers

    def _can_add(p: dict) -> bool:
        nonlocal overseas_count, wk_count
        if p["is_overseas"] and overseas_count >= MAX_OVERSEAS:
            return False
        if p["is_wk"] and wk_count >= 2:
            return False
        return True

    def _add(p: dict):
        nonlocal overseas_count, wk_count, bowling_options, batters_count, bowlers_count
        selected.append(p)
        if p["is_overseas"]:
            overseas_count += 1
        if p["is_wk"]:
            wk_count += 1
        if p["can_bowl"]:
            bowling_options += 1
        if p["is_pure_batsman"]:
            batters_count += 1
        if p["is_pure_bowler"] or _is_bowling_allrounder(p["role"]):
            bowlers_count += 1
        remaining.remove(p)

    # Step 1: Ensure at least 1 WK
    wk_candidates = [p for p in remaining if p["is_wk"]]
    if wk_candidates:
        best_wk = max(wk_candidates, key=lambda x: x["score"])
        _add(best_wk)

    # Step 2: Ensure at least MIN_BOWLERS bowling options (pure bowler or bowling allrounder)
    # Need MIN_BOWLERS (5) bowlers since each can bowl MAX_OVERS_PER_BOWLER (4) overs = 20 overs total
    bowler_candidates = sorted(
        [p for p in remaining if (p["is_pure_bowler"] or _is_bowling_allrounder(p["role"])) and _can_add(p)],
        key=lambda x: x["score"], reverse=True,
    )
    for bc in bowler_candidates[:max(4, MIN_BOWLERS - 1)]:
        if len(selected) < 11:
            _add(bc)

    # Step 3: Fill up to 11 with best remaining players respecting constraints
    for p in list(remaining):
        if len(selected) >= 11:
            break
        if _can_add(p):
            _add(p)

    # Step 4: Validate constraints and fix if needed
    # Ensure minimum MIN_BOWLERS (5) bowling options to cover 20 overs at 4 overs each
    while bowling_options < MIN_BOWLERS and remaining:
        bowl_cands = [p for p in remaining if p["can_bowl"] and _can_add(p)]
        if not bowl_cands:
            break
        best = max(bowl_cands, key=lambda x: x["score"])
        # Swap out the weakest non-bowler
        non_bowlers = [p for p in selected if not p["can_bowl"]]
        if non_bowlers:
            weakest = min(non_bowlers, key=lambda x: x["score"])
            selected.remove(weakest)
            if weakest["is_overseas"]:
                overseas_count -= 1
            if weakest["is_wk"]:
                wk_count -= 1
            if weakest["is_pure_batsman"]:
                batters_count -= 1
            remaining.append(weakest)
            _add(best)
        else:
            break

    # Ensure at least 1 WK in final 11
    if wk_count == 0:
        wk_cands = [p for p in remaining if p["is_wk"] and _can_add(p)]
        if wk_cands:
            best_wk = max(wk_cands, key=lambda x: x["score"])
            # swap weakest non-wk
            non_wks = [p for p in selected if not p["is_wk"]]
            if non_wks:
                weakest = min(non_wks, key=lambda x: x["score"])
                selected.remove(weakest)
                if weakest["is_overseas"]:
                    overseas_count -= 1
                if weakest["can_bowl"]:
                    bowling_options -= 1
                if weakest["is_pure_batsman"]:
                    batters_count -= 1
                remaining.append(weakest)
                _add(best_wk)

    # Impact player selection
    batting_impact = None
    bowling_impact = None

    bat_candidates = [p for p in remaining if (p["is_pure_batsman"] or _is_batting_allrounder(p["role"]) or p["is_wk"]) and _can_add(p)]
    if bat_candidates:
        batting_impact = max(bat_candidates, key=lambda x: x["bat_score"])

    bowl_candidates_imp = [p for p in remaining if (p["is_pure_bowler"] or _is_bowling_allrounder(p["role"])) and _can_add(p)]
    if bowl_candidates_imp:
        bowling_impact = max(bowl_candidates_imp, key=lambda x: x["bowl_score"])

    # If no batting impact, pick next best scorer
    if not batting_impact and remaining:
        batting_impact = max(remaining, key=lambda x: x["bat_score"])
    if not bowling_impact and remaining:
        bowling_impact = max(remaining, key=lambda x: x["bowl_score"])

    selected_ids = {p["player_id"] for p in selected}
    impact_ids = set()
    if batting_impact:
        impact_ids.add(batting_impact["player_id"])
    if bowling_impact:
        impact_ids.add(bowling_impact["player_id"])

    not_selected = [
        {"player_id": p["player_id"], "name": p["name"], "role": p["role"], "country": p["country"], "score": p["score"]}
        for p in player_profiles
        if p["player_id"] not in selected_ids and p["player_id"] not in impact_ids
    ]

    # Clean output
    def _clean_player(p: dict) -> dict:
        return {
            "player_id": p["player_id"],
            "name": p["name"],
            "role": p["role"],
            "batting_style": p["batting_style"],
            "bowling_style": p["bowling_style"],
            "country": p["country"],
            "score": p["score"],
            "reasoning": p["reasoning"],
        }

    return {
        "playing_11": [_clean_player(p) for p in selected],
        "impact_player_batting": _clean_player(batting_impact) if batting_impact else None,
        "impact_player_bowling": _clean_player(bowling_impact) if bowling_impact else None,
        "squad_not_selected": not_selected,
    }


# ---------------------------------------------------------------------------
# 2. Toss Decision
# ---------------------------------------------------------------------------

def recommend_toss_decision(
    db: Session,
    team_short_name: str,
    opposition_short_name: str,
    venue_id: int,
) -> dict:
    """
    Recommend what to do if you win the toss.
    Analyzes venue stats, team strengths, and opposition tendencies.
    """
    # --- Venue Analysis ---
    venue_stats = db.query(VenueStats).filter(VenueStats.venue_id == venue_id).first()
    venue = db.get(Venue, venue_id)
    venue_name = venue.name if venue else f"Venue {venue_id}"

    bat_first_win_pct = venue_stats.bat_first_win_pct if venue_stats else 50.0
    avg_first = venue_stats.avg_first_innings_score if venue_stats else 160.0
    avg_second = venue_stats.avg_second_innings_score if venue_stats else 155.0

    # Compute pace vs spin wickets at venue
    match_ids_q = db.query(Match.id).filter(Match.venue_id == venue_id).subquery()

    # Pace wickets: bowlers with 'fast' or 'medium' in bowling_style
    pace_wickets_q = db.query(func.count(Delivery.id)).join(
        Player, Delivery.bowler_id == Player.id
    ).filter(
        Delivery.match_id.in_(db.query(match_ids_q.c.id)),
        Delivery.wicket_kind != None,
        or_(
            Player.bowling_style.like("%fast%"),
            Player.bowling_style.like("%medium%"),
        ),
    ).scalar() or 0

    spin_wickets_q = db.query(func.count(Delivery.id)).join(
        Player, Delivery.bowler_id == Player.id
    ).filter(
        Delivery.match_id.in_(db.query(match_ids_q.c.id)),
        Delivery.wicket_kind != None,
        or_(
            Player.bowling_style.like("%spin%"),
            Player.bowling_style.like("%leg%"),
            Player.bowling_style.like("%off%"),
            Player.bowling_style.like("%orthodox%"),
            Player.bowling_style.like("%chinaman%"),
        ),
    ).scalar() or 0

    total_venue_wickets = pace_wickets_q + spin_wickets_q
    pace_pct = round(pace_wickets_q / max(total_venue_wickets, 1) * 100, 1)
    spin_pct = round(spin_wickets_q / max(total_venue_wickets, 1) * 100, 1)

    # --- Team analysis ---
    squad_data = _load_squad_data()
    team_id = squad_data.get(team_short_name, {}).get("team_id")
    opp_id = squad_data.get(opposition_short_name, {}).get("team_id")

    # Team's record batting first vs chasing
    team_bat_first_wins = 0
    team_bat_first_total = 0
    team_chase_wins = 0
    team_chase_total = 0

    if team_id:
        # Matches where this team batted first (team1 in 1st innings)
        # We check toss: if team won toss and chose bat, or lost toss and opponent chose field
        team_matches = db.query(Match).filter(
            or_(Match.team1_id == team_id, Match.team2_id == team_id),
            Match.winner_id != None,
        ).all()

        for m in team_matches:
            # Determine if this team batted first
            team_batted_first = False
            if m.toss_winner_id == team_id and m.toss_decision == "bat":
                team_batted_first = True
            elif m.toss_winner_id != team_id and m.toss_decision == "field":
                team_batted_first = True

            if team_batted_first:
                team_bat_first_total += 1
                if m.winner_id == team_id:
                    team_bat_first_wins += 1
            else:
                team_chase_total += 1
                if m.winner_id == team_id:
                    team_chase_wins += 1

    team_bat_first_pct = round(team_bat_first_wins / max(team_bat_first_total, 1) * 100, 1)
    team_chase_pct = round(team_chase_wins / max(team_chase_total, 1) * 100, 1)

    # Opposition analysis
    opp_bat_first_wins = 0
    opp_bat_first_total = 0
    opp_chase_wins = 0
    opp_chase_total = 0

    if opp_id:
        opp_matches = db.query(Match).filter(
            or_(Match.team1_id == opp_id, Match.team2_id == opp_id),
            Match.winner_id != None,
        ).all()

        for m in opp_matches:
            opp_batted_first = False
            if m.toss_winner_id == opp_id and m.toss_decision == "bat":
                opp_batted_first = True
            elif m.toss_winner_id != opp_id and m.toss_decision == "field":
                opp_batted_first = True

            if opp_batted_first:
                opp_bat_first_total += 1
                if m.winner_id == opp_id:
                    opp_bat_first_wins += 1
            else:
                opp_chase_total += 1
                if m.winner_id == opp_id:
                    opp_chase_wins += 1

    opp_bat_first_pct = round(opp_bat_first_wins / max(opp_bat_first_total, 1) * 100, 1)
    opp_chase_pct = round(opp_chase_wins / max(opp_chase_total, 1) * 100, 1)

    # --- Decision Logic ---
    reasoning = []
    bat_score = 0  # positive = bat first, negative = field first

    # Venue factor
    if bat_first_win_pct > 55:
        bat_score += 20
        reasoning.append(f"Venue favors batting first ({bat_first_win_pct}% bat-first wins)")
    elif bat_first_win_pct < 45:
        bat_score -= 20
        reasoning.append(f"Venue favors chasing ({100 - bat_first_win_pct}% chase wins)")
    else:
        reasoning.append(f"Venue is neutral ({bat_first_win_pct}% bat-first wins)")

    # First vs second innings score
    if avg_first > avg_second + 10:
        bat_score += 10
        reasoning.append(f"Higher 1st innings avg ({avg_first:.0f} vs {avg_second:.0f}) - batting gets easier early")
    elif avg_second > avg_first + 5:
        bat_score -= 10
        reasoning.append(f"2nd innings scores competitive ({avg_second:.0f} vs {avg_first:.0f}) - chasing viable")

    # Dew factor (evening matches tend to favor chasing due to dew)
    bat_score -= 5
    reasoning.append("Dew factor in evening games slightly favors chasing")

    # Team strength
    if team_bat_first_pct > team_chase_pct + 10:
        bat_score += 15
        reasoning.append(f"{team_short_name} stronger batting first ({team_bat_first_pct}% vs {team_chase_pct}% chasing)")
    elif team_chase_pct > team_bat_first_pct + 10:
        bat_score -= 15
        reasoning.append(f"{team_short_name} stronger chasing ({team_chase_pct}% vs {team_bat_first_pct}% batting first)")
    else:
        reasoning.append(f"{team_short_name} balanced ({team_bat_first_pct}% bat first, {team_chase_pct}% chasing)")

    # Opposition weakness
    if opp_chase_pct > opp_bat_first_pct + 10:
        bat_score += 10
        reasoning.append(f"{opposition_short_name} better at chasing ({opp_chase_pct}%) - bat first to deny them comfort zone")
    elif opp_bat_first_pct > opp_chase_pct + 10:
        bat_score -= 10
        reasoning.append(f"{opposition_short_name} better batting first ({opp_bat_first_pct}%) - field first to exploit chase weakness")

    recommendation = "bat" if bat_score > 0 else "field"
    confidence = min(abs(bat_score) + 40, 95)

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reasoning": reasoning,
        "venue_analysis": {
            "venue_name": venue_name,
            "bat_first_win_pct": bat_first_win_pct,
            "avg_first_innings_score": round(avg_first, 1),
            "avg_second_innings_score": round(avg_second, 1),
            "pace_wicket_pct": pace_pct,
            "spin_wicket_pct": spin_pct,
            "total_wickets_analyzed": total_venue_wickets,
        },
        "team_batting_first_record": {
            "wins": team_bat_first_wins,
            "total": team_bat_first_total,
            "win_pct": team_bat_first_pct,
        },
        "team_chasing_record": {
            "wins": team_chase_wins,
            "total": team_chase_total,
            "win_pct": team_chase_pct,
        },
        "opposition_batting_first_record": {
            "wins": opp_bat_first_wins,
            "total": opp_bat_first_total,
            "win_pct": opp_bat_first_pct,
        },
        "opposition_chasing_record": {
            "wins": opp_chase_wins,
            "total": opp_chase_total,
            "win_pct": opp_chase_pct,
        },
    }


# ---------------------------------------------------------------------------
# 3. Create Game Plan
# ---------------------------------------------------------------------------

def create_game_plan(
    db: Session,
    team_short_name: str,
    playing_11_ids: List[int],
    opposition_short_name: str,
    opposition_11_ids: List[int],
    venue_id: int,
    batting_first: bool,
) -> dict:
    """
    Create a complete over-by-over game plan including batting order,
    bowling plan, and key matchups.
    """
    name_meta = _build_name_to_meta()

    # --- Build profiles for our players ---
    our_players = []
    for pid in playing_11_ids:
        player = db.get(Player, pid)
        if not player:
            continue
        meta = name_meta.get(player.name, {})
        role = player.role or meta.get("role", "Unknown")
        bowling_style = player.bowling_style or meta.get("bowling_style", "")

        pp_sr = _phase_batting_sr(db, pid, 0, 5)
        mid_sr = _phase_batting_sr(db, pid, 6, 14)
        death_sr = _phase_batting_sr(db, pid, 15, 19)

        pp_econ = _phase_economy(db, pid, 0, 5)
        mid_econ = _phase_economy(db, pid, 6, 14)
        death_econ = _phase_economy(db, pid, 15, 19)

        bat_stats = _get_batting_stats(db, pid)
        bowl_stats = _get_bowling_stats(db, pid)

        # Determine typical batting position from deliveries
        avg_pos_q = db.query(
            func.avg(Delivery.bat_pos).label("avg_pos")
        ).filter(
            Delivery.batter_id == pid,
            Delivery.bat_pos != None,
            Delivery.bat_pos > 0,
        ).first()
        avg_bat_pos = avg_pos_q.avg_pos if avg_pos_q and avg_pos_q.avg_pos else 11

        our_players.append({
            "player_id": pid,
            "name": player.name,
            "role": role,
            "bowling_style": bowling_style,
            "batting_style": player.batting_style or "",
            "can_bowl": _can_bowl_parttime(role, bowling_style),
            "is_wk": _is_wicketkeeper(role),
            "bat_avg": bat_stats["avg"],
            "bat_sr": bat_stats["sr"],
            "pp_sr": round(pp_sr, 1) if pp_sr else None,
            "mid_sr": round(mid_sr, 1) if mid_sr else None,
            "death_sr": round(death_sr, 1) if death_sr else None,
            "pp_econ": round(pp_econ, 2) if pp_econ else None,
            "mid_econ": round(mid_econ, 2) if mid_econ else None,
            "death_econ": round(death_econ, 2) if death_econ else None,
            "bowl_econ": bowl_stats["economy"] if bowl_stats["matches"] > 0 else None,
            "bowl_wpm": bowl_stats["wickets_per_match"],
            "avg_bat_pos": round(avg_bat_pos, 1),
            "bat_innings": bat_stats["innings"],
        })

    # --- Build profiles for opposition players ---
    opp_players = []
    for pid in opposition_11_ids:
        player = db.get(Player, pid)
        if not player:
            continue
        meta = name_meta.get(player.name, {})
        role = player.role or meta.get("role", "Unknown")
        bowling_style = player.bowling_style or meta.get("bowling_style", "")

        bat_stats = _get_batting_stats(db, pid)
        bowl_stats = _get_bowling_stats(db, pid)

        opp_players.append({
            "player_id": pid,
            "name": player.name,
            "role": role,
            "bowling_style": bowling_style,
            "can_bowl": _can_bowl_parttime(role, bowling_style),
            "bat_avg": bat_stats["avg"],
            "bat_sr": bat_stats["sr"],
            "bowl_econ": bowl_stats["economy"] if bowl_stats["matches"] > 0 else None,
        })

    # =====================
    # BATTING PLAN
    # =====================
    # Determine batting order
    batters = sorted(our_players, key=lambda x: x["avg_bat_pos"])

    # Categorize by role for ordering
    openers = []
    top_order = []
    middle_order = []
    finishers = []
    tail = []

    for p in our_players:
        if p["is_wk"] or (_is_pure_batsman(p["role"]) and p["avg_bat_pos"] <= 3):
            if p["avg_bat_pos"] <= 2.5 and p["bat_innings"] > 0:
                openers.append(p)
            else:
                top_order.append(p)
        elif _is_pure_batsman(p["role"]) or _is_batting_allrounder(p["role"]):
            if p["avg_bat_pos"] <= 5:
                top_order.append(p)
            else:
                middle_order.append(p)
        elif _is_bowling_allrounder(p["role"]):
            finishers.append(p)
        elif _is_pure_bowler(p["role"]):
            tail.append(p)
        else:
            middle_order.append(p)

    # Sort each group
    openers.sort(key=lambda x: x["bat_sr"], reverse=True)
    top_order.sort(key=lambda x: x["bat_avg"], reverse=True)
    middle_order.sort(key=lambda x: (x["bat_avg"] + x["bat_sr"]) / 2, reverse=True)
    finishers.sort(key=lambda x: x.get("death_sr") or x["bat_sr"], reverse=True)
    tail.sort(key=lambda x: x["bat_avg"], reverse=True)

    # Ensure at least 2 openers
    while len(openers) < 2 and top_order:
        openers.append(top_order.pop(0))

    batting_order_list = openers[:2] + top_order + middle_order + finishers + tail
    # Deduplicate
    seen_ids = set()
    deduped = []
    for p in batting_order_list:
        if p["player_id"] not in seen_ids:
            seen_ids.add(p["player_id"])
            deduped.append(p)
    # Add any missing players
    for p in our_players:
        if p["player_id"] not in seen_ids:
            seen_ids.add(p["player_id"])
            deduped.append(p)

    batting_order = []
    for i, p in enumerate(deduped):
        pos = i + 1
        if pos <= 2:
            pos_role = "Opener"
        elif pos <= 4:
            pos_role = "Top Order"
        elif pos <= 6:
            pos_role = "Middle Order"
        elif pos <= 8:
            pos_role = "Lower Middle / Finisher"
        else:
            pos_role = "Tail"

        # Reasoning
        reasons = []
        if p["avg_bat_pos"] <= 3 and p["bat_innings"] > 0:
            reasons.append(f"Historical avg position {p['avg_bat_pos']}")
        if p["bat_avg"] > 25:
            reasons.append(f"Strong avg {p['bat_avg']}")
        if p["bat_sr"] > 140:
            reasons.append(f"Aggressive SR {p['bat_sr']}")
        if p.get("death_sr") and p["death_sr"] > 150:
            reasons.append(f"Death SR {p['death_sr']} - finisher potential")
        if not reasons:
            reasons.append(f"Role-based placement ({p['role']})")

        batting_order.append({
            "position": pos,
            "player_id": p["player_id"],
            "name": p["name"],
            "role": pos_role,
            "reasoning": "; ".join(reasons),
            "projected_sr": p["bat_sr"],
            "phase_strengths": {
                "pp_sr": p["pp_sr"],
                "middle_sr": p["mid_sr"],
                "death_sr": p["death_sr"],
            },
        })

    # Phase targets from venue data
    venue_pp_avg = _venue_phase_avg(db, venue_id, 0, 5) or 48.0
    venue_mid_avg = _venue_phase_avg(db, venue_id, 6, 14) or 72.0
    venue_death_avg = _venue_phase_avg(db, venue_id, 15, 19) or 52.0

    phase_targets = {
        "powerplay": {
            "target_runs": round(venue_pp_avg),
            "target_wickets_max": 2,
            "overs": "1-6",
        },
        "middle": {
            "target_runs": round(venue_mid_avg),
            "target_wickets_max": 4,
            "overs": "7-15",
        },
        "death": {
            "target_runs": round(venue_death_avg),
            "target_wickets_max": 4,
            "overs": "16-20",
        },
    }

    # =====================
    # KEY MATCHUPS
    # =====================
    opp_bowler_ids = [p["player_id"] for p in opp_players if p["can_bowl"]]
    opp_batter_ids = [p["player_id"] for p in opp_players]

    matchups_exploit = []
    matchups_avoid = []

    for batter in our_players:
        for bowler_id in opp_bowler_ids:
            bvb = db.query(BatterVsBowler).filter(
                BatterVsBowler.batter_id == batter["player_id"],
                BatterVsBowler.bowler_id == bowler_id,
            ).first()
            if bvb and bvb.balls >= 10:
                sr = round(bvb.runs / bvb.balls * 100, 1) if bvb.balls > 0 else 0
                bowler_name = db.get(Player, bowler_id)
                b_name = bowler_name.name if bowler_name else f"Bowler {bowler_id}"

                if sr >= 160:
                    matchups_exploit.append({
                        "batter": batter["name"],
                        "batter_id": batter["player_id"],
                        "bowler": b_name,
                        "bowler_id": bowler_id,
                        "balls": bvb.balls,
                        "runs": bvb.runs,
                        "sr": sr,
                        "advantage": f"SR {sr} in {bvb.balls} balls - target this bowler",
                    })
                elif sr <= 90:
                    matchups_avoid.append({
                        "batter": batter["name"],
                        "batter_id": batter["player_id"],
                        "bowler": b_name,
                        "bowler_id": bowler_id,
                        "balls": bvb.balls,
                        "runs": bvb.runs,
                        "sr": sr,
                        "risk": f"SR {sr} in {bvb.balls} balls - rotate strike",
                    })

    matchups_exploit.sort(key=lambda x: x["sr"], reverse=True)
    matchups_avoid.sort(key=lambda x: x["sr"])

    # =====================
    # BOWLING PLAN
    # =====================
    bowlers = [p for p in our_players if p["can_bowl"]]

    # Rank bowlers by phase
    pp_bowlers = sorted(bowlers, key=lambda x: x["pp_econ"] if x["pp_econ"] else 99)
    mid_bowlers = sorted(bowlers, key=lambda x: x["mid_econ"] if x["mid_econ"] else 99)
    death_bowlers = sorted(bowlers, key=lambda x: x["death_econ"] if x["death_econ"] else 99)

    # Prefer fast bowlers in powerplay
    fast_bowlers_pp = [b for b in pp_bowlers if "fast" in (b["bowling_style"] or "").lower() or "medium" in (b["bowling_style"] or "").lower()]
    spin_bowlers_mid = [b for b in mid_bowlers if "spin" in (b["bowling_style"] or "").lower() or "leg" in (b["bowling_style"] or "").lower() or "off" in (b["bowling_style"] or "").lower() or "orthodox" in (b["bowling_style"] or "").lower()]

    if not fast_bowlers_pp:
        fast_bowlers_pp = pp_bowlers
    if not spin_bowlers_mid:
        spin_bowlers_mid = mid_bowlers

    # Build over-by-over plan
    bowler_overs_used: Dict[int, int] = {b["player_id"]: 0 for b in bowlers}
    bowling_plan = []

    last_bowler_id = None

    def _pick_bowler(phase_ranked: list, over_num: int, phase: str) -> Optional[dict]:
        nonlocal last_bowler_id
        # Rule: cannot bowl consecutive overs (same end in real cricket = alternating)
        # Pick the best available bowler who isn't the same as last over
        for b in phase_ranked:
            if bowler_overs_used.get(b["player_id"], 0) < MAX_OVERS_PER_BOWLER and b["player_id"] != last_bowler_id:
                return b
        # If all preferred bowlers are last_bowler or at limit, allow same bowler
        for b in phase_ranked:
            if bowler_overs_used.get(b["player_id"], 0) < MAX_OVERS_PER_BOWLER:
                return b
        # Fallback: any bowler with overs left
        for b in bowlers:
            if bowler_overs_used.get(b["player_id"], 0) < MAX_OVERS_PER_BOWLER and b["player_id"] != last_bowler_id:
                return b
        for b in bowlers:
            if bowler_overs_used.get(b["player_id"], 0) < MAX_OVERS_PER_BOWLER:
                return b
        return None

    def _danger_batters_for_bowler(bowler_id: int) -> list:
        dangers = []
        for opp_bat_id in opp_batter_ids:
            bvb = db.query(BatterVsBowler).filter(
                BatterVsBowler.batter_id == opp_bat_id,
                BatterVsBowler.bowler_id == bowler_id,
            ).first()
            if bvb and bvb.balls >= 10:
                sr = round(bvb.runs / bvb.balls * 100, 1) if bvb.balls > 0 else 0
                if sr >= 150:
                    opp_name = db.get(Player, opp_bat_id)
                    dangers.append({
                        "batter": opp_name.name if opp_name else f"ID {opp_bat_id}",
                        "sr": sr,
                        "balls": bvb.balls,
                        "warning": f"SR {sr} in {bvb.balls} balls",
                    })
        dangers.sort(key=lambda x: x["sr"], reverse=True)
        return dangers[:3]

    for over in range(20):
        if over < 6:
            phase = "powerplay"
            ranked = fast_bowlers_pp if fast_bowlers_pp else pp_bowlers
            target = round(venue_pp_avg / 6)
        elif over < 15:
            phase = "middle"
            ranked = spin_bowlers_mid if spin_bowlers_mid else mid_bowlers
            target = round(venue_mid_avg / 9)
        else:
            phase = "death"
            ranked = death_bowlers
            target = round(venue_death_avg / 5)

        bowler = _pick_bowler(ranked, over, phase)
        if bowler:
            bowler_overs_used[bowler["player_id"]] = bowler_overs_used.get(bowler["player_id"], 0) + 1
            last_bowler_id = bowler["player_id"]

            econ_key = f"{phase[:2] if phase != 'death' else 'death'}_econ"
            if phase == "powerplay":
                econ_key = "pp_econ"
            elif phase == "middle":
                econ_key = "mid_econ"
            else:
                econ_key = "death_econ"

            projected_econ = bowler.get(econ_key) or bowler.get("bowl_econ") or 8.0

            danger = _danger_batters_for_bowler(bowler["player_id"])

            bowling_plan.append({
                "over": over + 1,
                "bowler_id": bowler["player_id"],
                "bowler_name": bowler["name"],
                "phase": phase,
                "projected_economy": round(projected_econ, 2),
                "target_runs": target,
                "reason": f"Best {phase} option (econ {projected_econ:.1f})" + (
                    f" | {bowler['bowling_style']}" if bowler.get("bowling_style") else ""
                ),
                "danger_batters": danger,
            })
        else:
            bowling_plan.append({
                "over": over + 1,
                "bowler_id": None,
                "bowler_name": "TBD",
                "phase": phase,
                "projected_economy": 8.0,
                "target_runs": target,
                "reason": "No bowlers available with remaining overs",
                "danger_batters": [],
            })

    # Bowling phase summary
    bowling_phase_summary = {
        "powerplay": {
            "bowlers": [
                {"name": b["name"], "economy": b.get("pp_econ") or b.get("bowl_econ", "N/A")}
                for b in fast_bowlers_pp[:3]
            ],
            "strategy": "Attack with pace, target early wickets, use new ball movement",
        },
        "middle": {
            "bowlers": [
                {"name": b["name"], "economy": b.get("mid_econ") or b.get("bowl_econ", "N/A")}
                for b in spin_bowlers_mid[:3]
            ],
            "strategy": "Control with spin, build dot ball pressure, use variations",
        },
        "death": {
            "bowlers": [
                {"name": b["name"], "economy": b.get("death_econ") or b.get("bowl_econ", "N/A")}
                for b in death_bowlers[:3]
            ],
            "strategy": "Yorkers and slower balls, minimize boundaries, use best death bowlers",
        },
    }

    return {
        "batting_order": batting_order,
        "phase_targets": phase_targets,
        "key_matchups_exploit": matchups_exploit[:10],
        "key_matchups_avoid": matchups_avoid[:10],
        "bowling_plan": bowling_plan,
        "bowling_phase_summary": bowling_phase_summary,
    }


# ---------------------------------------------------------------------------
# 4. Live Game Plan Update
# ---------------------------------------------------------------------------

def live_game_plan_update(
    db: Session,
    team_short_name: str,
    playing_11_ids: List[int],
    opposition_short_name: str,
    current_score: int,
    current_wickets: int,
    current_over: float,
    is_batting: bool,
    venue_id: int,
) -> dict:
    """
    Adjusts game plan based on current match situation.
    Compares to venue par score and recommends strategy changes.
    """
    name_meta = _build_name_to_meta()

    # Parse current_over: e.g., 10.3 means 10 overs and 3 balls
    overs_completed = int(current_over)
    balls_in_current = round((current_over - overs_completed) * 10)
    total_balls_bowled = overs_completed * 6 + balls_in_current
    remaining_balls = 120 - total_balls_bowled
    remaining_overs = remaining_balls / 6.0

    # Venue stats
    venue_stats = db.query(VenueStats).filter(VenueStats.venue_id == venue_id).first()
    avg_total = 165.0
    if venue_stats:
        avg_total = venue_stats.avg_first_innings_score or 165.0

    # Compute par score at this stage (linear interpolation)
    par_score_at_stage = round(avg_total * (total_balls_bowled / 120.0))

    # Determine situation
    delta = current_score - par_score_at_stage

    if delta > 15:
        situation = "well_ahead"
    elif delta > 5:
        situation = "ahead"
    elif delta > -5:
        situation = "par"
    elif delta > -15:
        situation = "behind"
    else:
        situation = "well_behind"

    # Current run rate
    current_rr = round((current_score / max(total_balls_bowled, 1)) * 6, 2)
    # Required run rate for par total
    runs_needed_par = max(0, avg_total - current_score)
    required_rr = round((runs_needed_par / max(remaining_balls, 1)) * 6, 2) if remaining_balls > 0 else 0

    # Projected score
    projected_score = round(current_score + (current_rr * remaining_overs))

    result: Dict[str, Any] = {
        "situation": situation,
        "par_score": par_score_at_stage,
        "actual_score": current_score,
        "delta": delta,
        "current_run_rate": current_rr,
        "required_run_rate_par": required_rr,
        "projected_score": projected_score,
        "overs_remaining": round(remaining_overs, 1),
        "balls_remaining": remaining_balls,
    }

    if is_batting:
        result["strategy"] = _batting_strategy(
            db, playing_11_ids, current_score, current_wickets,
            total_balls_bowled, remaining_balls, situation, delta,
            avg_total, name_meta, current_rr, required_rr,
        )
    else:
        result["strategy"] = _bowling_strategy(
            db, playing_11_ids, current_score, current_wickets,
            total_balls_bowled, remaining_balls, situation, delta,
            avg_total, name_meta, current_rr,
        )

    return result


def _batting_strategy(
    db: Session,
    playing_11_ids: List[int],
    current_score: int,
    current_wickets: int,
    total_balls: int,
    remaining_balls: int,
    situation: str,
    delta: int,
    avg_total: float,
    name_meta: dict,
    current_rr: float,
    required_rr: float,
) -> dict:
    """Generate batting strategy based on match situation."""
    wickets_in_hand = 10 - current_wickets
    remaining_overs = remaining_balls / 6.0

    # Approach
    if situation in ("well_ahead", "ahead"):
        if wickets_in_hand >= 7:
            approach = "Continue aggressive approach. Well ahead of par with wickets in hand."
            target_rr = current_rr * 1.1
        else:
            approach = "Maintain current tempo. Ahead of par, protect remaining wickets."
            target_rr = current_rr
    elif situation == "par":
        if wickets_in_hand >= 6:
            approach = "Look to accelerate. At par with wickets in hand - push for above-par total."
            target_rr = required_rr * 1.1
        else:
            approach = "Steady accumulation. At par but need to manage wickets."
            target_rr = required_rr
    elif situation == "behind":
        if wickets_in_hand >= 6:
            approach = "Accelerate. Behind par but wickets in hand - target boundaries against weaker bowlers."
            target_rr = required_rr * 1.15
        else:
            approach = "Consolidate first, then accelerate in death. Behind par with few wickets."
            target_rr = required_rr
    else:  # well_behind
        if wickets_in_hand >= 5:
            approach = "Go all out. Significantly behind par - play high-risk shots, target boundary bowlers."
            target_rr = required_rr * 1.25
        else:
            approach = "Damage limitation. Well behind and short on wickets - aim for respectable total."
            target_rr = required_rr * 0.9

    # Recommend next batters based on situation
    recommended_next = []
    for pid in playing_11_ids:
        player = db.get(Player, pid)
        if not player:
            continue
        meta = name_meta.get(player.name, {})
        role = player.role or meta.get("role", "Unknown")

        if situation in ("well_behind", "behind") and remaining_balls <= 30:
            # Need power hitters
            death_sr = _phase_batting_sr(db, pid, 15, 19)
            if death_sr and death_sr > 140:
                recommended_next.append({
                    "player_id": pid,
                    "name": player.name,
                    "reason": f"Death SR {death_sr:.0f} - power hitting needed",
                })
        elif situation in ("well_ahead", "ahead") and wickets_in_hand <= 4:
            # Need steady batters
            bat_stats = _get_batting_stats(db, pid)
            if bat_stats["avg"] > 25:
                recommended_next.append({
                    "player_id": pid,
                    "name": player.name,
                    "reason": f"Avg {bat_stats['avg']} - steady accumulator",
                })

    # Phase adjustment
    current_phase = "powerplay" if total_balls < 36 else "middle" if total_balls < 90 else "death"
    phase_adjustment = {
        "current_phase": current_phase,
        "target_run_rate": round(target_rr, 2),
        "approach": approach,
    }

    if current_phase == "death" and situation in ("behind", "well_behind"):
        phase_adjustment["tactic"] = "Target weaker bowlers, look for boundaries on every ball, run hard between wickets"
    elif current_phase == "middle" and situation == "ahead":
        phase_adjustment["tactic"] = "Rotate strike, pick boundaries off loose balls, set up for death overs assault"
    elif current_phase == "powerplay":
        phase_adjustment["tactic"] = "Maximize fielding restrictions, target gaps in the field, be aggressive but smart"

    return {
        "recommended_batting_approach": approach,
        "target_run_rate": round(target_rr, 2),
        "wickets_in_hand": wickets_in_hand,
        "recommended_next_batters": recommended_next[:4],
        "phase_adjustment": phase_adjustment,
    }


def _bowling_strategy(
    db: Session,
    playing_11_ids: List[int],
    current_score: int,
    current_wickets: int,
    total_balls: int,
    remaining_balls: int,
    situation: str,
    delta: int,
    avg_total: float,
    name_meta: dict,
    current_rr: float,
) -> dict:
    """Generate bowling strategy based on opposition's match situation."""
    remaining_overs = remaining_balls / 6.0

    # From bowling team's perspective, opposition being "ahead" is bad for us
    if situation in ("well_ahead", "ahead"):
        approach = "Need wickets urgently. Opposition ahead of par - bring on attacking bowlers, set aggressive fields."
    elif situation == "par":
        approach = "Maintain pressure. Opposition at par - focus on dot balls, build pressure for wickets."
    elif situation == "behind":
        approach = "Good position. Opposition behind par - keep squeezing, vary pace and lengths."
    else:
        approach = "Dominating. Opposition well behind - maintain discipline, don't give freebies."

    # Recommend bowlers based on situation
    recommended_bowlers = []
    current_phase = "powerplay" if total_balls < 36 else "middle" if total_balls < 90 else "death"

    for pid in playing_11_ids:
        player = db.get(Player, pid)
        if not player:
            continue
        meta = name_meta.get(player.name, {})
        role = player.role or meta.get("role", "Unknown")
        bowling_style = player.bowling_style or meta.get("bowling_style", "")

        if not _can_bowl_parttime(role, bowling_style):
            continue

        if current_phase == "powerplay":
            econ = _phase_economy(db, pid, 0, 5)
        elif current_phase == "middle":
            econ = _phase_economy(db, pid, 6, 14)
        else:
            econ = _phase_economy(db, pid, 15, 19)

        if situation in ("well_ahead", "ahead"):
            # Need attacking bowlers - prioritize wicket takers
            bowl_stats = _get_bowling_stats(db, pid)
            if bowl_stats["wickets_per_match"] > 1:
                recommended_bowlers.append({
                    "player_id": pid,
                    "name": player.name,
                    "reason": f"Wicket-taker ({bowl_stats['wickets_per_match']} wpm) - need breakthroughs",
                    "phase_economy": round(econ, 2) if econ else None,
                })
        else:
            # Economy-focused
            if econ and econ < 8:
                recommended_bowlers.append({
                    "player_id": pid,
                    "name": player.name,
                    "reason": f"Economical in {current_phase} (econ {econ:.1f}) - maintain pressure",
                    "phase_economy": round(econ, 2),
                })

    # If no specific recommendations, add all bowlers
    if not recommended_bowlers:
        for pid in playing_11_ids:
            player = db.get(Player, pid)
            if not player:
                continue
            role = player.role or ""
            bowling_style = player.bowling_style or ""
            if _can_bowl_parttime(role, bowling_style):
                recommended_bowlers.append({
                    "player_id": pid,
                    "name": player.name,
                    "reason": "Available bowling option",
                    "phase_economy": None,
                })

    phase_adjustment = {
        "current_phase": current_phase,
        "opposition_run_rate": current_rr,
        "approach": approach,
    }

    if current_phase == "death" and situation in ("well_ahead", "ahead"):
        phase_adjustment["tactic"] = "Mix yorkers with bouncers, use slower balls, avoid slot lengths"
    elif current_phase == "middle" and situation in ("behind", "well_behind"):
        phase_adjustment["tactic"] = "Continue building dot ball pressure, spin through middle, restrict scoring areas"
    elif current_phase == "powerplay" and situation in ("well_ahead", "ahead"):
        phase_adjustment["tactic"] = "Need early wickets, attack the stumps, use pace and swing"

    return {
        "recommended_bowling_approach": approach,
        "recommended_bowlers": recommended_bowlers[:5],
        "phase_adjustment": phase_adjustment,
    }
