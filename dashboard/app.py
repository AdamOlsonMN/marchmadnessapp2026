"""
Streamlit diagnostics app: overview, model diagnostics, data quality.
Primary product is the React + FastAPI dashboard; use this for model/data inspection only.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st
import pandas as pd

from mm.config import RAW_DIR, PROCESSED_DIR, BRACKET_PATH


def load_bracket_source():
    """Bracket path from central config."""
    if BRACKET_PATH.exists():
        return BRACKET_PATH
    return None


def page_overview():
    st.header("Overview")
    bracket_path = load_bracket_source()
    st.metric("Bracket loaded", "Yes" if bracket_path else "No")
    st.caption("Bracket source: " + (str(bracket_path) if bracket_path else "None (fill data/raw/bracket_2026.json when released)"))
    for p in [RAW_DIR, PROCESSED_DIR]:
        exists = p.exists()
        st.text(f"  {p.name}: {'exists' if exists else 'missing'}")
    model_path = PROCESSED_DIR / "xgb_model.pkl"
    st.metric("Model trained", "Yes" if model_path.exists() else "No")
    st.caption("Primary app: run API (uvicorn dashboard.api.main:app) and frontend (npm run dev in dashboard/frontend).")


def page_model_diagnostics():
    st.header("Model diagnostics")
    try:
        baseline_path = PROCESSED_DIR / "baseline.pkl"
        xgb_path = PROCESSED_DIR / "xgb_model.pkl"
        feats_path = PROCESSED_DIR / "feature_columns.pkl"
        cv_path = PROCESSED_DIR / "rolling_cv_results.csv"
        st.subheader("Artifacts")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Baseline model", "Present" if baseline_path.exists() else "Missing")
        col2.metric("XGBoost model", "Present" if xgb_path.exists() else "Missing")
        col3.metric("Feature list", "Present" if feats_path.exists() else "Missing")
        col4.metric("CV results", "Present" if cv_path.exists() else "Missing")

        if feats_path.exists():
            import pickle
            with open(feats_path, "rb") as f:
                feats = pickle.load(f)
            st.subheader("Feature columns")
            st.code(", ".join(feats))

        if cv_path.exists():
            cv = pd.read_csv(cv_path)
            cv_display = cv.copy()
            if "accuracy" in cv_display.columns:
                cv_display["accuracy"] = cv_display["accuracy"].round(3)
            if "brier" in cv_display.columns:
                cv_display["brier"] = cv_display["brier"].round(4)
            if "log_loss" in cv_display.columns:
                cv_display["log_loss"] = cv_display["log_loss"].round(4)
            if "roc_auc" in cv_display.columns:
                cv_display["roc_auc"] = cv_display["roc_auc"].round(3)
            st.subheader("Rolling cross-validation (by validation season)")
            st.dataframe(cv_display, use_container_width=True)
            st.subheader("Mean metrics by model")
            summary = cv.groupby("Model").agg(
                accuracy=("accuracy", "mean"),
                brier=("brier", "mean"),
                log_loss=("log_loss", "mean"),
                roc_auc=("roc_auc", "mean"),
            ).round(4)
            st.dataframe(summary)
            if "brier" in cv.columns and "ValSeason" in cv.columns:
                st.subheader("Brier score over time")
                cv_plot = cv.pivot(index="ValSeason", columns="Model", values="brier")
                st.line_chart(cv_plot)

        if xgb_path.exists():
            import pickle
            with open(xgb_path, "rb") as f:
                model = pickle.load(f)
            est = model
            if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
                est = model.calibrated_classifiers_[0].estimator
            elif hasattr(model, "estimators_") and model.estimators_:
                est = model.estimators_[0]
            if hasattr(est, "get_booster"):
                st.subheader("XGBoost feature importance (gain)")
                booster = est.get_booster()
                imp = booster.get_score(importance_type="gain")
                if imp:
                    imp_series = pd.Series(imp).sort_values(ascending=False)
                    st.bar_chart(imp_series)
                else:
                    st.caption("No gain-based importance available.")
    except Exception as e:
        st.error(str(e))


def page_data_quality():
    st.header("Data quality")
    try:
        from mm.data.kaggle_loader import load_all
        from mm.data.validate_schema import run_validation
        data = load_all(RAW_DIR)
        st.write("Loaded sources:", list(data.keys()))
        errs = run_validation(RAW_DIR)
        if errs:
            st.error("Schema errors:")
            for e in errs:
                st.text(e)
        else:
            st.success("Schema validation passed.")
    except Exception as e:
        st.error(str(e))


def main():
    st.set_page_config(page_title="March Madness Diagnostics", layout="wide")
    st.title("March Madness Diagnostics")
    if st.button("Refresh"):
        st.rerun()
    nav = st.sidebar.radio(
        "Page",
        ["Overview", "Model diagnostics", "Data quality"],
    )
    if nav == "Overview":
        page_overview()
    elif nav == "Model diagnostics":
        page_model_diagnostics()
    else:
        page_data_quality()


if __name__ == "__main__":
    main()
