"""
Ingest IPL.csv into the SQLite database.

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    python -m app.ingestion.load_csv
"""

import sys
import re
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text

# Ensure the api directory is on the path when run as a module
API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.database import engine, SessionLocal, Base
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
from typing import Dict, Set

from app.ingestion.team_mappings import (
    normalize_team_name,
    TEAM_SHORT_NAMES,
    ACTIVE_TEAMS,
)

CSV_PATH = Path(__file__).resolve().parents[4] / "IPL.csv"


def _safe_int(val, default=None):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val, default=None):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("na", "nan", "") else default


def run_ingestion():
    print(f"Reading CSV from {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"Loaded {len(df)} rows.")

    # Drop the unnamed index column
    if df.columns[0] == "" or df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=[df.columns[0]])

    # Normalize team names
    for col in ["batting_team", "bowling_team", "match_won_by", "toss_winner"]:
        df[col] = df[col].apply(lambda x: normalize_team_name(str(x)) if pd.notna(x) else x)

    # Normalize stage
    df["stage"] = df["stage"].apply(lambda x: "League" if _safe_str(x) in (None, "Unknown") else str(x).strip())

    # Create tables
    print("Creating database tables ...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        # --- Teams ---
        print("Inserting teams ...")
        all_teams = set()
        for col in ["batting_team", "bowling_team", "match_won_by", "toss_winner"]:
            all_teams.update(df[col].dropna().unique())
        all_teams.discard("Unknown")

        team_map: Dict[str, int] = {}
        for t_name in sorted(all_teams):
            canonical = normalize_team_name(t_name)
            if canonical in team_map:
                continue
            team = Team(
                name=canonical,
                short_name=TEAM_SHORT_NAMES.get(canonical, canonical[:3].upper()),
                is_active=canonical in ACTIVE_TEAMS,
            )
            session.add(team)
            session.flush()
            team_map[canonical] = team.id
        session.commit()
        print(f"  {len(team_map)} teams inserted.")

        # --- Players ---
        print("Inserting players ...")
        all_players: Set[str] = set()
        for col in ["batter", "bowler", "non_striker", "player_out", "player_of_match"]:
            if col in df.columns:
                all_players.update(df[col].dropna().unique())
        all_players.discard("Unknown")
        all_players.discard("NA")

        player_map: Dict[str, int] = {}
        player_objs = []
        for p_name in sorted(all_players):
            name = str(p_name).strip()
            if not name or name in ("Unknown", "NA", "nan"):
                continue
            player_objs.append(Player(name=name))

        session.add_all(player_objs)
        session.flush()
        for p in player_objs:
            player_map[p.name] = p.id
        session.commit()
        print(f"  {len(player_map)} players inserted.")

        # --- Venues ---
        print("Inserting venues ...")
        venue_df = df.groupby("venue").agg({"city": "first"}).reset_index()
        venue_map: Dict[str, int] = {}
        for _, row in venue_df.iterrows():
            v_name = _safe_str(row["venue"])
            if not v_name:
                continue
            venue = Venue(name=v_name, city=_safe_str(row["city"]))
            session.add(venue)
            session.flush()
            venue_map[v_name] = venue.id
        session.commit()
        print(f"  {len(venue_map)} venues inserted.")

        # --- Matches ---
        print("Inserting matches ...")
        match_groups = df.groupby("match_id")
        match_agg = match_groups.first()

        # Compute innings scores per match
        innings_scores = (
            df.groupby(["match_id", "innings"])
            .agg({"team_runs": "max"})
            .reset_index()
        )
        first_inn_scores = innings_scores[innings_scores["innings"] == 1].set_index("match_id")["team_runs"]
        second_inn_scores = innings_scores[innings_scores["innings"] == 2].set_index("match_id")["team_runs"]

        match_db_map: Dict[int, int] = {}  # source_match_id -> db id
        match_objects = []

        for source_mid, row in match_agg.iterrows():
            source_mid = int(source_mid)

            # Parse date
            date_val = None
            raw_date = _safe_str(row.get("date"))
            if raw_date:
                try:
                    date_val = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    pass

            season = _safe_str(row.get("season"), "Unknown")
            stage = _safe_str(row.get("stage"), "League")
            venue_name = _safe_str(row.get("venue"))
            venue_id = venue_map.get(venue_name) if venue_name else None

            batting_team = normalize_team_name(_safe_str(row.get("batting_team"), ""))
            bowling_team = normalize_team_name(_safe_str(row.get("bowling_team"), ""))
            team1_id = team_map.get(batting_team)
            team2_id = team_map.get(bowling_team)

            toss_winner_name = normalize_team_name(_safe_str(row.get("toss_winner"), ""))
            toss_winner_id = team_map.get(toss_winner_name)
            toss_decision = _safe_str(row.get("toss_decision"))

            winner_name = normalize_team_name(_safe_str(row.get("match_won_by"), ""))
            winner_id = team_map.get(winner_name) if winner_name and winner_name != "Unknown" else None

            # Parse win margin and type
            win_outcome_raw = _safe_str(row.get("win_outcome"), "")
            win_margin = None
            win_type = None
            if win_outcome_raw:
                m = re.match(r"(\d+)\s+(runs?|wickets?)", win_outcome_raw)
                if m:
                    win_margin = int(m.group(1))
                    win_type = "runs" if "run" in m.group(2) else "wickets"

            pom_name = _safe_str(row.get("player_of_match"))
            pom_id = player_map.get(pom_name) if pom_name else None

            method = _safe_str(row.get("method"))
            if method in ("NA", "Unknown"):
                method = None

            first_score = _safe_int(first_inn_scores.get(source_mid))
            second_score = _safe_int(second_inn_scores.get(source_mid))

            match_obj = Match(
                source_match_id=source_mid,
                date=date_val,
                season=season,
                stage=stage,
                venue_id=venue_id,
                team1_id=team1_id,
                team2_id=team2_id,
                toss_winner_id=toss_winner_id,
                toss_decision=toss_decision,
                winner_id=winner_id,
                win_margin=win_margin,
                win_type=win_type,
                player_of_match_id=pom_id,
                method=method,
                first_innings_score=first_score,
                second_innings_score=second_score,
            )
            match_objects.append((source_mid, match_obj))

        session.add_all([m for _, m in match_objects])
        session.flush()
        for source_mid, m in match_objects:
            match_db_map[source_mid] = m.id
        session.commit()
        print(f"  {len(match_db_map)} matches inserted.")

        # --- Deliveries ---
        print("Inserting deliveries (this may take a moment) ...")
        delivery_rows = []
        for _, row in df.iterrows():
            source_mid = _safe_int(row.get("match_id"))
            db_match_id = match_db_map.get(source_mid) if source_mid else None
            if db_match_id is None:
                continue

            batter_name = _safe_str(row.get("batter"))
            bowler_name = _safe_str(row.get("bowler"))
            non_striker_name = _safe_str(row.get("non_striker"))
            player_out_name = _safe_str(row.get("player_out"))

            delivery_rows.append(
                {
                    "match_id": db_match_id,
                    "innings": _safe_int(row.get("innings"), 1),
                    "over_num": _safe_int(row.get("over"), 0),
                    "ball_num": _safe_int(row.get("ball"), 0),
                    "batter_id": player_map.get(batter_name),
                    "bowler_id": player_map.get(bowler_name),
                    "non_striker_id": player_map.get(non_striker_name),
                    "bat_pos": _safe_int(row.get("bat_pos")),
                    "runs_batter": _safe_int(row.get("runs_batter"), 0),
                    "runs_extras": _safe_int(row.get("runs_extras"), 0),
                    "runs_total": _safe_int(row.get("runs_total"), 0),
                    "valid_ball": bool(row.get("valid_ball", True)) if pd.notna(row.get("valid_ball")) else True,
                    "extra_type": _safe_str(row.get("extra_type")),
                    "wicket_kind": _safe_str(row.get("wicket_kind")),
                    "player_out_id": player_map.get(player_out_name),
                    "team_runs": _safe_int(row.get("team_runs")),
                    "team_wickets": _safe_int(row.get("team_wicket")),
                }
            )

            # Bulk insert every 50K rows
            if len(delivery_rows) >= 50000:
                session.execute(Delivery.__table__.insert(), delivery_rows)
                session.commit()
                print(f"    ... {len(delivery_rows)} deliveries flushed")
                delivery_rows = []

        if delivery_rows:
            session.execute(Delivery.__table__.insert(), delivery_rows)
            session.commit()
        print("  Deliveries inserted.")

        # --- Aggregates ---
        _compute_batting_aggregates(session, df, player_map, team_map)
        _compute_bowling_aggregates(session, df, player_map, team_map)
        _compute_batter_vs_bowler(session, df, player_map)
        _compute_venue_stats(session, df, venue_map, team_map, match_db_map)

        print("Ingestion complete!")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _compute_batting_aggregates(session, df, player_map, team_map):
    print("Computing batting aggregates ...")
    # Filter to valid batting deliveries
    bat_df = df[df["batter"].notna()].copy()
    bat_df["batter"] = bat_df["batter"].astype(str).str.strip()
    bat_df["batting_team_norm"] = bat_df["batting_team"].apply(
        lambda x: normalize_team_name(str(x)) if pd.notna(x) else None
    )

    # Group by batter, season
    grouped = bat_df.groupby(["batter", "season"])

    records = []
    for (batter_name, season), grp in grouped:
        pid = player_map.get(batter_name)
        if pid is None:
            continue

        # Find team (most common)
        team_name = grp["batting_team_norm"].mode()
        team_name = team_name.iloc[0] if len(team_name) > 0 else None
        team_id = team_map.get(team_name) if team_name else None

        valid = grp[grp["valid_ball"] == True] if "valid_ball" in grp.columns else grp
        matches = grp["match_id"].nunique()

        # Per-innings stats
        innings_grp = grp.groupby("match_id").agg(
            runs=("runs_batter", "sum"),
            balls=("valid_ball", "sum"),
        )
        innings_count = len(innings_grp)

        total_runs = int(innings_grp["runs"].sum())
        total_balls = int(innings_grp["balls"].sum())

        # Dismissals in this season for this batter
        dismissals = grp[
            (grp["player_out"] == batter_name) & grp["wicket_kind"].notna()
        ]["match_id"].count()
        dismissals = int(dismissals)
        not_outs = innings_count - dismissals

        fours = int((grp["runs_batter"] == 4).sum())
        sixes = int((grp["runs_batter"] == 6).sum())

        sr = (total_runs / total_balls * 100) if total_balls > 0 else 0.0
        avg = (total_runs / dismissals) if dismissals > 0 else float(total_runs)

        highest = int(innings_grp["runs"].max()) if len(innings_grp) > 0 else 0
        fifties = int((innings_grp["runs"] >= 50).sum() - (innings_grp["runs"] >= 100).sum())
        hundreds = int((innings_grp["runs"] >= 100).sum())

        records.append(
            {
                "player_id": pid,
                "season": str(season),
                "team_id": team_id,
                "matches": matches,
                "innings": innings_count,
                "runs": total_runs,
                "balls_faced": total_balls,
                "fours": fours,
                "sixes": sixes,
                "strike_rate": round(sr, 2),
                "average": round(avg, 2),
                "highest_score": highest,
                "fifties": max(fifties, 0),
                "hundreds": hundreds,
                "not_outs": max(not_outs, 0),
            }
        )

    if records:
        session.execute(PlayerSeasonBatting.__table__.insert(), records)
        session.commit()
    print(f"  {len(records)} batting season records inserted.")


def _compute_bowling_aggregates(session, df, player_map, team_map):
    print("Computing bowling aggregates ...")
    bowl_df = df[df["bowler"].notna()].copy()
    bowl_df["bowler"] = bowl_df["bowler"].astype(str).str.strip()
    bowl_df["bowling_team_norm"] = bowl_df["bowling_team"].apply(
        lambda x: normalize_team_name(str(x)) if pd.notna(x) else None
    )

    grouped = bowl_df.groupby(["bowler", "season"])
    records = []

    for (bowler_name, season), grp in grouped:
        pid = player_map.get(bowler_name)
        if pid is None:
            continue

        team_name = grp["bowling_team_norm"].mode()
        team_name = team_name.iloc[0] if len(team_name) > 0 else None
        team_id = team_map.get(team_name) if team_name else None

        matches = grp["match_id"].nunique()
        innings = grp.groupby("match_id")["innings"].first().nunique()

        valid_balls = int(grp["valid_ball"].sum())
        overs = valid_balls // 6 + (valid_balls % 6) / 10.0
        runs_conceded = int(grp["runs_total"].sum() - grp["runs_batter"].sum() + grp["runs_batter"].sum())
        # Runs conceded = runs_bowler column if exists, else runs_total
        if "runs_bowler" in grp.columns:
            runs_conceded = int(grp["runs_bowler"].sum())
        else:
            runs_conceded = int(grp["runs_total"].sum())

        wickets_mask = grp["wicket_kind"].notna() & ~grp["wicket_kind"].isin(["run out", "retired hurt", "retired out", "obstructing the field"])
        wickets = int(wickets_mask.sum())

        economy = (runs_conceded / (valid_balls / 6)) if valid_balls > 0 else 0.0
        avg = (runs_conceded / wickets) if wickets > 0 else 0.0

        # Best figures per match
        match_wickets = grp[wickets_mask].groupby("match_id").size()
        match_runs = grp.groupby("match_id")["runs_bowler"].sum() if "runs_bowler" in grp.columns else grp.groupby("match_id")["runs_total"].sum()

        best_w = int(match_wickets.max()) if len(match_wickets) > 0 else 0
        if best_w > 0:
            best_match = match_wickets.idxmax()
            best_r = int(match_runs.get(best_match, 0))
            best_figures = f"{best_w}/{best_r}"
        else:
            best_figures = "0/0"

        four_w = int((match_wickets >= 4).sum()) if len(match_wickets) > 0 else 0
        five_w = int((match_wickets >= 5).sum()) if len(match_wickets) > 0 else 0

        records.append(
            {
                "player_id": pid,
                "season": str(season),
                "team_id": team_id,
                "matches": matches,
                "innings": innings,
                "overs_bowled": round(overs, 1),
                "runs_conceded": runs_conceded,
                "wickets": wickets,
                "economy": round(economy, 2),
                "average": round(avg, 2),
                "best_figures": best_figures,
                "four_wickets": four_w,
                "five_wickets": five_w,
            }
        )

    if records:
        session.execute(PlayerSeasonBowling.__table__.insert(), records)
        session.commit()
    print(f"  {len(records)} bowling season records inserted.")


def _compute_batter_vs_bowler(session, df, player_map):
    print("Computing batter vs bowler stats ...")
    bvb = df[(df["batter"].notna()) & (df["bowler"].notna())].copy()
    bvb["batter"] = bvb["batter"].astype(str).str.strip()
    bvb["bowler"] = bvb["bowler"].astype(str).str.strip()

    grouped = bvb.groupby(["batter", "bowler"])
    records = []

    for (batter_name, bowler_name), grp in grouped:
        bat_id = player_map.get(batter_name)
        bowl_id = player_map.get(bowler_name)
        if bat_id is None or bowl_id is None:
            continue

        valid = grp[grp["valid_ball"] == True] if "valid_ball" in grp.columns else grp
        balls = int(valid.shape[0]) if len(valid) > 0 else int(grp.shape[0])
        runs = int(grp["runs_batter"].sum())

        # Dismissals: wickets where player_out == batter and not run out
        dismiss_mask = (
            (grp["player_out"] == batter_name)
            & grp["wicket_kind"].notna()
            & ~grp["wicket_kind"].isin(["run out", "retired hurt", "retired out", "obstructing the field"])
        )
        dismissals = int(dismiss_mask.sum())
        dots = int((grp["runs_batter"] == 0).sum())
        fours = int((grp["runs_batter"] == 4).sum())
        sixes = int((grp["runs_batter"] == 6).sum())

        records.append(
            {
                "batter_id": bat_id,
                "bowler_id": bowl_id,
                "balls": balls,
                "runs": runs,
                "dismissals": dismissals,
                "dots": dots,
                "fours": fours,
                "sixes": sixes,
            }
        )

    if records:
        # Insert in chunks
        chunk = 10000
        for i in range(0, len(records), chunk):
            session.execute(BatterVsBowler.__table__.insert(), records[i : i + chunk])
        session.commit()
    print(f"  {len(records)} batter vs bowler records inserted.")


def _compute_venue_stats(session, df, venue_map, team_map, match_db_map):
    print("Computing venue stats ...")
    match_df = df.groupby("match_id").first().reset_index()

    innings_scores = (
        df.groupby(["match_id", "innings"])
        .agg({"team_runs": "max"})
        .reset_index()
    )
    first_inn = innings_scores[innings_scores["innings"] == 1]
    second_inn = innings_scores[innings_scores["innings"] == 2]

    records = []
    for venue_name, venue_id in venue_map.items():
        venue_matches = match_df[match_df["venue"] == venue_name]
        matches_played = len(venue_matches)
        if matches_played == 0:
            continue

        venue_match_ids = venue_matches["match_id"].values
        fi = first_inn[first_inn["match_id"].isin(venue_match_ids)]["team_runs"]
        si = second_inn[second_inn["match_id"].isin(venue_match_ids)]["team_runs"]

        avg_fi = float(fi.mean()) if len(fi) > 0 else 0.0
        avg_si = float(si.mean()) if len(si) > 0 else 0.0

        # Bat first win %: winner == batting_team of innings 1
        first_bat = df[df["match_id"].isin(venue_match_ids) & (df["innings"] == 1)].groupby("match_id")["batting_team"].first()
        winners = venue_matches.set_index("match_id")["match_won_by"]
        bat_first_wins = 0
        total_decided = 0
        for mid in venue_match_ids:
            fb = first_bat.get(mid)
            w = winners.get(mid)
            if fb and w and w != "Unknown" and pd.notna(w):
                total_decided += 1
                # Normalize both for comparison
                if normalize_team_name(str(fb)) == normalize_team_name(str(w)):
                    bat_first_wins += 1

        bat_first_pct = (bat_first_wins / total_decided * 100) if total_decided > 0 else 50.0

        all_scores = pd.concat([fi, si])
        highest = int(all_scores.max()) if len(all_scores) > 0 else 0
        lowest = int(all_scores.min()) if len(all_scores) > 0 else 0

        records.append(
            {
                "venue_id": venue_id,
                "matches_played": matches_played,
                "avg_first_innings_score": round(avg_fi, 1),
                "avg_second_innings_score": round(avg_si, 1),
                "bat_first_win_pct": round(bat_first_pct, 1),
                "highest_score": highest,
                "lowest_score": lowest,
            }
        )

    if records:
        session.execute(VenueStats.__table__.insert(), records)
        session.commit()
    print(f"  {len(records)} venue stats records inserted.")


if __name__ == "__main__":
    run_ingestion()
