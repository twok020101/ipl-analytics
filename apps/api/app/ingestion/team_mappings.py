from typing import Dict, Set
# Canonical team name mappings: variant -> canonical name
TEAM_NAME_MAP: Dict[str, str] = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Rising Pune Supergiant": "Rising Pune Supergiants",
}

# Short names for each canonical team
TEAM_SHORT_NAMES: Dict[str, str] = {
    "Chennai Super Kings": "CSK",
    "Mumbai Indians": "MI",
    "Royal Challengers Bengaluru": "RCB",
    "Delhi Capitals": "DC",
    "Kolkata Knight Riders": "KKR",
    "Sunrisers Hyderabad": "SRH",
    "Rajasthan Royals": "RR",
    "Punjab Kings": "PBKS",
    "Gujarat Titans": "GT",
    "Lucknow Super Giants": "LSG",
    "Rising Pune Supergiants": "RPS",
    "Gujarat Lions": "GL",
    "Pune Warriors": "PW",
    "Deccan Chargers": "DCH",
    "Kochi Tuskers Kerala": "KTK",
}

# Teams currently active in IPL
ACTIVE_TEAMS: Set[str] = {
    "Chennai Super Kings",
    "Mumbai Indians",
    "Royal Challengers Bengaluru",
    "Delhi Capitals",
    "Kolkata Knight Riders",
    "Sunrisers Hyderabad",
    "Rajasthan Royals",
    "Punjab Kings",
    "Gujarat Titans",
    "Lucknow Super Giants",
}


def normalize_team_name(name: str) -> str:
    """Return the canonical team name."""
    if not name or name == "Unknown":
        return name
    return TEAM_NAME_MAP.get(name, name)
