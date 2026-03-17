"""
Load March Machine Learning Mania data from Kaggle CSV files.

Expects files in data/raw/ with names like:
  MTeams.csv, MSeasons.csv, MNCAATourneySeeds.csv,
  MRegularSeasonCompactResults.csv, MNCAATourneyCompactResults.csv,
  MMasseyOrdinals.csv
Men's prefix can be M or NCAAM; women's W or NCAAW.
"""

from pathlib import Path
from typing import Optional

import pandas as pd


# Default subfolder under project root for raw data
DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


def _find_file(raw_dir: Path, *candidates: str) -> Optional[Path]:
    """Return path to first existing file among candidates (with or without .csv)."""
    for name in candidates:
        p = raw_dir / name
        if p.exists():
            return p
        if not name.endswith(".csv"):
            p = raw_dir / f"{name}.csv"
            if p.exists():
                return p
    return None


def load_teams(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load team list. Columns: TeamID, TeamName (or similar)."""
    path = _find_file(raw_dir, "MTeams.csv", "NCAAMTeams.csv", "MTeams")
    if path is None:
        raise FileNotFoundError(f"No teams file found in {raw_dir}")
    df = pd.read_csv(path)
    # Normalize column names to TeamID, TeamName
    rename = {}
    for c in df.columns:
        if "team" in c.lower() and "id" in c.lower():
            rename[c] = "TeamID"
        elif "name" in c.lower() or "team" in c.lower():
            rename[c] = "TeamName"
    df = df.rename(columns=rename)
    if "TeamID" not in df.columns:
        df = df.rename(columns={df.columns[0]: "TeamID"})
    if "TeamName" not in df.columns and len(df.columns) >= 2:
        df = df.rename(columns={df.columns[1]: "TeamName"})
    return df


def load_seasons(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load season metadata. At least Season."""
    path = _find_file(raw_dir, "MSeasons.csv", "NCAAMSeasons.csv", "MSeasons")
    if path is None:
        raise FileNotFoundError(f"No seasons file found in {raw_dir}")
    return pd.read_csv(path)


def load_tourney_seeds(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load tournament seeds. Columns: Season, Seed, TeamID (Seed e.g. W01, X16)."""
    path = _find_file(
        raw_dir, "MNCAATourneySeeds.csv", "NCAAMNCAATourneySeeds.csv", "MNCAATourneySeeds"
    )
    if path is None:
        raise FileNotFoundError(f"No tourney seeds file found in {raw_dir}")
    df = pd.read_csv(path)
    if "TeamID" not in df.columns and "Team_Id" in df.columns:
        df = df.rename(columns={"Team_Id": "TeamID"})
    return df


def load_regular_season_compact(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load regular season game results. Columns: Season, DayNum, WTeamID, LTeamID, WScore, LScore."""
    path = _find_file(
        raw_dir,
        "MRegularSeasonCompactResults.csv",
        "NCAAMRegularSeasonCompactResults.csv",
        "MRegularSeasonCompactResults",
    )
    if path is None:
        raise FileNotFoundError(f"No regular season compact results in {raw_dir}")
    df = pd.read_csv(path)
    # Normalize
    for wl in ("W", "L"):
        for suffix in ("TeamID", "Score"):
            col = f"{wl}{suffix}"
            if col not in df.columns and f"{wl}Team_Id" in df.columns and suffix == "TeamID":
                df = df.rename(columns={f"{wl}Team_Id": col})
            if col not in df.columns and f"{wl}_Team_Id" in df.columns and suffix == "TeamID":
                df = df.rename(columns={f"{wl}_Team_Id": col})
    return df


def load_tourney_compact(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load tournament game results (historical). Same column pattern as regular season."""
    path = _find_file(
        raw_dir,
        "MNCAATourneyCompactResults.csv",
        "NCAAMNCAATourneyCompactResults.csv",
        "MNCAATourneyCompactResults",
    )
    if path is None:
        raise FileNotFoundError(f"No tourney compact results in {raw_dir}")
    df = pd.read_csv(path)
    for wl in ("W", "L"):
        if f"{wl}TeamID" not in df.columns and f"{wl}Team_Id" in df.columns:
            df = df.rename(columns={f"{wl}Team_Id": f"{wl}TeamID"})
    return df


def load_massey_ordinals(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load Massey ordinals. Columns: Season, RankingDayNum, SystemName, TeamID, OrdinalRank."""
    path = _find_file(raw_dir, "MMasseyOrdinals.csv", "NCAAMMasseyOrdinals.csv", "MMasseyOrdinals")
    if path is None:
        raise FileNotFoundError(f"No Massey ordinals file in {raw_dir}")
    df = pd.read_csv(path)
    if "TeamID" not in df.columns and "Team_Id" in df.columns:
        df = df.rename(columns={"Team_Id": "TeamID"})
    if "OrdinalRank" not in df.columns and "Ordinal_Rank" in df.columns:
        df = df.rename(columns={"Ordinal_Rank": "OrdinalRank"})
    return df


def load_all(raw_dir: Path = DEFAULT_RAW_DIR) -> dict[str, pd.DataFrame]:
    """Load all Kaggle datasets that exist. Keys: teams, seasons, seeds, regular, tourney, massey."""
    out = {}
    try:
        out["teams"] = load_teams(raw_dir)
    except FileNotFoundError:
        pass
    try:
        out["seasons"] = load_seasons(raw_dir)
    except FileNotFoundError:
        pass
    try:
        out["seeds"] = load_tourney_seeds(raw_dir)
    except FileNotFoundError:
        pass
    try:
        out["regular"] = load_regular_season_compact(raw_dir)
    except FileNotFoundError:
        pass
    try:
        out["tourney"] = load_tourney_compact(raw_dir)
    except FileNotFoundError:
        pass
    try:
        out["massey"] = load_massey_ordinals(raw_dir)
    except FileNotFoundError:
        pass
    return out
