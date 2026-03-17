"""
Central runtime config: paths, season, sim count, model label.
Single source of truth for API, Streamlit diagnostics, and scripts.
"""

import os
from pathlib import Path

# Project root (march-madness); __file__ is src/mm/config.py
ROOT = Path(__file__).resolve().parents[2]

# Optional override for data directory (e.g. tests or non-standard deploy)
_data_dir = os.environ.get("MM_DATA_DIR")
if _data_dir:
    _data_root = Path(_data_dir)
else:
    _data_root = ROOT / "data"

RAW_DIR = _data_root / "raw"
PROCESSED_DIR = _data_root / "processed"
BRACKET_PATH = RAW_DIR / "bracket_2026.json"
HISTORY_DB = _data_root / "history.db"

DEFAULT_SEASON = 2026
DEFAULT_N_SIMS = 10000
# Fewer sims for dashboard API so /bracket responds in under a minute (full 10k via scripts/refresh.py)
DASHBOARD_N_SIMS = 2000
# Cached GET /bracket response; refreshed by scripts/refresh.py or on first load
DASHBOARD_BRACKET_CACHE = PROCESSED_DIR / "dashboard_bracket_cache.json"
# Precomputed pairwise win probs + bracket metadata for instant /whatif (exact propagation)
DASHBOARD_MATCHUP_MATRIX = PROCESSED_DIR / "dashboard_matchup_matrix.json"


def model_info(n_sims: int | None = None) -> str:
    """Human-readable label for the current model/sim setup."""
    k = n_sims or DEFAULT_N_SIMS
    label = "10k" if k == 10000 else str(k)
    return f"XGBoost, {label} sims"
