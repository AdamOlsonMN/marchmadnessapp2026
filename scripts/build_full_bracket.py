"""
Build a full 32-game bracket from Kaggle seeds and slots, then run the simulation.
Uses 2025 seeds (latest in dataset) and 1985 slot structure. Writes data/raw/bracket_2026.json.
Play-in seeds (W16a/W16b etc.): we use the first listed for that seed slot so we have 32 matchups.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "bracket_2026.json"
SEASON = 2025


def main():
    # Load seeds for SEASON
    seeds_path = RAW_DIR / "MNCAATourneySeeds.csv"
    slots_path = RAW_DIR / "MNCAATourneySlots.csv"
    teams_path = _find_teams(RAW_DIR)
    if not seeds_path.exists() or not slots_path.exists():
        print("Need MNCAATourneySeeds.csv and MNCAATourneySlots.csv in data/raw")
        sys.exit(1)

    seeds = pd.read_csv(seeds_path)
    seeds = seeds[seeds["Season"] == SEASON].copy()
    # Normalize play-in: W16a/W16b -> use first as W16 for bracket building
    seeds["SeedNorm"] = seeds["Seed"].astype(str).str.replace(r"[ab]$", "", regex=True)
    # One row per normalized seed (take first if duplicate, e.g. W16a then W16b)
    seed_to_team = {}
    for _, row in seeds.iterrows():
        sn = row["SeedNorm"]
        if sn not in seed_to_team:
            seed_to_team[sn] = int(row["TeamID"])

    slots = pd.read_csv(slots_path)
    slots = slots[slots["Season"] == 1985]  # same structure every year
    r1 = slots[slots["Slot"].str.startswith("R1")]
    if r1.empty:
        print("No R1 slots found")
        sys.exit(1)

    teams_df = pd.read_csv(teams_path) if teams_path else None
    if "TeamName" not in (teams_df.columns if teams_df is not None else []):
        teams_df = None
    team_names = {}
    if teams_df is not None:
        for _, row in teams_df.iterrows():
            team_names[int(row["TeamID"])] = str(row.get("TeamName", row["TeamID"]))

    games = []
    team_ids = set()
    for _, row in r1.iterrows():
        slot = str(row["Slot"])
        strong = str(row["StrongSeed"]).strip()
        weak = str(row["WeakSeed"]).strip()
        tid1 = seed_to_team.get(strong)
        tid2 = seed_to_team.get(weak)
        if tid1 is None or tid2 is None:
            print(f"Warning: missing team for {slot} ({strong} vs {weak})")
            continue
        team_ids.add(tid1)
        team_ids.add(tid2)
        s1 = _seed_to_num(strong)
        s2 = _seed_to_num(weak)
        reg = strong[0] if strong[0] in "WXYZ" else "W"
        games.append({
            "slot": slot,
            "team1_id": tid1,
            "team2_id": tid2,
            "seed1": s1,
            "seed2": s2,
            "region": reg,
        })

    teams_list = []
    for tid in sorted(team_ids):
        seed_str = next((s for s, t in seed_to_team.items() if t == tid), None)
        seed_num = _seed_to_num(seed_str) if seed_str else 0
        region = (seed_str[0] if seed_str and seed_str[0] in "WXYZ" else "W")
        teams_list.append({
            "id": tid,
            "name": team_names.get(tid, f"Team {tid}"),
            "seed": seed_num,
            "region": region,
        })

    out = {"teams": teams_list, "games": games}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote full bracket: {len(games)} games, {len(teams_list)} teams -> {OUT_PATH}")
    return out


def _seed_to_num(s):
    if not s or not isinstance(s, str):
        return 0
    s = s.replace("a", "").replace("b", "").strip()
    if len(s) >= 2 and s[-2:].isdigit():
        return int(s[-2:])
    return 0


def _find_teams(raw_dir):
    for name in ["MTeams.csv", "NCAAMTeams.csv"]:
        p = raw_dir / name
        if p.exists():
            return p
    return None


if __name__ == "__main__":
    main()
