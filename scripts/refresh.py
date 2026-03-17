#!/usr/bin/env python3
"""
One-command refresh: validate data, rebuild features, train model, run simulation, export artifacts.
Uses central config (mm.config) for paths and defaults.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mm.config import RAW_DIR, PROCESSED_DIR, BRACKET_PATH, DEFAULT_N_SIMS, DASHBOARD_MATCHUP_MATRIX


def main():
    import argparse
    p = argparse.ArgumentParser(description="Refresh data, model, and bracket outputs")
    p.add_argument("--skip-train", action="store_true", help="Skip training (use existing models)")
    p.add_argument("--with-validation", action="store_true", help="Run rolling CV and write model_meta.json")
    p.add_argument("--skip-export", action="store_true", help="Skip writing CSV/artifacts to processed dir")
    p.add_argument("--n-sims", type=int, default=None, help=f"Monte Carlo sim count (default: {DEFAULT_N_SIMS}). Use 2000 for a quicker run.")
    args = p.parse_args()
    n_sims = args.n_sims if args.n_sims is not None else DEFAULT_N_SIMS

    print("1. Validating schema…")
    from mm.data.validate_schema import run_validation
    errs = run_validation(RAW_DIR)
    if errs:
        print("   Schema errors:", errs)
        return 1
    print("   OK")

    print("2. Rebuilding matchups…")
    from mm.features.build_matchups import build_and_save
    build_and_save(raw_dir=RAW_DIR, processed_dir=PROCESSED_DIR)
    print("   OK")

    if not args.skip_train:
        print("3. Training models…")
        from mm.models.train import run_training
        run_training(
            processed_dir=PROCESSED_DIR,
            raw_dir=RAW_DIR,
            with_validation=args.with_validation,
        )
        print("   OK")
    else:
        print("3. Skipping training (--skip-train)")

    if not BRACKET_PATH.exists():
        print("4. No bracket file; skip simulation. Add data/raw/bracket_2026.json and re-run.")
        return 0

    print(f"4. Running bracket simulation ({n_sims} sims)…")
    from mm.config import DEFAULT_SEASON
    from mm.bracket.simulate import (
        load_bracket_and_simulate,
        load_slot_tree,
        load_model,
        load_feature_columns,
        build_pairwise_win_matrix,
        _team_to_seed_from_game_probs,
    )
    from mm.data.kaggle_loader import load_all

    game_probs, champ_probs, advancement, next_probs = load_bracket_and_simulate(
        BRACKET_PATH, raw_dir=RAW_DIR, model_dir=PROCESSED_DIR, n_sims=n_sims
    )
    print(f"   Games: {len(game_probs)}, champion odds for {len(champ_probs)} teams")

    # Write dashboard cache so GET /bracket serves instantly without re-running sim
    sys.path.insert(0, str(ROOT))
    from dashboard.api.main import _build_bracket_response, _save_bracket_cache
    with open(BRACKET_PATH) as f:
        import json as _json
        bracket = _json.load(f)
    slot_tree, slot_order = load_slot_tree(RAW_DIR)
    response = _build_bracket_response(bracket, game_probs, champ_probs, advancement, next_probs, slot_tree, slot_order)
    _save_bracket_cache(response, BRACKET_PATH)
    print("   Dashboard cache updated (GET /bracket will serve from cache)")

    # Write matchup matrix for instant /whatif (exact propagation)
    data = load_all(RAW_DIR)
    regular = data["regular"]
    season = DEFAULT_SEASON
    if season not in regular["Season"].values:
        season = int(regular["Season"].max())
    massey = data.get("massey")
    if massey is not None:
        massey = massey[massey["Season"] == season]
    model = load_model(PROCESSED_DIR, "xgb")
    feats = load_feature_columns(PROCESSED_DIR)
    print("   Building pairwise win matrix…", flush=True)
    pairwise = build_pairwise_win_matrix(game_probs, model, feats, season, regular, massey)
    team_to_seed = _team_to_seed_from_game_probs(game_probs)
    r1_slot_probs = {}
    for gp in game_probs:
        slot = str(gp.get("slot", ""))
        if not slot.startswith("R1"):
            continue
        t_lo = int(gp["team_lower"])
        t_hi = int(gp["team_higher"])
        p_lo = float(gp["prob_lower_wins"])
        r1_slot_probs[slot] = {str(t_lo): p_lo, str(t_hi): 1.0 - p_lo}
    artifact = {
        "pairwise_win_prob": pairwise,
        "team_to_seed": {str(k): v for k, v in team_to_seed.items()},
        "slot_tree": {k: list(v) for k, v in slot_tree.items()},
        "slot_order": slot_order,
        "r1_slot_probs": r1_slot_probs,
    }
    DASHBOARD_MATCHUP_MATRIX.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_MATCHUP_MATRIX, "w") as f:
        _json.dump(artifact, f, indent=0)
    print("   Matchup matrix written (POST /whatif will use exact propagation)")

    if args.skip_export:
        print("5. Skip export (--skip-export)")
        return 0

    print("5. Exporting artifacts…")
    import pandas as pd
    out_dir = PROCESSED_DIR / "bracket_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(game_probs).to_csv(out_dir / "game_probs.csv", index=False)
    pd.Series(champ_probs).to_csv(out_dir / "champ_probs.csv")
    if advancement:
        for key in ("champ", "final4", "elite8", "sweet16", "r2"):
            if key in advancement and advancement[key]:
                pd.Series(advancement[key]).to_csv(out_dir / f"advancement_{key}.csv")
    from mm.value.recommendations import run_value_pipeline
    recs = run_value_pipeline(BRACKET_PATH, raw_dir=RAW_DIR, threshold=0.05)
    if not recs.empty:
        recs.to_csv(out_dir / "value_recommendations.csv", index=False)
        print(f"   Value recs: {len(recs)}")
    print("   Wrote", out_dir)
    print("Done. Start dashboard: PYTHONPATH=src uvicorn dashboard.api.main:app --port 8000")
    print("         Frontend: cd dashboard/frontend && npm run dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
