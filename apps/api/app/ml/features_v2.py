"""
Advanced feature engineering for IPL win prediction.

Builds ~45 features per match using rolling team stats, head-to-head,
venue characteristics, toss, and phase-wise scoring from ball-by-ball data.

All features use only data available BEFORE each match (no leakage).
"""

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional


def load_all_data(db: Session) -> dict:
    """Load all match and delivery data into DataFrames for fast computation."""
    engine = db.get_bind()

    matches = pd.read_sql(text("""
        SELECT m.id, m.date, m.season, m.stage, m.venue_id,
               m.team1_id, m.team2_id, m.toss_winner_id, m.toss_decision,
               m.winner_id, m.first_innings_score, m.second_innings_score,
               v.city as venue_city
        FROM matches m
        LEFT JOIN venues v ON m.venue_id=v.id
        WHERE m.winner_id IS NOT NULL AND m.team1_id IS NOT NULL AND m.team2_id IS NOT NULL
        ORDER BY m.date, m.id
    """), engine)

    # Phase-wise innings stats from deliveries
    innings_stats = pd.read_sql(text("""
        SELECT d.match_id, d.innings,
            MAX(d.team_runs) as total_runs,
            MAX(d.team_wickets) as total_wickets,
            SUM(CASE WHEN d.over_num <= 5 AND d.valid_ball=true THEN d.runs_total ELSE 0 END) as pp_runs,
            SUM(CASE WHEN d.over_num BETWEEN 6 AND 14 AND d.valid_ball=true THEN d.runs_total ELSE 0 END) as middle_runs,
            SUM(CASE WHEN d.over_num >= 15 AND d.valid_ball=true THEN d.runs_total ELSE 0 END) as death_runs,
            SUM(CASE WHEN d.over_num <= 5 AND d.valid_ball=true THEN 1 ELSE 0 END) as pp_balls,
            SUM(CASE WHEN d.over_num >= 15 AND d.valid_ball=true THEN 1 ELSE 0 END) as death_balls,
            SUM(CASE WHEN d.runs_batter >= 4 THEN 1 ELSE 0 END) as boundaries,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.valid_ball=true AND d.runs_total=0 THEN 1 ELSE 0 END) as dots
        FROM deliveries d
        GROUP BY d.match_id, d.innings
    """), engine)

    return {"matches": matches, "innings_stats": innings_stats}


