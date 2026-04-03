"""Shared DB helper functions for finding or creating teams, players, venues."""

import hashlib
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Team, Player, Venue


def find_or_create_team(db: Session, short_name: str, full_name: str) -> Team:
    """Find team by short_name or create."""
    team = db.query(Team).filter(Team.short_name == short_name).first()
    if team:
        return team
    team = db.query(Team).filter(Team.name == full_name).first()
    if team:
        if not team.short_name:
            team.short_name = short_name
        return team
    team = Team(name=full_name, short_name=short_name, is_active=True)
    db.add(team)
    db.flush()
    return team


def find_or_create_player(db: Session, name: str, **kwargs) -> Player:
    """Find player by name or create/enrich with metadata."""
    player = db.query(Player).filter(Player.name == name).first()
    if player:
        if kwargs.get("role") and not player.role:
            player.role = kwargs["role"]
        if kwargs.get("batting_style") and not player.batting_style:
            player.batting_style = kwargs["batting_style"]
        if kwargs.get("bowling_style") and not player.bowling_style:
            player.bowling_style = kwargs["bowling_style"]
        if kwargs.get("country") and not player.country:
            player.country = kwargs["country"]
        if kwargs.get("player_img") and not player.player_img:
            player.player_img = kwargs["player_img"]
        return player
    player = Player(
        name=name,
        role=kwargs.get("role"),
        batting_style=kwargs.get("batting_style"),
        bowling_style=kwargs.get("bowling_style"),
        country=kwargs.get("country"),
        player_img=kwargs.get("player_img"),
    )
    db.add(player)
    db.flush()
    return player


_GENERIC_VENUE_WORDS = {"stadium", "cricket", "international", "sports", "ground", "academy"}


def find_or_create_venue(db: Session, venue_str: str) -> Optional[Venue]:
    """Find venue by name (exact, substring, or city match) or create."""
    if not venue_str:
        return None
    venue = db.query(Venue).filter(Venue.name == venue_str).first()
    if venue:
        return venue

    # Extract city from "Stadium Name, City"
    parts = venue_str.rsplit(", ", 1)
    new_city = parts[-1].strip().lower() if len(parts) > 1 else None

    all_venues = db.query(Venue).all()
    for v in all_venues:
        v_lower = v.name.lower()
        new_lower = venue_str.lower()
        # Exact substring match (one name fully contained in the other)
        if v_lower in new_lower or new_lower in v_lower:
            return v
        # Significant word overlap (exclude generic words like "Stadium", "Cricket")
        v_words = set(re.findall(r'\b\w{5,}\b', v_lower)) - _GENERIC_VENUE_WORDS
        new_words = set(re.findall(r'\b\w{5,}\b', new_lower)) - _GENERIC_VENUE_WORDS
        overlap = v_words & new_words
        if len(overlap) >= 2:
            return v
        # Single distinctive word match + same city
        if overlap and new_city and v.city and v.city.lower() == new_city:
            return v

    city = parts[-1] if len(parts) > 1 else None
    venue = Venue(name=venue_str, city=city)
    db.add(venue)
    db.flush()
    return venue


def stable_source_id(cricapi_uuid: str) -> int:
    """Deterministic integer ID from CricAPI UUID (for source_match_id column)."""
    return int(hashlib.sha256(cricapi_uuid.encode()).hexdigest()[:7], 16) + 2000000
