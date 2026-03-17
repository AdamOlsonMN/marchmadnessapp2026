"""
Overtime Markets odds ingestion: API (when key approved) or fallback from JSON/CSV.
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd

# API base from docs
OVERTIME_API_BASE = "https://api.overtime.io"
DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


def load_odds_from_json(path: Path) -> pd.DataFrame:
    """
    Load odds from a JSON snapshot. Expected structure:
    - list of markets, each with homeTeam, awayTeam, odds (list of {american, decimal, normalizedImplied}),
      or
    - dict with "markets" key containing such list.
    """
    import json
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        markets = data
    else:
        markets = data.get("markets", data.get("markets", []))
    rows = []
    for m in markets:
        home = m.get("homeTeam", m.get("home_team", ""))
        away = m.get("awayTeam", m.get("away_team", ""))
        odds_list = m.get("odds", [])
        if isinstance(odds_list[0], dict):
            # normalizedImplied = P(that outcome)
            for i, o in enumerate(odds_list):
                prob = o.get("normalizedImplied", o.get("normalized_implied", 1.0 / len(odds_list)))
                rows.append({"home_team": home, "away_team": away, "outcome_index": i, "implied_prob": prob})
        else:
            rows.append({"home_team": home, "away_team": away, "implied_prob": 1.0 / max(len(odds_list), 1)})
    return pd.DataFrame(rows)


def load_odds_from_csv(path: Path) -> pd.DataFrame:
    """
    Load odds from CSV. Expected columns: home_team, away_team, implied_prob (or team1, team2, prob).
    """
    df = pd.read_csv(path)
    if "implied_prob" not in df.columns and "prob" in df.columns:
        df = df.rename(columns={"prob": "implied_prob"})
    if "home_team" not in df.columns and "team1" in df.columns:
        df = df.rename(columns={"team1": "home_team", "team2": "away_team"})
    return df


def fetch_overtime_markets(
    network_id: int = 10,
    league_id: Optional[int] = None,
    api_key: Optional[str] = None,
) -> Optional[list[dict]]:
    """
    Fetch markets from Overtime API. Requires approved API key in env OVERTIME_API_KEY or passed in.
    Returns list of market dicts or None if unavailable.
    """
    api_key = api_key or os.environ.get("OVERTIME_API_KEY")
    if not api_key:
        return None
    try:
        import requests
        url = f"{OVERTIME_API_BASE}/overtime-v2/networks/{network_id}/markets"
        params = {}
        if league_id is not None:
            params["leagueId"] = league_id
        r = requests.get(url, headers={"x-api-key": api_key}, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("markets") == "no change":
            return None
        return data.get("markets") if isinstance(data.get("markets"), list) else [data]
    except Exception:
        return None


def get_odds(
    raw_dir: Path = DEFAULT_RAW_DIR,
    json_path: Optional[Path] = None,
    csv_path: Optional[Path] = None,
    use_api: bool = True,
) -> pd.DataFrame:
    """
    Load odds from fallback file(s) or API. Priority: json_path > csv_path > overtime_odds.json > overtime_odds.csv > API.
    """
    if json_path and json_path.exists():
        return load_odds_from_json(json_path)
    if csv_path and csv_path.exists():
        return load_odds_from_csv(csv_path)
    for name in ("overtime_odds.json", "odds.json", "markets.json"):
        p = raw_dir / name
        if p.exists():
            return load_odds_from_json(p)
    for name in ("overtime_odds.csv", "odds.csv"):
        p = raw_dir / name
        if p.exists():
            return load_odds_from_csv(p)
    if use_api:
        markets = fetch_overtime_markets()
        if markets:
            # Convert to DataFrame
            rows = []
            for m in markets:
                home = m.get("homeTeam", "")
                away = m.get("awayTeam", "")
                for i, o in enumerate(m.get("odds", [])):
                    prob = o.get("normalizedImplied", 0.0)
                    rows.append({"home_team": home, "away_team": away, "outcome_index": i, "implied_prob": prob})
            return pd.DataFrame(rows)
    return pd.DataFrame(columns=["home_team", "away_team", "implied_prob"])
