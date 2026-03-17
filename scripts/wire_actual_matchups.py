#!/usr/bin/env python3
"""
After the bracket is released: ensure bracket_2026.json is filled, then run loader,
point simulator/dashboard at official bracket, and regenerate predictions + value recs.

Usage:
  1. Manually fill data/raw/bracket_2026.json with the official 68-team field and first-round pairings.
  2. Run: python scripts/wire_actual_matchups.py
  3. Run API + frontend for the main dashboard; streamlit run dashboard/app.py for diagnostics only.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mm.config import RAW_DIR, PROCESSED_DIR, BRACKET_PATH, DEFAULT_N_SIMS


def main():
    if not BRACKET_PATH.exists():
        print("bracket_2026.json not found. Create and fill it with the official bracket.")
        return 1
    import json
    with open(BRACKET_PATH) as f:
        data = json.load(f)
    games = data.get("games", [])
    teams = data.get("teams", [])
    if len(games) == 0:
        print("bracket_2026.json has no games. Add first-round matchups.")
        return 1
    print(f"Bracket has {len(teams)} teams and {len(games)} games.")

    from mm.bracket.official_bracket import load_and_validate
    from mm.data.kaggle_loader import load_all

    data_all = load_all(RAW_DIR)
    teams_df = data_all.get("teams")
    bracket, errs = load_and_validate(BRACKET_PATH, teams_df=teams_df, normalize=True)
    if errs:
        print("Validation errors:")
        for e in errs:
            print(" ", e)
        return 1
    print("Validation passed.")

    from mm.bracket.simulate import load_bracket_and_simulate
    game_probs, champ_probs, advancement, _ = load_bracket_and_simulate(
        BRACKET_PATH, raw_dir=RAW_DIR, model_dir=PROCESSED_DIR, n_sims=DEFAULT_N_SIMS
    )
    print("Simulation complete. Game-level probs and champion odds computed.")
    out_dir = PROCESSED_DIR / "bracket_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    pd.DataFrame(game_probs).to_csv(out_dir / "game_probs.csv", index=False)
    pd.Series(champ_probs).to_csv(out_dir / "champ_probs.csv")
    if advancement:
        for key in ("champ", "final4", "elite8", "sweet16", "r2"):
            if key in advancement and advancement[key]:
                pd.Series(advancement[key]).to_csv(out_dir / f"advancement_{key}.csv")
    print("Wrote", out_dir / "game_probs.csv", out_dir / "champ_probs.csv")

    from mm.value.recommendations import run_value_pipeline
    recs = run_value_pipeline(BRACKET_PATH, raw_dir=RAW_DIR, threshold=0.05)
    if not recs.empty:
        recs.to_csv(out_dir / "value_recommendations.csv", index=False)
        print("Wrote", out_dir / "value_recommendations.csv")
    else:
        print("No odds loaded; value recommendations skipped. Add data/raw/overtime_odds.json or CSV.")
    print("Done. Run API + frontend for dashboard; streamlit run dashboard/app.py for diagnostics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
