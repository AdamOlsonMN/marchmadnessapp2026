"""
Train baseline (logistic) and XGBoost models for matchup outcome prediction.
Saves fitted models and calibration to data/processed/.
Optionally runs rolling CV and writes model_meta.json so the saved model is tied to validation.
"""

import json
from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb

from mm.features.build_matchups import (
    DEFAULT_PROCESSED_DIR,
    DEFAULT_RAW_DIR,
    feature_columns,
    build_and_save,
)


DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"


def load_matchups(processed_dir: Path = DEFAULT_PROCESSED_DIR, raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load prebuilt matchups from parquet. Build if missing."""
    p = processed_dir / "matchups.parquet"
    if not p.exists():
        build_and_save(raw_dir=raw_dir, processed_dir=processed_dir)
    return pd.read_parquet(p)


def train_baseline(X: np.ndarray, y: np.ndarray) -> Any:
    """Train logistic regression with L2."""
    m = LogisticRegression(max_iter=1000, C=0.1, random_state=42)
    m.fit(X, y)
    return m


def train_xgboost_model(X: np.ndarray, y: np.ndarray) -> Any:
    """Train XGBoost classifier."""
    m = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="logloss",
    )
    m.fit(X, y)
    return m


def train_calibrated(
    base_estimator: Any,
    X: np.ndarray,
    y: np.ndarray,
    method: str = "isotonic",
    cv: int = 5,
) -> Any:
    """Wrap estimator with isotonic or sigmoid calibration."""
    return CalibratedClassifierCV(base_estimator, method=method, cv=cv).fit(X, y)


def _write_model_meta(model_dir: Path, processed_dir: Path, raw_dir: Path) -> None:
    """Run rolling CV and write model_meta.json with last validation season and xgb_cal metrics."""
    from mm.models.validate import run_rolling_cv
    summary = run_rolling_cv(raw_dir=raw_dir, processed_dir=processed_dir)
    if summary.empty:
        meta = {"validation": None, "message": "No validation runs (insufficient data)"}
    else:
        xgb_rows = summary[summary["Model"] == "xgb_cal"]
        if xgb_rows.empty:
            meta = {"validation": None, "message": "No xgb_cal rows in CV summary"}
        else:
            last = xgb_rows.iloc[-1]
            meta = {
                "validation": {
                    "val_season": int(last["ValSeason"]),
                    "brier": float(last["brier"]),
                    "log_loss": float(last["log_loss"]),
                    "roc_auc": float(last["roc_auc"]),
                    "accuracy": float(last["accuracy"]),
                },
                "cv_results_path": str(processed_dir / "rolling_cv_results.csv"),
            }
    with open(model_dir / "model_meta.json", "w") as f:
        json.dump(meta, f, indent=2)


def run_training(
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    model_dir: Path = DEFAULT_MODEL_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    calibrate: bool = True,
    with_validation: bool = False,
) -> dict[str, Any]:
    """
    Load matchups, train baseline and XGBoost (optionally calibrated), save artifacts.
    If with_validation=True, runs rolling CV and writes model_meta.json tying model to validation.
    Returns dict with keys: baseline, xgb, feature_cols, calibration (bool).
    """
    df = load_matchups(processed_dir, raw_dir=raw_dir)
    feats = feature_columns()
    for c in feats:
        if c not in df.columns:
            raise ValueError(f"Missing feature column: {c}")
    X = df[feats].fillna(0).values
    y = df["Label"].values

    model_dir.mkdir(parents=True, exist_ok=True)

    # Baseline
    baseline = train_baseline(X, y)
    if calibrate:
        baseline = train_calibrated(
            LogisticRegression(max_iter=1000, C=0.1, random_state=42),
            X, y, method="isotonic",
        )
    with open(model_dir / "baseline.pkl", "wb") as f:
        pickle.dump(baseline, f)

    # XGBoost
    xgb_est = train_xgboost_model(X, y)
    if calibrate:
        xgb_est = train_calibrated(
            xgb.XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                eval_metric="logloss",
            ),
            X, y, method="isotonic",
        )
    with open(model_dir / "xgb_model.pkl", "wb") as f:
        pickle.dump(xgb_est, f)

    # Save feature list for inference
    with open(model_dir / "feature_columns.pkl", "wb") as f:
        pickle.dump(feats, f)

    if with_validation:
        _write_model_meta(model_dir, processed_dir, raw_dir)

    return {
        "baseline": baseline,
        "xgb": xgb_est,
        "feature_cols": feats,
        "calibration": calibrate,
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    p.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    p.add_argument("--no-calibrate", action="store_true", help="Skip probability calibration")
    p.add_argument("--with-validation", action="store_true", help="Run rolling CV and write model_meta.json")
    args = p.parse_args()
    run_training(
        processed_dir=args.processed_dir,
        model_dir=args.model_dir,
        raw_dir=args.raw_dir,
        calibrate=not args.no_calibrate,
        with_validation=args.with_validation,
    )
    print("Training complete. Models saved to", args.model_dir)
