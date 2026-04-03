"""Shared squad and player metadata queries — single source of truth for 2026 squad data."""

import json
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.models import SquadMember, Player, Team
from app.config import DATA_DIR


def get_squad_data(db: Session, season: str = "2026") -> dict:
    """Get squad membership: {short_name: {team_id, team_name, player_ids, captain_id}}.

    Queries DB first, falls back to team_squads_2026.json for transition.
    """
    members = (
        db.query(SquadMember)
        .filter(SquadMember.season == season)
        .join(SquadMember.team)
        .all()
    )

    if members:
        result = {}
        for m in members:
            key = m.team.short_name
            if key not in result:
                result[key] = {
                    "team_id": m.team_id,
                    "team_name": m.team.name,
                    "player_ids": [],
                    "captain_id": None,
                }
            result[key]["player_ids"].append(m.player_id)
            if m.is_captain:
                result[key]["captain_id"] = m.player_id
        return result

    # Fallback to JSON
    path = DATA_DIR / "team_squads_2026.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def get_player_meta(db: Session, season: str = "2026") -> dict:
    """Get player metadata: {name: {country, role, batting_style, bowling_style}}.

    Queries players who are squad members for the given season.
    Falls back to ipl2026.json squads data.
    """
    players = (
        db.query(Player)
        .join(SquadMember, SquadMember.player_id == Player.id)
        .filter(SquadMember.season == season)
        .all()
    )

    if players:
        return {
            p.name: {
                "country": p.country or "India",
                "role": p.role or "Unknown",
                "batting_style": p.batting_style or "",
                "bowling_style": p.bowling_style or "",
            }
            for p in players
        }

    # Fallback to JSON
    path = DATA_DIR / "ipl2026.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        meta = {}
        for squad in data.get("squads", {}).values():
            for p in squad.get("players", []):
                meta[p["name"]] = {
                    "country": p.get("country", "India"),
                    "role": p.get("role", "Unknown"),
                    "batting_style": p.get("battingStyle", ""),
                    "bowling_style": p.get("bowlingStyle", ""),
                }
        return meta
    return {}


def get_squad_player_names(db: Session, team_short: str, season: str = "2026") -> list[str]:
    """Get list of player names for a team's squad."""
    names = (
        db.query(Player.name)
        .join(SquadMember, SquadMember.player_id == Player.id)
        .join(Team, SquadMember.team_id == Team.id)
        .filter(SquadMember.season == season, Team.short_name == team_short)
        .all()
    )
    if names:
        return [n[0] for n in names]

    # Fallback
    path = DATA_DIR / "ipl2026.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        squad = data.get("squads", {}).get(team_short, {})
        return [p["name"] for p in squad.get("players", [])]
    return []
