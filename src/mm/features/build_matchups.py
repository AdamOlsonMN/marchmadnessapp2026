"""
Build pairwise matchup rows for training and prediction.

Each row = one game with pregame features only (no leakage).
Label: 1 if lower TeamID wins, 0 otherwise (Kaggle convention).
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Default paths
DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"
DEFAULT_PROCESSED_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"


def _seed_to_int(seed: str) -> int:
    """Parse seed string like 'W01' or 'X16' to numeric 1-16."""
    if isinstance(seed, (int, float)) and not np.isnan(seed):
        return int(seed)
    s = str(seed).strip()
    for i, c in enumerate(s):
        if c.isdigit():
            return int(s[i:].replace("a", "").replace("b", "").strip() or 1)
    return 16


def rolling_win_rates(
    regular: pd.DataFrame,
    through_day: Optional[int] = None,
    min_games: int = 5,
) -> pd.DataFrame:
    """
    For each (Season, TeamID) compute win rate over games up to through_day.
    Returns DataFrame with columns Season, TeamID, wins, games, win_rate.
    """
    if through_day is not None:
        reg = regular[regular["DayNum"] <= through_day].copy()
    else:
        reg = regular.copy()

    wins = reg.groupby(["Season", "WTeamID"]).size().reset_index(name="wins")
    losses = reg.groupby(["Season", "LTeamID"]).size().reset_index(name="losses")
    wins = wins.rename(columns={"WTeamID": "TeamID"})
    losses = losses.rename(columns={"LTeamID": "TeamID"})

    team_games = wins.merge(
        losses, on=["Season", "TeamID"], how="outer"
    ).fillna(0)
    team_games["games"] = team_games["wins"] + team_games["losses"]
    team_games["win_rate"] = np.where(
        team_games["games"] >= min_games,
        team_games["wins"] / team_games["games"],
        np.nan,
    )
    return team_games[["Season", "TeamID", "wins", "games", "win_rate"]]


def season_point_margins(regular: pd.DataFrame) -> pd.DataFrame:
    """Average point diff (pf - pa) per team per season. Use as strength proxy."""
    reg = regular.copy()
    reg["WScore"] = reg["WScore"].astype(float)
    reg["LScore"] = reg["LScore"].astype(float)
    w = reg.groupby(["Season", "WTeamID"]).agg(
        pf=("WScore", "sum"), pa=("LScore", "sum"), n=("Season", "size")
    ).reset_index()
    w = w.rename(columns={"WTeamID": "TeamID"})
    l = reg.groupby(["Season", "LTeamID"]).agg(
        pf=("LScore", "sum"), pa=("WScore", "sum"), n=("Season", "size")
    ).reset_index()
    l = l.rename(columns={"LTeamID": "TeamID"})
    combined = pd.concat([
        w.assign(win=1),
        l.assign(win=0),
    ], ignore_index=True)
    grp = combined.groupby(["Season", "TeamID"])
    out = grp.agg(
        pf=("pf", "sum"),
        pa=("pa", "sum"),
        games=("n", "sum"),
    ).reset_index()
    out["point_margin_per_game"] = (out["pf"] - out["pa"]) / out["games"]
    return out[["Season", "TeamID", "games", "point_margin_per_game"]]


def last_n_win_rate(
    regular: pd.DataFrame,
    n: int = 10,
    through_day: Optional[int] = 132,
    min_games: int = 1,
) -> pd.DataFrame:
    """Win rate over each team's last n games before through_day. Columns: Season, TeamID, last_n_win_rate."""
    reg = regular[regular["DayNum"] <= through_day].copy() if through_day is not None else regular.copy()
    reg = reg.sort_values(["Season", "DayNum"])
    # Long format: one row per team per game (compact has WTeamID, LTeamID)
    long_w = reg[["Season", "DayNum", "WTeamID"]].rename(columns={"WTeamID": "TeamID"})
    long_w["Win"] = 1
    long_l = reg[["Season", "DayNum", "LTeamID"]].rename(columns={"LTeamID": "TeamID"})
    long_l["Win"] = 0
    long = pd.concat([long_w, long_l], ignore_index=True)
    rows = []
    for (season, team_id), grp in long.groupby(["Season", "TeamID"]):
        grp = grp.sort_values("DayNum").tail(n)
        wins = grp["Win"].sum()
        rate = wins / len(grp) if len(grp) >= min_games else np.nan
        rows.append({"Season": season, "TeamID": team_id, "last_n_win_rate": rate})
    out = pd.DataFrame(rows)
    return out