def merge_innings_data(matches: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    """Merge per-innings stats onto match rows."""
    inn1 = innings[innings["innings"] == 1].rename(
        columns={c: f"inn1_{c}" for c in innings.columns if c not in ("match_id", "innings")}
    )
    inn2 = innings[innings["innings"] == 2].rename(
        columns={c: f"inn2_{c}" for c in innings.columns if c not in ("match_id", "innings")}
    )
    matches = matches.merge(inn1.drop(columns=["innings"]), left_on="id", right_on="match_id", how="left")
    matches = matches.merge(inn2.drop(columns=["innings"]), left_on="id", right_on="match_id", how="left", suffixes=("", "_2"))
    return matches


def build_team_match_records(matches: pd.DataFrame) -> pd.DataFrame:
    """Build per-team-per-match records from merged match data."""
    records = []
    for _, m in matches.iterrows():
        for team_col, opp_col, batting_first in [("team1_id", "team2_id", True), ("team2_id", "team1_id", False)]:
            team_id = m[team_col]
            opp_id = m[opp_col]
            won = 1 if m["winner_id"] == team_id else 0

            if batting_first:
                score = m.get("inn1_total_runs", m.get("first_innings_score"))
                pp = m.get("inn1_pp_runs")
                death = m.get("inn1_death_runs")
                bounds = m.get("inn1_boundaries")
                s6 = m.get("inn1_sixes")
                dots = m.get("inn1_dots")
                opp_score = m.get("inn2_total_runs", m.get("second_innings_score"))
            else:
                score = m.get("inn2_total_runs", m.get("second_innings_score"))
                pp = m.get("inn2_pp_runs")
                death = m.get("inn2_death_runs")
                bounds = m.get("inn2_boundaries")
                s6 = m.get("inn2_sixes")
                dots = m.get("inn2_dots")
                opp_score = m.get("inn1_total_runs", m.get("first_innings_score"))

            records.append({
                "match_id": m["id"],
                "date": m["date"],
                "team_id": team_id,
                "opp_id": opp_id,
                "venue_id": m["venue_id"],
                "batting_first": batting_first,
                "won": won,
                "score": score,
                "opp_score": opp_score,
                "pp_runs": pp,
                "death_runs": death,
                "boundaries": bounds,
                "sixes": s6,
                "dots": dots,
            })
    return pd.DataFrame(records)


def build_feature_matrix(data: dict) -> tuple:
    """Build feature matrix for all matches.

    Returns (X, y, match_ids, feature_names) where X[i] corresponds to match_ids[i].
    """
    matches = data["matches"].copy()
    innings = data["innings_stats"]

    matches = merge_innings_data(matches, innings)
    tmr = build_team_match_records(matches)

    # Now build rolling features for each match
    feature_rows = []
    feature_names = None

    for idx, m in matches.iterrows():
        prior = matches.iloc[:idx]  # all matches before this one
        if len(prior) < 20:
            continue  # need minimum history

        features, names = _compute_match_features(m, prior, tmr, matches)
        if features is not None:
            label = 1 if m["winner_id"] == m["team1_id"] else 0
            feature_rows.append({"match_id": m["id"], "season": m["season"], "features": features, "label": label})
            if feature_names is None:
                feature_names = names

    X = np.array([r["features"] for r in feature_rows])
    y = np.array([r["label"] for r in feature_rows])
    match_ids = [r["match_id"] for r in feature_rows]
    seasons = [r["season"] for r in feature_rows]

    return X, y, match_ids, seasons, feature_names


def _compute_match_features(match, prior_matches, tmr, all_matches) -> tuple:
    """Compute ~45 features for a single match using only prior data."""
    t1 = match["team1_id"]
    t2 = match["team2_id"]
    vid = match["venue_id"]
    mid = match["id"]

    # Filter team-match records to prior matches only
    prior_ids = set(prior_matches["id"])
    tmr_prior = tmr[tmr["match_id"].isin(prior_ids)]

    t1_records = tmr_prior[tmr_prior["team_id"] == t1].sort_values("date", ascending=False)
    t2_records = tmr_prior[tmr_prior["team_id"] == t2].sort_values("date", ascending=False)

    features = []
    names = []

    # === TEAM 1 FEATURES ===
    for prefix, records in [("t1", t1_records), ("t2", t2_records)]:
        # Overall win %
        win_pct = records["won"].mean() if len(records) > 0 else 0.5
        features.append(win_pct)
        names.append(f"{prefix}_win_pct_all")

        # Last 10 win %
        last10 = records.head(10)
        features.append(last10["won"].mean() if len(last10) > 0 else 0.5)
        names.append(f"{prefix}_win_pct_10")

        # Last 5 win %
        last5 = records.head(5)
        features.append(last5["won"].mean() if len(last5) > 0 else 0.5)
        names.append(f"{prefix}_win_pct_5")

        # Avg score last 10
        last10_scores = last10["score"].dropna()
        features.append(last10_scores.mean() / 200.0 if len(last10_scores) > 0 else 0.75)
        names.append(f"{prefix}_avg_score_10")

        # Avg batting first score
        bf = records[records["batting_first"] == True].head(10)
        features.append(bf["score"].dropna().mean() / 200.0 if len(bf) > 0 else 0.75)
        names.append(f"{prefix}_avg_bat_first_10")

        # Avg batting second score
        bs = records[records["batting_first"] == False].head(10)
        features.append(bs["score"].dropna().mean() / 200.0 if len(bs) > 0 else 0.75)
        names.append(f"{prefix}_avg_bat_second_10")

        # Powerplay avg runs last 10
        pp = last10["pp_runs"].dropna()
        features.append(pp.mean() / 60.0 if len(pp) > 0 else 0.7)
        names.append(f"{prefix}_pp_avg_10")

        # Death overs avg runs last 10
        death = last10["death_runs"].dropna()
        features.append(death.mean() / 70.0 if len(death) > 0 else 0.7)
        names.append(f"{prefix}_death_avg_10")

        # Boundaries per match
        bounds = last10["boundaries"].dropna()
        features.append(bounds.mean() / 30.0 if len(bounds) > 0 else 0.5)
        names.append(f"{prefix}_boundaries_10")

        # Sixes per match
        s6 = last10["sixes"].dropna()
        features.append(s6.mean() / 15.0 if len(s6) > 0 else 0.5)
        names.append(f"{prefix}_sixes_10")

        # Dot ball %
        dots = last10["dots"].dropna()
        features.append(dots.mean() / 120.0 if len(dots) > 0 else 0.4)
        names.append(f"{prefix}_dots_10")

    # === HEAD TO HEAD (4 features) ===
    h2h = prior_matches[
        ((prior_matches["team1_id"] == t1) & (prior_matches["team2_id"] == t2)) |
        ((prior_matches["team1_id"] == t2) & (prior_matches["team2_id"] == t1))
    ]
    h2h_total = len(h2h)
    h2h_t1_wins = len(h2h[h2h["winner_id"] == t1])

    features.append(h2h_t1_wins / h2h_total if h2h_total > 0 else 0.5)
    names.append("h2h_t1_win_pct")

    # Last 5 H2H
    h2h_last5 = h2h.tail(5)
    features.append(len(h2h_last5[h2h_last5["winner_id"] == t1]) / len(h2h_last5) if len(h2h_last5) > 0 else 0.5)
    names.append("h2h_t1_win_pct_5")

    # H2H matches played (log scaled)
    features.append(min(np.log1p(h2h_total) / 4.0, 1.0))
    names.append("h2h_matches_log")

    # H2H score difference
    h2h_score_diff = 0
    if h2h_total > 0:
        for _, hm in h2h.iterrows():
            if hm["winner_id"] == t1:
                h2h_score_diff += 1
            else:
                h2h_score_diff -= 1
        h2h_score_diff /= h2h_total
    features.append((h2h_score_diff + 1) / 2.0)  # normalize to 0-1
    names.append("h2h_dominance")

    # === VENUE FEATURES (6 features) ===
    venue_matches = prior_matches[prior_matches["venue_id"] == vid]
    venue_total = len(venue_matches)

    # Bat first win % at venue
    if venue_total > 0:
        bat_first_wins = len(venue_matches[venue_matches["winner_id"] == venue_matches["team1_id"]])
        features.append(bat_first_wins / venue_total)
    else:
        features.append(0.5)
    names.append("venue_bat_first_win_pct")

    # Avg first innings score at venue
    venue_inn = tmr_prior[(tmr_prior["match_id"].isin(set(venue_matches["id"]))) & (tmr_prior["batting_first"] == True)]
    features.append(venue_inn["score"].dropna().mean() / 200.0 if len(venue_inn) > 0 else 0.75)
    names.append("venue_avg_first_inn")

    # Avg second innings score at venue
    venue_inn2 = tmr_prior[(tmr_prior["match_id"].isin(set(venue_matches["id"]))) & (tmr_prior["batting_first"] == False)]
    features.append(venue_inn2["score"].dropna().mean() / 200.0 if len(venue_inn2) > 0 else 0.72)
    names.append("venue_avg_second_inn")

    # Venue PP run rate
    venue_pp = venue_inn["pp_runs"].dropna()
    features.append(venue_pp.mean() / 60.0 if len(venue_pp) > 0 else 0.7)
    names.append("venue_pp_avg")

    # Venue death run rate
    venue_death = venue_inn["death_runs"].dropna()
    features.append(venue_death.mean() / 70.0 if len(venue_death) > 0 else 0.7)
    names.append("venue_death_avg")

    # Venue matches played (more = more reliable)
    features.append(min(np.log1p(venue_total) / 5.0, 1.0))
    names.append("venue_matches_log")

    # === TOSS FEATURES (3 features) ===
    toss_is_t1 = 1.0 if match["toss_winner_id"] == t1 else 0.0
    toss_bat = 1.0 if match["toss_decision"] == "bat" else 0.0

    features.append(toss_is_t1)
    names.append("toss_is_team1")

    features.append(toss_bat)
    names.append("toss_chose_bat")

    # Toss-venue interaction: toss winner batting first at high-scoring venue
    features.append(toss_is_t1 * toss_bat * features[names.index("venue_avg_first_inn")])
    names.append("toss_venue_interaction")

    # === CONTEXT FEATURES (3 features) ===
    # Stage
    stage = str(match.get("stage", "")).lower()
    if "final" in stage:
        stage_val = 1.0
    elif "qualifier" in stage or "eliminator" in stage:
        stage_val = 0.7
    else:
        stage_val = 0.0
    features.append(stage_val)
    names.append("is_knockout")

    # Home advantage
    venue_city = str(match.get("venue_city", "")).lower()
    # Simple: check if team has played many matches at this venue
    t1_at_venue = tmr_prior[(tmr_prior["team_id"] == t1) & (tmr_prior["match_id"].isin(set(venue_matches["id"])))]
    t2_at_venue = tmr_prior[(tmr_prior["team_id"] == t2) & (tmr_prior["match_id"].isin(set(venue_matches["id"])))]
    home_adv = 0.5
    if len(t1_at_venue) > 3 and len(t2_at_venue) > 3:
        home_adv = t1_at_venue["won"].mean() - t2_at_venue["won"].mean()
        home_adv = (home_adv + 1) / 2.0  # normalize
    features.append(home_adv)
    names.append("home_advantage")

    # Relative strength: team1 win% - team2 win% (key feature)
    features.append(features[names.index("t1_win_pct_all")] - features[names.index("t2_win_pct_all")] + 0.5)
    names.append("relative_strength")

    return np.array(features, dtype=np.float32), names


def build_prediction_features(db: Session, team1_id: int, team2_id: int,
                               venue_id: int, toss_winner_id: int = None,
                               toss_decision: str = None) -> np.ndarray:
    """Build features for a new prediction using latest available data."""
    data = load_all_data(db)
    matches = data["matches"]
    tmr_list = []
    innings = data["innings_stats"]

    # Build tmr from all data
    inn1 = innings[innings["innings"] == 1].set_index("match_id")
    inn2 = innings[innings["innings"] == 2].set_index("match_id")

    for _, m in matches.iterrows():
        for team_col, batting_first in [("team1_id", True), ("team2_id", False)]:
            tid = m[team_col]
            mid = m["id"]
            inn = inn1 if batting_first else inn2
            row = inn.loc[mid] if mid in inn.index else pd.Series()
            tmr_list.append({
                "match_id": mid, "date": m["date"], "team_id": tid,
                "opp_id": m["team2_id"] if batting_first else m["team1_id"],
                "venue_id": m["venue_id"], "batting_first": batting_first,
                "won": 1 if m["winner_id"] == tid else 0,
                "score": row.get("total_runs", m.get("first_innings_score") if batting_first else m.get("second_innings_score")),
                "opp_score": None,
                "pp_runs": row.get("pp_runs"), "death_runs": row.get("death_runs"),
                "boundaries": row.get("boundaries"), "sixes": row.get("sixes"),
                "dots": row.get("dots"),
            })

    tmr = pd.DataFrame(tmr_list)

    # Create a fake match row for feature computation
    fake_match = pd.Series({
        "id": -1, "date": "9999-12-31", "season": "2026", "stage": "League",
        "venue_id": venue_id, "team1_id": team1_id, "team2_id": team2_id,
        "toss_winner_id": toss_winner_id or team1_id,
        "toss_decision": toss_decision or "bat",
        "winner_id": None, "venue_city": "",
    })

    features, _ = _compute_match_features(fake_match, matches, tmr, matches)
    return features
