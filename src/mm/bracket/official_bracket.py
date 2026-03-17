"""
Load and validate the released bracket JSON; resolve team names to internal/Kaggle IDs.
"""

import json
from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

# Aliases for team name resolution (name variant -> canonical name or id)
TEAM_ALIASES = {
    "uconn": "Connecticut",
    "unc": "North Carolina",
    "uk": "Kentucky",
    "usc": "South Carolina",
    "ucla": "UCLA",
    "lsu": "LSU",
    "byu": "BYU",
    "smu": "SMU",
    "tcu": "TCU",
    "unlv": "UNLV",
    "utsa": "UTSA",
    "ucf": "UCF",
    "usf": "South Florida",
    "ole miss": "Mississippi",
    "nc state": "NC State",
    "st. john's": "St. John's",
    "st john's": "St. John's",
    "st. mary's": "St. Mary's",
    "st mary's": "St. Mary's",
}


def resolve_team_name(name: str, teams_df: Optional[pd.DataFrame] = None) -> Optional[int]:
    """
    Resolve team name (or alias) to TeamID. If teams_df is None, return None (caller uses string id).
    """
    if teams_df is None or "TeamID" not in teams_df.columns:
        return None
    raw = str(name).strip()
    name_lower = raw.lower()
    # Try alias first
    canonical = TEAM_ALIASES.get(name_lower, raw)
    for _, row in teams_df.iterrows():
        team_name = str(row.get("TeamName", "")).strip()
        if name_lower == team_name.lower() or canonical.lower() == team_name.lower():
            return int(row["TeamID"])
        if name_lower in team_name.lower() or team_name.lower() in name_lower:
            return int(row["TeamID"])
    return None


def load_bracket(path: Path) -> dict:
    """Load bracket JSON. Expected: teams (list), games (list)."""
    with open(path) as f:
        return json.load(f)


def validate_bracket(bracket: dict) -> list[str]:
    """
    Validate bracket structure. Returns list of error messages.
    - 68 teams (or 64 + 4 play-in; we accept 64+ for first round).
    - games: each has team1_id/team2_id or team1/team2, seed1/seed2, region/slot.
    - No duplicate teams in a single game.
    """
    errs = []
    teams = bracket.get("teams", [])
    games = bracket.get("games", [])

    if len(teams) < 2:
        errs.append(f"Expected at least 2 teams, got {len(teams)}")
    elif len(teams) < 64:
        # Partial bracket (e.g. first-round only) is allowed
        pass
    if not games:
        errs.append("No games in bracket")

    seen_teams_in_games = set()
    for i, g in enumerate(games):
        t1 = g.get("team1_id", g.get("team1", g.get("Team1ID")))
        t2 = g.get("team2_id", g.get("team2", g.get("Team2ID")))
        if t1 is None or t2 is None:
            errs.append(f"Game {i}: missing team1 or team2")
        if t1 == t2:
            errs.append(f"Game {i}: same team for both sides")
        key = (tuple(sorted([str(t1), str(t2)])))
        if key in seen_teams_in_games:
            errs.append(f"Game {i}: duplicate matchup")
        seen_teams_in_games.add(key)

    return errs


def normalize_bracket(bracket: dict, teams_df: Optional[pd.DataFrame] = None) -> dict:
    """
    Normalize bracket: resolve team names to IDs where possible, ensure games have team1_id, team2_id, seed1, seed2, slot.
    """
    teams = bracket.get("teams", [])
    games = bracket.get("games", [])
    team_id_by_name = {}
    for t in teams:
        tid = t.get("id", t.get("TeamID", t.get("team_id")))
        name = t.get("name", t.get("TeamName", ""))
        if name:
            team_id_by_name[str(name).strip().lower()] = tid
        if tid is not None:
            team_id_by_name[str(tid)] = tid

    resolved = {}
    for name_or_id, tid in team_id_by_name.items():
        if isinstance(tid, str) and tid.isdigit():
            resolved[name_or_id] = int(tid)
        elif isinstance(tid, (int, float)):
            resolved[name_or_id] = int(tid)
        else:
            # Resolve name to ID via teams_df
            rid = resolve_team_name(str(tid), teams_df) if teams_df is not None else None
            resolved[name_or_id] = rid if rid is not None else tid

    out_games = []
    for g in games:
        t1 = g.get("team1_id", g.get("team1", g.get("Team1ID")))
        t2 = g.get("team2_id", g.get("team2", g.get("Team2ID")))
        s1 = g.get("seed1", g.get("Seed1", 8))
        s2 = g.get("seed2", g.get("Seed2", 8))
        slot = g.get("slot", g.get("Slot", ""))
        region = g.get("region", g.get("Region", ""))
        # Resolve to int IDs
        t1 = resolved.get(str(t1).lower(), resolved.get(str(t1), t1))
        t2 = resolved.get(str(t2).lower(), resolved.get(str(t2), t2))
        if isinstance(t1, str) and t1.isdigit():
            t1 = int(t1)
        if isinstance(t2, str) and t2.isdigit():
            t2 = int(t2)
        out_games.append({
            "slot": slot,
            "team1_id": t1,
            "team2_id": t2,
            "seed1": int(s1) if s1 is not None else 8,
            "seed2": int(s2) if s2 is not None else 8,
            "region": region,
        })
    return {"teams": teams, "games": out_games}


def load_and_validate(
    path: Path,
    teams_df: Optional[pd.DataFrame] = None,
    normalize: bool = True,
) -> tuple[dict, list[str]]:
    """
    Load bracket, validate, optionally normalize. Returns (bracket_dict, list of errors).
    """
    bracket = load_bracket(path)
    errs = validate_bracket(bracket)
    if normalize and not errs:
        bracket = normalize_bracket(bracket, teams_df=teams_df)
    return bracket, errs
