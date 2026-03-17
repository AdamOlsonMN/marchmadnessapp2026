"""
Rolling season cross-validation and calibration evaluation.
Train on seasons < Y, validate on season Y. Report Brier, log loss, ROC AUC, accuracy.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    roc_auc_score,
    accuracy_score,
)
import xgboost as xgb

from mm.features.build_matchups import (
    build_tourney_matchups,
    feature_columns,
    DEFAULT_RAW_DIR,
    DEFAULT_PROCESSED_DIR,
)
from mm.data.kaggle_loader import load_all


def get_seasons_with_tourney(data: dict) -> list[int]:
    """Return sorted list of seasons that have tournament results."""
    if "tourney" not in data:
        return []
    return sorted(data["tourney"]["Season"].unique().tolist())


def rolling_cv_splits(
    df: pd.DataFrame,
    seasons: list[int],
    min_train_seasons: int = 3,
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Yield (X_train, y_train, X_val, y_val) for each validation season.
    Train on all seasons before val season.
    """
    feats = feature_columns()
    for i, val_season in enumerate(seasons):
        if i < min_train_seasons:
            continue
        train_df = df[df["Season"] < val_season]
        val_df = df[df["Season"] == val_season]
        if len(train_df) < 10 or len(val_df) < 1:
            continue
        X_train = train_df[feats].fillna(0).values
        y_train = train_df["Label"].values
        X_val = val_df[feats].fillna(0).values
        y_val = val_df["Label"].values
        yield X_train, y_train, X_val, y_val, val_season


def evaluate_probs(y_true: np.ndarray, proba: np.ndarray) -> dict[str, float]:
    """Compute Brier, log loss, ROC AUC, accuracy. proba = P(lower TeamID wins)."""
    proba = np.asarray(proba).ravel()
    y_true = np.asarray(y_true).ravel()
    proba = np.clip(proba, 1e-6, 1 - 1e-6)
    return {
        "brier": brier_score_loss(y_true, proba),
        "log_loss": log_loss(y_true, proba),
        "roc_auc": roc_auc_score(y_true, proba) if len(np.unique(y_true)) > 1 else 0.0,
        "accuracy": accuracy_score(y_true, (proba >= 0.5).astype(int)),
    }


def run_rolling_cv(
    raw_dir: Path = DEFAULT_RAW_DIR,
    processed_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Run rolling season CV for baseline and XGBoost (with calibration).
    Returns DataFrame with columns: ValSeason, Model, Brier, LogLoss, ROC_AUC, Accuracy.
    """
    data = load_all(raw_dir)
    if "seeds" not in data or "tourney" not in data or "regular" not in data:
        raise FileNotFoundError("Need seeds, tourney, regular in raw_dir")
    seeds = data["seeds"]
    tourney = data["tourney"]
    regular = data["regular"]
    massey = data.get("massey")

    df = build_tourney_matchups(seeds, tourney, regular, massey=massey)
    seasons = get_seasons_with_tourney(data)
    feats = feature_columns()

    results = []
    for X_train, y_train, X_val, y_val, val_season in rolling_cv_splits(df, seasons):
        # Baseline + calibration
        base = LogisticRegression(max_iter=1000, C=0.1, random_state=42)
        base_cal = CalibratedClassifierCV(base, method="isotonic", cv=5)
        base_cal.fit(X_train, y_train)
        p_base = base_cal.predict_proba(X_val)[:, 1]
        for k, v in evaluate_probs(y_val, p_base).items():
            results.append({"ValSeason": val_season, "Model": "baseline_cal", "Metric": k, "Value": v})

        # XGBoost + calibration
        xgb_est = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            eval_metric="logloss", use_label_encoder=False,
        )
        xgb_cal = CalibratedClassifierCV(xgb_est, method="isotonic", cv=5)
        xgb_cal.fit(X_train, y_train)
        p_xgb = xgb_cal.predict_proba(X_val)[:, 1]
        for k, v in evaluate_probs(y_val, p_xgb).items():
            results.append({"ValSeason": val_season, "Model": "xgb_cal", "Metric": k, "Value": v})

    res_df = pd.DataFrame(results)
    if res_df.empty:
        return res_df
    summary = res_df.pivot_table(
        index=["ValSeason", "Model"], columns="Metric", values="Value"
    ).reset_index()
    out_path = (processed_dir or DEFAULT_PROCESSED_DIR) / "rolling_cv_results.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False)
    return summary


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    p.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    args = p.parse_args()
    summary = run_rolling_cv(raw_dir=args.raw_dir, processed_dir=args.processed_dir)
    print(summary.to_string())
    print("\nResults saved to", args.processed_dir / "rolling_cv_results.csv")
