# March Madness Predictor

NCAA men's tournament bracket prediction using public historical data, calibrated XGBoost models, and a React + FastAPI dashboard with pick explanations and value recommendations.

## Quick start

```bash
cd march-madness
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

**Data:** Download [Kaggle March Machine Learning Mania](https://www.kaggle.com/competitions/march-machine-learning-mania-2026) into `data/raw/` (see Data sources below).

**One-command refresh** (validate, build features, train, simulate, export):

```bash
PYTHONPATH=src python scripts/refresh.py
```

Optional: `--skip-train` to use existing models, `--n-sims 2000` for a quicker run (default 10k), `--with-validation` to run rolling CV and write `model_meta.json`.

**Launch dashboard:**

```bash
# Terminal 1: API
PYTHONPATH=src uvicorn dashboard.api.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
cd dashboard/frontend && npm install && npm run dev
```

Open the frontend URL (e.g. http://localhost:5173). Use **Bracket** for the interactive bracket, **2026 picks** for model picks and explanations, **Best values** for model-vs-market edges. Predictions are **cached** (train/predict): run `scripts/refresh.py` when the bracket or model changes; the dashboard then serves from cache until the next refresh.

**Diagnostics only** (model artifacts, CV results, data quality):

```bash
streamlit run dashboard/app.py
```

## Data sources

- **Kaggle**: Place competition CSVs in `data/raw/`. Use `pip install -e ".[kaggle]"` and `python scripts/download_kaggle_data.py` if you use the Kaggle API.
- **Bracket**: Fill `data/raw/bracket_2026.json` with teams and first-round games (see schema below). Use `scripts/build_full_bracket.py` for a synthetic 32-game bracket from seeds, or paste the official bracket when released.
- **Odds**: Optional. Add `data/raw/overtime_odds.json` or a CSV with `home_team`, `away_team`, `implied_prob` for value recommendations.

## Bracket schema

- **`teams`**: list of `{ "id": <int>, "name": "Team Name", "seed": 1-16, "region": "W"|"X"|"Y"|"Z" }`.
- **`games`**: list of `{ "slot": "R1W1", "team1_id": <id>, "team2_id": <id>, "seed1": 1, "seed2": 16, "region": "W" }`.

Validation and name resolution: `src/mm/bracket/official_bracket.py`. With all 32 R1 slots filled, the simulator runs full Monte Carlo and returns champion and advancement odds.

## Commands

| Command | Description |
|--------|-------------|
| `PYTHONPATH=src python scripts/refresh.py` | Full refresh (data, train, sim, export) |
| `python -m mm.models.train` | Train baseline + XGBoost (optionally `--with-validation`) |
| `python -m mm.models.validate` | Rolling CV, writes `rolling_cv_results.csv` |
| `python -m mm.bracket.simulate` | Run simulation only |
| `python scripts/wire_actual_matchups.py` | Validate bracket, run sim, export (after filling bracket) |
| `PYTHONPATH=src uvicorn dashboard.api.main:app --port 8000` | Start API |
| `streamlit run dashboard/app.py` | Diagnostics UI |

## Deploy

To run on a cloud VPS (Docker or bare metal), one-time bootstrap, CI/CD, and refresh: see **[docs/deploy.md](docs/deploy.md)**. You need a Linux server with SSH; GitHub Actions can deploy on push to `main` and run refresh on demand or on a schedule.

## Project layout

- `data/raw/` — Kaggle CSVs, `bracket_2026.json`, optional odds
- `data/processed/` — matchups, models, `model_meta.json`, `bracket_output/`
- `src/mm/` — config, data, features, models, bracket simulation, value engine
- `dashboard/api/` — FastAPI (bracket, whatif, value, history)
- `dashboard/frontend/` — React dashboard (primary UI)
- `dashboard/app.py` — Streamlit diagnostics
- `tests/` — data, bracket, simulation, recommendations, API
