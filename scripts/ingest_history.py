"""
Build or refresh data/history.db from Kaggle tournament results and seeds.
Run after each Kaggle download: python scripts/ingest_history.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "history.db"


def seed_to_int(seed_str: str) -> int:
    """Convert Kaggle seed e.g. W01, X16 to numeric 1-16."""
    s = str(seed_str).strip()
    if len(s) >= 2 and s[-2:].isdigit():
        return int(s[-2:])
    return 0


def main() -> None:
    results_path = RAW_DIR / "MNCAATourneyCompactResults.csv"
    seeds_path = RAW_DIR / "MNCAATourneySeeds.csv"
    if not results_path.exists():
        print(f"Missing {results_path}. Download Kaggle data first.")
        sys.exit(1)
    if not seeds_path.exists():
        print(f"Missing {seeds_path}. Download Kaggle data first.")
        sys.exit(1)

    results = pd.read_csv(results_path)
    seeds = pd.read_csv(seeds_path)
    seeds["seed_int"] = seeds["Seed"].apply(seed_to_int)

    # Season -> TeamID -> seed_int
    season_team_seed = {}
    for _, row in seeds.iterrows():
        key = (int(row["Season"]), int(row["TeamID"]))
        season_team_seed[key] = int(row["seed_int"])

    rows = []
    for _, r in results.iterrows():
        season = int(r["Season"])
        w_id = int(r["WTeamID"])
        l_id = int(r["LTeamID"])
        w_seed = season_team_seed.get((season, w_id), 0)
        l_seed = season_team_seed.get((season, l_id), 0)
        upset = 1 if w_seed > l_seed else 0
        round_day = int(r["DayNum"]) if "DayNum" in r else 0
        rows.append((season, round_day, w_id, l_id, w_seed, l_seed, upset))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tourney_games (
            season INTEGER,
            round_day INTEGER,
            winner_team_id INTEGER,
            loser_team_id INTEGER,
            winner_seed INTEGER,
            loser_seed INTEGER,
            upset INTEGER
        )
    """)
    conn.execute("DELETE FROM tourney_games")
    conn.executemany(
        "INSERT INTO tourney_games (season, round_day, winner_team_id, loser_team_id, winner_seed, loser_seed, upset) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM tourney_games").fetchone()[0]
    conn.close()
    print(f"Wrote {count} games to {DB_PATH}")


if __name__ == "__main__":
    main()
