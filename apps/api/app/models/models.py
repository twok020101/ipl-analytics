from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    plan = Column(String(20), default="free")  # free, pro, enterprise
    created_at = Column(DateTime, server_default=func.now())
    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(20), default="analyst")  # admin, analyst, viewer
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    organization = relationship("Organization", back_populates="users")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    short_name = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)

    home_matches = relationship("Match", foreign_keys="Match.team1_id", back_populates="team1")
    away_matches = relationship("Match", foreign_keys="Match.team2_id", back_populates="team2")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)
    role = Column(String(50), nullable=True)
    batting_style = Column(String(50), nullable=True)
    bowling_style = Column(String(50), nullable=True)

    batting_stats = relationship("PlayerSeasonBatting", back_populates="player")
    bowling_stats = relationship("PlayerSeasonBowling", back_populates="player")


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    city = Column(String(100), nullable=True)

    matches = relationship("Match", back_populates="venue")
    stats = relationship("VenueStats", back_populates="venue", uselist=False)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_match_id = Column(Integer, unique=True, nullable=False, index=True)
    date = Column(Date, nullable=True)
    season = Column(String(20), nullable=True)
    stage = Column(String(50), nullable=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=True)
    team1_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team2_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    toss_winner_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    toss_decision = Column(String(10), nullable=True)
    winner_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    win_margin = Column(Integer, nullable=True)
    win_type = Column(String(20), nullable=True)
    player_of_match_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    method = Column(String(20), nullable=True)
    first_innings_score = Column(Integer, nullable=True)
    first_innings_overs = Column(Float, nullable=True)
    second_innings_score = Column(Integer, nullable=True)
    second_innings_overs = Column(Float, nullable=True)

    venue = relationship("Venue", back_populates="matches")
    team1 = relationship("Team", foreign_keys=[team1_id], back_populates="home_matches")
    team2 = relationship("Team", foreign_keys=[team2_id], back_populates="away_matches")
    toss_winner = relationship("Team", foreign_keys=[toss_winner_id])
    winner = relationship("Team", foreign_keys=[winner_id])
    player_of_match = relationship("Player", foreign_keys=[player_of_match_id])
    deliveries = relationship("Delivery", back_populates="match")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    innings = Column(Integer, nullable=False)
    over_num = Column(Integer, nullable=False)
    ball_num = Column(Integer, nullable=False)
    batter_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    bowler_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    non_striker_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    bat_pos = Column(Integer, nullable=True)
    runs_batter = Column(Integer, default=0)
    runs_extras = Column(Integer, default=0)
    runs_total = Column(Integer, default=0)
    valid_ball = Column(Boolean, default=True)
    extra_type = Column(String(50), nullable=True)
    wicket_kind = Column(String(50), nullable=True)
    player_out_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    team_runs = Column(Integer, nullable=True)
    team_wickets = Column(Integer, nullable=True)

    match = relationship("Match", back_populates="deliveries")
    batter = relationship("Player", foreign_keys=[batter_id])
    bowler = relationship("Player", foreign_keys=[bowler_id])
    non_striker = relationship("Player", foreign_keys=[non_striker_id])
    player_out = relationship("Player", foreign_keys=[player_out_id])

    __table_args__ = (
        Index("ix_delivery_match_innings", "match_id", "innings"),
        Index("ix_delivery_batter", "batter_id"),
        Index("ix_delivery_bowler", "bowler_id"),
    )


class PlayerSeasonBatting(Base):
    __tablename__ = "player_season_batting"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(String(20), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    matches = Column(Integer, default=0)
    innings = Column(Integer, default=0)
    runs = Column(Integer, default=0)
    balls_faced = Column(Integer, default=0)
    fours = Column(Integer, default=0)
    sixes = Column(Integer, default=0)
    strike_rate = Column(Float, default=0.0)
    average = Column(Float, default=0.0)
    highest_score = Column(Integer, default=0)
    fifties = Column(Integer, default=0)
    hundreds = Column(Integer, default=0)
    not_outs = Column(Integer, default=0)

    player = relationship("Player", back_populates="batting_stats")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_bat"),
        Index("ix_psb_player", "player_id"),
    )


class PlayerSeasonBowling(Base):
    __tablename__ = "player_season_bowling"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(String(20), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    matches = Column(Integer, default=0)
    innings = Column(Integer, default=0)
    overs_bowled = Column(Float, default=0.0)
    runs_conceded = Column(Integer, default=0)
    wickets = Column(Integer, default=0)
    economy = Column(Float, default=0.0)
    average = Column(Float, default=0.0)
    best_figures = Column(String(10), nullable=True)
    four_wickets = Column(Integer, default=0)
    five_wickets = Column(Integer, default=0)

    player = relationship("Player", back_populates="bowling_stats")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_bowl"),
        Index("ix_psbow_player", "player_id"),
    )


class BatterVsBowler(Base):
    __tablename__ = "batter_vs_bowler"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batter_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    bowler_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    balls = Column(Integer, default=0)
    runs = Column(Integer, default=0)
    dismissals = Column(Integer, default=0)
    dots = Column(Integer, default=0)
    fours = Column(Integer, default=0)
    sixes = Column(Integer, default=0)

    batter = relationship("Player", foreign_keys=[batter_id])
    bowler = relationship("Player", foreign_keys=[bowler_id])

    __table_args__ = (
        UniqueConstraint("batter_id", "bowler_id", name="uq_batter_bowler"),
        Index("ix_bvb_batter", "batter_id"),
        Index("ix_bvb_bowler", "bowler_id"),
    )


class VenueStats(Base):
    __tablename__ = "venue_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), unique=True, nullable=False)
    matches_played = Column(Integer, default=0)
    avg_first_innings_score = Column(Float, default=0.0)
    avg_second_innings_score = Column(Float, default=0.0)
    bat_first_win_pct = Column(Float, default=0.0)
    highest_score = Column(Integer, default=0)
    lowest_score = Column(Integer, default=0)

    venue = relationship("Venue", back_populates="stats")
