"""Shared CricAPI utility functions for parsing scores and team names."""

import re

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