def avg_opponent_win_rate(
    regular: pd.DataFrame,
    through_day: Optional[int] = 132,
    win_rates: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Per (Season, TeamID), average win rate of opponents. Columns: Season, TeamID, avg_opp_win_rate."""
    if through_day is not None:
        reg = regular[regular["DayNum"] <= through_day].copy()
    else:
        reg = regular.copy()
    if win_rates is None:
        win_rates = rolling_win_rates(reg, through_day=None)
    wr_map = win_rates.set_index(["Season", "TeamID"])["win_rate"].to_dict()
    rows = []
    for _, r in reg.iterrows():
        season = int(r["Season"])
        w, l = int(r["WTeamID"]), int(r["LTeamID"])
        for team_id, opp in [(w, l), (l, w)]:
            rows.append((season, team_id, wr_map.get((season, opp), 0.5)))
    if not rows:
        return pd.DataFrame(columns=["Season", "TeamID", "avg_opp_win_rate"])
    tmp = pd.DataFrame(rows, columns=["Season", "TeamID", "opp_wr"])
    out = tmp.groupby(["Season", "TeamID"])["opp_wr"].mean().reset_index()
    out = out.rename(columns={"opp_wr": "avg_opp_win_rate"})
    return out


def latest_massey_ranks(massey: pd.DataFrame, through_day: int = 132) -> pd.DataFrame:
    """For each (Season, TeamID) return best (lowest) OrdinalRank on or before through_day."""
    m = massey[massey["RankingDayNum"] <= through_day].copy()
    rank_col = "OrdinalRank" if "OrdinalRank" in m.columns else "Ordinal_Rank"
    # Best rank = min ordinal (1 = best)
    best = m.groupby(["Season", "TeamID"])[rank_col].min().reset_index()
    best = best.rename(columns={rank_col: "massey_rank"})
    return best


def build_tourney_matchups(
    seeds: pd.DataFrame,
    tourney_results: pd.DataFrame,
    regular: pd.DataFrame,
    massey: Optional[pd.DataFrame] = None,
    through_day: int = 132,
) -> pd.DataFrame:
    """
    Build one row per historical tournament game with pregame features.
    Features: seed diff, win_rate diff, point_margin diff, massey rank diff.
    Label: 1 if lower TeamID won, 0 otherwise.
    """
    seeds = seeds.copy()
    seeds["seed_num"] = seeds["Seed"].map(_seed_to_int)

    win_rates = rolling_win_rates(regular, through_day=through_day)
    margins = season_point_margins(regular)
    last10 = last_n_win_rate(regular, n=10, through_day=through_day)
    sos_df = avg_opponent_win_rate(regular, through_day=through_day, win_rates=win_rates)
    massey_df = latest_massey_ranks(massey, through_day) if massey is not None else None

    rows = []
    for _, row in tourney_results.iterrows():
        season = row["Season"]
        wid = int(row["WTeamID"])
        lid = int(row["LTeamID"])
        # Kaggle: lower TeamID is "team1", label = 1 if team1 wins
        team1 = min(wid, lid)
        team2 = max(wid, lid)
        label = 1 if wid == team1 else 0

        s1 = seeds[(seeds["Season"] == season) & (seeds["TeamID"] == team1)]
        s2 = seeds[(seeds["Season"] == season) & (seeds["TeamID"] == team2)]
        seed1 = s1["seed_num"].iloc[0] if len(s1) else 8
        seed2 = s2["seed_num"].iloc[0] if len(s2) else 8

        wr1 = win_rates[(win_rates["Season"] == season) & (win_rates["TeamID"] == team1)]
        wr2 = win_rates[(win_rates["Season"] == season) & (win_rates["TeamID"] == team2)]
        win_rate1 = wr1["win_rate"].iloc[0] if len(wr1) else 0.5
        win_rate2 = wr2["win_rate"].iloc[0] if len(wr2) else 0.5
        if np.isnan(win_rate1):
            win_rate1 = 0.5
        if np.isnan(win_rate2):
            win_rate2 = 0.5

        m1 = margins[(margins["Season"] == season) & (margins["TeamID"] == team1)]
        m2 = margins[(margins["Season"] == season) & (margins["TeamID"] == team2)]
        margin1 = m1["point_margin_per_game"].iloc[0] if len(m1) else 0.0
        margin2 = m2["point_margin_per_game"].iloc[0] if len(m2) else 0.0

        seed_diff = seed1 - seed2  # positive = team1 higher seed (better)
        win_rate_diff = win_rate1 - win_rate2
        margin_diff = margin1 - margin2

        massey1 = np.nan
        massey2 = np.nan
        if massey_df is not None:
            r1 = massey_df[(massey_df["Season"] == season) & (massey_df["TeamID"] == team1)]
            r2 = massey_df[(massey_df["Season"] == season) & (massey_df["TeamID"] == team2)]
            if len(r1):
                massey1 = r1["massey_rank"].iloc[0]
            if len(r2):
                massey2 = r2["massey_rank"].iloc[0]
        massey_diff = (np.nanmean([massey2, 100]) - np.nanmean([massey1, 100])) if (np.isnan(massey1) or np.isnan(massey2)) else (massey2 - massey1)  # lower rank = better
        massey_diff = massey_diff if not np.isnan(massey_diff) else 0.0

        l10_1 = last10[(last10["Season"] == season) & (last10["TeamID"] == team1)]["last_n_win_rate"].iloc[0] if len(last10[(last10["Season"] == season) & (last10["TeamID"] == team1)]) else 0.5
        l10_2 = last10[(last10["Season"] == season) & (last10["TeamID"] == team2)]["last_n_win_rate"].iloc[0] if len(last10[(last10["Season"] == season) & (last10["TeamID"] == team2)]) else 0.5
        if np.isnan(l10_1):
            l10_1 = 0.5
        if np.isnan(l10_2):
            l10_2 = 0.5
        last10_diff = l10_1 - l10_2

        sos1 = sos_df[(sos_df["Season"] == season) & (sos_df["TeamID"] == team1)]["avg_opp_win_rate"].iloc[0] if len(sos_df[(sos_df["Season"] == season) & (sos_df["TeamID"] == team1)]) else 0.5
        sos2 = sos_df[(sos_df["Season"] == season) & (sos_df["TeamID"] == team2)]["avg_opp_win_rate"].iloc[0] if len(sos_df[(sos_df["Season"] == season) & (sos_df["TeamID"] == team2)]) else 0.5
        if np.isnan(sos1):
            sos1 = 0.5
        if np.isnan(sos2):
            sos2 = 0.5
        sos_diff = sos1 - sos2

        seed_massey_interaction = seed_diff * (massey_diff / 50.0)  # scale for stability

        rows.append({
            "Season": season,
            "Team1": team1,
            "Team2": team2,
            "Seed1": seed1,
            "Seed2": seed2,
            "SeedDiff": seed_diff,
            "WinRate1": win_rate1,
            "WinRate2": win_rate2,
            "WinRateDiff": win_rate_diff,
            "Margin1": margin1,
            "Margin2": margin2,
            "MarginDiff": margin_diff,
            "MasseyDiff": massey_diff,
            "Last10WinRateDiff": last10_diff,
            "SOSDiff": sos_diff,
            "SeedMasseyInteraction": seed_massey_interaction,
            "Label": label,
        })

    return pd.DataFrame(rows)


def feature_columns() -> list[str]:
    """Column names used as model features (numeric, no label)."""
    return [
        "SeedDiff",
        "WinRateDiff",
        "MarginDiff",
        "MasseyDiff",
        "Last10WinRateDiff",
        "SOSDiff",
        "SeedMasseyInteraction",
    ]


def build_and_save(
    raw_dir: Path = DEFAULT_RAW_DIR,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
) -> pd.DataFrame:
    """Load Kaggle data, build matchup DataFrame, save to processed dir, return it."""
    from mm.data.kaggle_loader import load_all

    data = load_all(raw_dir)
    if "seeds" not in data or "tourney" not in data or "regular" not in data:
        raise FileNotFoundError("Need seeds, tourney, and regular season data in raw_dir")
    seeds = data["seeds"]
    tourney = data["tourney"]
    regular = data["regular"]
    massey = data.get("massey")

    df = build_tourney_matchups(seeds, tourney, regular, massey=massey)
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / "matchups.parquet"
    df.to_parquet(out_path, index=False)
    return df
