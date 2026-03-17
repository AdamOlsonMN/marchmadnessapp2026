"""
Team-strength enrichment from Sports-Reference or cached data.

To avoid scraping limits/ToS issues, prefer loading from a cached CSV in data/raw/
(e.g. season_ratings.csv with columns: season, team_id or team_name, srs, sos, ortg, drtg, ...).
If you have such a file, place it in data/raw/ and pass its path to load_season_ratings().

Optional: implement a one-off fetch behind a --fetch flag or script for manual runs.
"""

from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

# Expected columns for cached season ratings (optional enrichment)
RATINGS_COLUMNS = [
    "season",
    "team_id",  # or team_name; must join to Kaggle TeamID via resolver
    "srs",
    "sos",
    "ortg",
    "drtg",
    "pace",
    "efg_pct",
    "tov_pct",
    "orb_pct",
    "ftr",
]


def load_season_ratings(
    path: Optional[Path] = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
) -> Optional[pd.DataFrame]:
    """
    Load optional season-level ratings (SRS, SOS, efficiency, etc.).
    Returns None if no file found. Caller should handle missing enrichment.
    """
    if path is None:
        for name in ("season_ratings.csv", "sports_ref_ratings.csv", "team_ratings.csv"):
            p = raw_dir / name
            if p.exists():
                path = p
                break
    if path is None or not path.exists():
        return None
    df = pd.read_csv(path)
    # Ensure season column exists
    if "season" not in df.columns and "Season" in df.columns:
        df = df.rename(columns={"Season": "season"})
    if "season" not in df.columns and len(df.columns) > 0:
        df["season"] = pd.NA
    return df


def validate_teams_schema(teams_df: pd.DataFrame) -> list[str]:
    """Validate teams dataframe has required columns. Returns list of errors."""
    errs = []
    if "TeamID" not in teams_df.columns:
        errs.append("teams: missing column TeamID")
        return errs
    if teams_df.duplicated(subset=["TeamID"]).any():
        errs.append("teams: duplicate TeamID")
    return errs


def validate_seeds_schema(seeds_df: pd.DataFrame) -> list[str]:
    """Validate seeds dataframe. Returns list of errors."""
    errs = []
    for col in ("Season", "Seed", "TeamID"):
        if col not in seeds_df.columns:
            errs.append(f"seeds: missing column {col}")
    if seeds_df.duplicated(subset=["Season", "TeamID"]).any():
        errs.append("seeds: duplicate (Season, TeamID)")
    return errs


def validate_results_schema(results_df: pd.DataFrame, name: str) -> list[str]:
    """Validate compact results dataframe. Returns list of errors."""
    errs = []
    for col in ("Season", "DayNum", "WTeamID", "LTeamID", "WScore", "LScore"):
        if col not in results_df.columns:
            errs.append(f"{name}: missing column {col}")
    if not errs and (results_df["WTeamID"] == results_df["LTeamID"]).any():
        errs.append(f"{name}: same team as winner and loser")
    return errs


def validate_massey_schema(massey_df: pd.DataFrame) -> list[str]:
    """Validate Massey ordinals dataframe. Returns list of errors."""
    errs = []
    required = ["Season", "RankingDayNum", "SystemName", "TeamID"]
    for col in required:
        if col not in massey_df.columns:
            errs.append(f"massey: missing column {col}")
    if "OrdinalRank" not in massey_df.columns and "Ordinal_Rank" not in massey_df.columns:
        errs.append("massey: missing column OrdinalRank or Ordinal_Rank")
    return errs
