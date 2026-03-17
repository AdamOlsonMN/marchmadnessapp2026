"""
Hyperparameter tuning via rolling season CV. Finds best XGBoost and optional logistic params
by mean Brier score, then retrains the best model on all data and saves.
"""

from pathlib import Path
import pickle
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
import xgboost as xgb

from mm.features.build_matchups import (
    build_tourney_matchups,
    feature_columns,
    DEFAULT_RAW_DIR,
    DEFAULT_PROCESSED_DIR,
)
from mm.data.kaggle_loader import load_all
from mm.models.validate import get_seasons_with_tourney, rolling_cv_splits

warnings.filterwarnings("ignore", message=".*use_label_encoder.*")

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"

# Search space: XGBoost
XGB_GRID = [
    {"n_estimators": 150, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"n_estimators": 300, "max_depth": 4, "learning_rate": 0.03, "subsample": 0.85, "colsample_bytree": 0.85},
    {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.75, "colsample_bytree": 0.75},
    {"n_estimators": 250, "max_depth": 4, "learning_rate": 0.04, "subsample": 0.8, "colsample_bytree": 0.8},
    {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.06, "subsample": 0.9, "colsample_bytree": 0.9},
]
# Logistic C
LOGISTIC_C = [0.01, 0.05, 0.1, 0.5, 1.0]


def score_rolling_cv(
    df: pd.DataFrame,
    seasons: list[int],
    model_type: str,
    params: dict[str, Any],
    feats: list[str],
) -> float:
    """Return mean Brier score over rolling CV folds (lower is better)."""
    briers = []
    for X_train, y_train, X_val, y_val, _ in rolling_cv_splits(df, seasons):
        if model_type == "xgb":
            est = xgb.XGBClassifier(
                random_state=42,
                eval_metric="logloss",
                **params,
            )
        else:
            est = LogisticRegression(max_iter=1000, random_state=42, C=params["C"])
        cal = CalibratedClassifierCV(est, method="isotonic", cv=5)
        cal.fit(X_train, y_train)
        p = cal.predict_proba(X_val)[:, 1]
        p = np.clip(p, 1e-6, 1 - 1e-6)
        briers.append(brier_score_loss(y_val, p))
    return float(np.mean(briers)) if briers else 1.0


def run_tuning(
    raw_dir: Path = DEFAULT_RAW_DIR,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    n_xgb_trials: int = 6,
    tune_baseline: bool = True,
) -> dict[str, Any]:
    """
    Run tuning over XGBoost grid and optional logistic C; save best models.
    Returns dict with best_params_xgb, best_params_baseline, best_brier_xgb, best_brier_baseline.
    """
    data = load_all(raw_dir)
    if "seeds" not in data or "tourney" not in data or "regular" not in data:
        raise FileNotFoundError("Need seeds, tourney, regular in raw_dir")
    df = build_tourney_matchups(
        data["seeds"], data["tourney"], data["regular"], massey=data.get("massey")
    )
    seasons = get_seasons_with_tourney(data)
    feats = feature_columns()

    # Tune XGBoost
    best_brier_xgb = 1.0
    best_params_xgb = XGB_GRID[0]
    for i, params in enumerate(XGB_GRID[:n_xgb_trials]):
        brier = score_rolling_cv(df, seasons, "xgb", params, feats)
        if brier < best_brier_xgb:
            best_brier_xgb = brier
            best_params_xgb = params
    print(f"Best XGBoost: Brier={best_brier_xgb:.4f} params={best_params_xgb}")

    # Tune logistic C
    best_brier_base = 1.0
    best_c = 0.1
    if tune_baseline:
        for c in LOGISTIC_C:
            brier = score_rolling_cv(df, seasons, "logistic", {"C": c}, feats)
            if brier < best_brier_base:
                best_brier_base = brier
                best_c = c
        print(f"Best baseline: Brier={best_brier_base:.4f} C={best_c}")

    # Retrain best models on full data and save
    X = df[feats].fillna(0).values
    y = df["Label"].values
    processed_dir.mkdir(parents=True, exist_ok=True)

    base = LogisticRegression(max_iter=1000, C=best_c, random_state=42)
    base_cal = CalibratedClassifierCV(base, method="isotonic", cv=5)
    base_cal.fit(X, y)
    with open(processed_dir / "baseline.pkl", "wb") as f:
        pickle.dump(base_cal, f)

    xgb_est = xgb.XGBClassifier(
        random_state=42,
        eval_metric="logloss",
        **best_params_xgb,
    )
    xgb_cal = CalibratedClassifierCV(xgb_est, method="isotonic", cv=5)
    xgb_cal.fit(X, y)
    with open(processed_dir / "xgb_model.pkl", "wb") as f:
        pickle.dump(xgb_cal, f)

    with open(processed_dir / "feature_columns.pkl", "wb") as f:
        pickle.dump(feats, f)

    return {
        "best_params_xgb": best_params_xgb,
        "best_params_baseline": {"C": best_c},
        "best_brier_xgb": best_brier_xgb,
        "best_brier_baseline": best_brier_base,
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    p.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    p.add_argument("--n-xgb-trials", type=int, default=6, help="Number of XGBoost configs to try")
    p.add_argument("--no-baseline", action="store_true", help="Skip tuning logistic C")
    args = p.parse_args()
    result = run_tuning(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        n_xgb_trials=args.n_xgb_trials,
        tune_baseline=not args.no_baseline,
    )
    print("Tuning complete. Best models saved to", args.processed_dir, flush=True)
    for k, v in result.items():
        print(f"  {k}: {v}", flush=True)
    return result


if __name__ == "__main__":
    main()
