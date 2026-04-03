"""Shared cricket utility functions — score parsing, overs conversion, toss resolution."""

import re
from typing import Tuple

# Pre-compiled regex patterns
_SCORE_FULL_RE = re.compile(r"(\d+)/(\d+)\s*\((\d+\.?\d*)\)")
_SCORE_PARTIAL_RE = re.compile(r"(\d+)/(\d+)")
_TEAM_SHORT_RE = re.compile(r"\[(\w+)\]")


def parse_score(score_str: str) -> dict:
    """Parse score string like '141/10 (18.4)' into {runs, wickets, overs}.

    Returns empty dict if score_str is falsy (matching match_sync behaviour),
    or a dict with zeros if nothing matched (matching live_tracker behaviour).
    """
    if not score_str:
        return {"runs": 0, "wickets": 0, "overs": 0.0}
    m = _SCORE_FULL_RE.match(score_str)
    if m:
        return {
            "runs": int(m.group(1)),
            "wickets": int(m.group(2)),
            "overs": float(m.group(3)),
        }
    m = _SCORE_PARTIAL_RE.match(score_str)
    if m:
        return {"runs": int(m.group(1)), "wickets": int(m.group(2)), "overs": 0.0}
    return {"runs": 0, "wickets": 0, "overs": 0.0}


def extract_team_short(team_str: str) -> str:
    """Extract short name from 'Delhi Capitals [DC]' -> 'DC'."""
    m = _TEAM_SHORT_RE.search(team_str)
    if m:
        short = m.group(1)
        return "RCB" if short == "RCBW" else short
    return team_str.split()[0] if team_str.strip() else ""


def cricket_overs_to_decimal(overs: float) -> float:
    """Convert cricket overs notation to decimal overs.

    In cricket, 19.4 means 19 overs and 4 balls = 19 + 4/6 = 19.667 overs.
    The fractional part represents balls (0-5), not a decimal fraction.
    """
    whole = int(overs)
    balls = round((overs - whole) * 10)
    return whole + balls / 6.0


def resolve_batting_order(
    toss_winner_id: int | None,
    toss_decision: str | None,
    team1_id: int,
    team2_id: int,
) -> Tuple[int, int]:
    """Determine which team batted first from toss data.

    Returns (bat_first_id, bat_second_id). Falls back to team1 batting
    first if toss data is unavailable.
    """
    if toss_winner_id and toss_decision:
        if toss_decision == "bat":
            bat_first = toss_winner_id
        else:
            bat_first = team2_id if toss_winner_id == team1_id else team1_id
    else:
        bat_first = team1_id
    bat_second = team2_id if bat_first == team1_id else team1_id
    return bat_first, bat_second
