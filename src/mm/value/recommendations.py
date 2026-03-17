"""
Value recommendations: compare model win probabilities to market-implied probabilities
and flag games where the model disagrees beyond a threshold.
Uses official_bracket.resolve_team_name for canonical team resolution.
"""

from pathlib import Path
from typing import Optional

import pandas as pd

from mm.odds.overtime import get_odds, DEFAULT_RAW_DIR
from mm.bracket.simulate import load_bracket_and_simulate
from mm.bracket.official_bracket import resolve_team_name
from mm.data.kaggle_loader import load_all


def _team_id_to_name(team_id: int, teams_df: Optional[pd.DataFrame]) -> str:
    """Resolve TeamID to display name."""
    if teams_df is None or len(teams_df) == 0:
        return str(team_id)
    row = teams_df[teams_df["TeamID"] == team_id]
    if len(row):
        return str(row["TeamName"].iloc[0])
    return str(team_id)


def _match_odds_row_to_game(
    g: dict,
    odds_df: pd.DataFrame,
    teams_df: Optional[pd.DataFrame],
) -> Optional[tuple[float, int, int]]:
    """
    Match game (team_lower, team_higher) to one odds row using canonical name resolution.
    Returns (implied_prob_for_lower, home_id, away_id) or None.
    implied_prob is always P(lower TeamID wins) for consistency with model_prob.
    """
    t_lo = g["team_lower"]
    t_hi = g["team_higher"]
    name_lo = _team_id_to_name(t_lo, teams_df)
    name_hi = _team_id_to_name(t_hi, teams_df)
    for _, row in odds_df.iterrows():
        h_raw = str(row.get("home_team", "")).strip()
        a_raw = str(row.get("away_team", "")).strip()
        h_id = resolve_team_name(h_raw, teams_df) if teams_df is not None else None
        a_id = resolve_team_name(a_raw, teams_df) if teams_df is not None else None
        if h_id is None or a_id is None:
            # Fallback: match by name string (case-insensitive)
            if not h_raw or not a_raw:
                continue
            hl, al = h_raw.lower(), a_raw.lower()
            nlo, nhi = name_lo.lower(), name_hi.lower()
            if (hl == nlo and al == nhi):
                return (float(row.get("implied_prob", 0.5)), t_lo, t_hi)
            if (hl == nhi and al == nlo):
                return (1.0 - float(row.get("implied_prob", 0.5)), t_lo, t_hi)
            continue
        if (h_id, a_id) == (t_lo, t_hi):
            implied = float(row.get("implied_prob", 0.5))
            # Odds row is (home, away) = (lower, higher); implied is P(home)=P(lower)
            return (implied, h_id, a_id)
        if (h_id, a_id) == (t_hi, t_lo):
            implied = 1.0 - float(row.get("implied_prob", 0.5))
            return (implied, h_id, a_id)
    return None


def build_recommendations(
    game_probs: list[dict],
    odds_df: pd.DataFrame,
    teams_df: Optional[pd.DataFrame] = None,
    threshold: float = 0.05,
) -> pd.DataFrame:
    """
    Match games to odds via resolve_team_name; compute edge = model_prob - implied_prob.
    Return side-aware rows: slot, matchup names, model pick, market implied, edge.
    """
    if odds_df.empty:
        return pd.DataFrame(columns=[
            "slot", "team1", "team2", "model_pick", "model_prob", "implied_prob", "edge", "recommendation",
        ])
    recs = []
    for g in game_probs:
        t_lo = g["team_lower"]
        t_hi = g["team_higher"]
        model_prob = g["prob_lower_wins"]
        matched = _match_odds_row_to_game(g, odds_df, teams_df)
        if matched is None:
            continue
        implied, _, _ = matched
        edge = model_prob - implied
        if abs(edge) < threshold:
            continue
        name_lo = _team_id_to_name(t_lo, teams_df)
        name_hi = _team_id_to_name(t_hi, teams_df)
        if edge > 0:
            model_pick = name_lo
            model_p_prob = model_prob
            impl_p_favored = implied
        else:
            model_pick = name_hi
            model_p_prob = 1.0 - model_prob
            impl_p_favored = 1.0 - implied
        recs.append({
            "slot": g.get("slot", ""),
            "team1": name_lo,
            "team2": name_hi,
            "model_pick": model_pick,
            "model_prob": round(model_p_prob, 4),
            "implied_prob": round(impl_p_favored, 4),
            "edge": round(edge, 4),
            "recommendation": f"model likes {model_pick} (edge {edge:+.2%})",
        })
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    return df.sort_values("edge", key=abs, ascending=False).reset_index(drop=True)


def run_value_pipeline(
    bracket_path: Path,
    raw_dir: Path = DEFAULT_RAW_DIR,
    odds_json_path: Optional[Path] = None,
    odds_csv_path: Optional[Path] = None,
    threshold: float = 0.05,
) -> pd.DataFrame:
    """Load bracket, run simulation, load odds, build recommendations."""
    game_probs, _, _, _ = load_bracket_and_simulate(bracket_path, raw_dir=raw_dir)
    odds_df = get_odds(raw_dir, json_path=odds_json_path, csv_path=odds_csv_path, use_api=True)
    data = load_all(raw_dir)
    teams_df = data.get("teams")
    return build_recommendations(game_probs, odds_df, teams_df=teams_df, threshold=threshold)
