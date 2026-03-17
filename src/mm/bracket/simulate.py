"""
Bracket simulation: use a bracket source (official JSON or synthetic) and model to compute
game win probabilities, then run Monte Carlo simulations for advancement/champion odds.
"""

from pathlib import Path
from typing import Optional, Any
import pickle
import json
import numpy as np
import pandas as pd

from mm.features.build_matchups import (
    build_tourney_matchups,
    feature_columns,
    rolling_win_rates,
    season_point_margins,
    latest_massey_ranks,
    last_n_win_rate,
    avg_opponent_win_rate,
    _seed_to_int,
)
from mm.data.kaggle_loader import load_all
from mm.config import DEFAULT_SEASON, DEFAULT_N_SIMS

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"
DEFAULT_PROCESSED_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
DEFAULT_MODEL_DIR = DEFAULT_PROCESSED_DIR


def load_slot_tree(raw_dir: Path = DEFAULT_RAW_DIR, season: int = 1985) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """
    Load bracket slot dependency tree from MNCAATourneySlots: slot -> (input_slot_a, input_slot_b).
    Returns (tree for R2+ slots, list of all slots in dependency order R1..R6).
    """
    slots_path = raw_dir / "MNCAATourneySlots.csv"
    if not slots_path.exists():
        return {}, []
    df = pd.read_csv(slots_path)
    df = df[df["Season"] == season]
    tree = {}
    all_slots = []
    for _, row in df.iterrows():
        slot = str(row["Slot"])
        strong, weak = str(row["StrongSeed"]), str(row["WeakSeed"])
        all_slots.append(slot)
        if strong.startswith("R") and weak.startswith("R"):
            tree[slot] = (strong, weak)
    all_slots = sorted(set(all_slots), key=lambda s: (int(s[1]) if s[1].isdigit() else 0, s))
    return tree, all_slots


def load_model(model_dir: Path = DEFAULT_MODEL_DIR, name: str = "xgb") -> Any:
    """Load trained model (baseline or xgb) from pickle."""
    path = model_dir / "xgb_model.pkl" if name == "xgb" else model_dir / "baseline.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}. Run training first.")
    with open(path, "rb") as f:
        return pickle.load(f)


def load_feature_columns(model_dir: Path = DEFAULT_MODEL_DIR) -> list[str]:
    with open(model_dir / "feature_columns.pkl", "rb") as f:
        return pickle.load(f)


def bracket_source_from_json(
    path: Path,
    validate: bool = True,
    teams_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Load bracket from JSON. If validate=True and bracket has games, validate and normalize via official_bracket.
    """
    with open(path) as f:
        bracket = json.load(f)
    if validate and len(bracket.get("games", [])) > 0:
        from mm.bracket.official_bracket import load_and_validate
        bracket, errs = load_and_validate(path, teams_df=teams_df, normalize=True)
        if errs:
            raise ValueError("Bracket validation failed: " + "; ".join(errs))
    return bracket


def build_matchup_features_for_pair(
    team1_id: int,
    team2_id: int,
    seed1: int,
    seed2: int,
    season: int,
    regular: pd.DataFrame,
    massey: Optional[pd.DataFrame],
    through_day: int = 132,
) -> dict[str, float]:
    """Build one row of features for a single matchup (for prediction)."""
    win_rates = rolling_win_rates(regular, through_day=through_day)
    margins = season_point_margins(regular)
    massey_df = latest_massey_ranks(massey, through_day) if massey is not None else None

    wr1 = win_rates[(win_rates["Season"] == season) & (win_rates["TeamID"] == team1_id)]
    wr2 = win_rates[(win_rates["Season"] == season) & (win_rates["TeamID"] == team2_id)]
    win_rate1 = wr1["win_rate"].iloc[0] if len(wr1) else 0.5
    win_rate2 = wr2["win_rate"].iloc[0] if len(wr2) else 0.5
    if np.isnan(win_rate1):
        win_rate1 = 0.5
    if np.isnan(win_rate2):
        win_rate2 = 0.5

    m1 = margins[(margins["Season"] == season) & (margins["TeamID"] == team1_id)]
    m2 = margins[(margins["Season"] == season) & (margins["TeamID"] == team2_id)]
    margin1 = m1["point_margin_per_game"].iloc[0] if len(m1) else 0.0
    margin2 = m2["point_margin_per_game"].iloc[0] if len(m2) else 0.0

    seed_diff = seed1 - seed2
    win_rate_diff = win_rate1 - win_rate2
    margin_diff = margin1 - margin2

    massey1 = np.nan
    massey2 = np.nan
    if massey_df is not None:
        r1 = massey_df[(massey_df["Season"] == season) & (massey_df["TeamID"] == team1_id)]
        r2 = massey_df[(massey_df["Season"] == season) & (massey_df["TeamID"] == team2_id)]
        if len(r1):
            massey1 = r1["massey_rank"].iloc[0]
        if len(r2):
            massey2 = r2["massey_rank"].iloc[0]
    massey_diff = (massey2 - massey1) if (not np.isnan(massey1) and not np.isnan(massey2)) else 0.0

    last10_df = last_n_win_rate(regular, n=10, through_day=through_day)
    sos_df = avg_opponent_win_rate(regular, through_day=through_day, win_rates=win_rates)
    l10_1 = last10_df[(last10_df["Season"] == season) & (last10_df["TeamID"] == team1_id)]["last_n_win_rate"]
    l10_2 = last10_df[(last10_df["Season"] == season) & (last10_df["TeamID"] == team2_id)]["last_n_win_rate"]
    last10_1 = float(l10_1.iloc[0]) if len(l10_1) and not np.isnan(l10_1.iloc[0]) else 0.5
    last10_2 = float(l10_2.iloc[0]) if len(l10_2) and not np.isnan(l10_2.iloc[0]) else 0.5
    sos1 = sos_df[(sos_df["Season"] == season) & (sos_df["TeamID"] == team1_id)]["avg_opp_win_rate"]
    sos2 = sos_df[(sos_df["Season"] == season) & (sos_df["TeamID"] == team2_id)]["avg_opp_win_rate"]
    sos_1 = float(sos1.iloc[0]) if len(sos1) and not np.isnan(sos1.iloc[0]) else 0.5
    sos_2 = float(sos2.iloc[0]) if len(sos2) and not np.isnan(sos2.iloc[0]) else 0.5
    seed_massey_interaction = seed_diff * (massey_diff / 50.0)

    return {
        "SeedDiff": seed_diff,
        "WinRateDiff": win_rate_diff,
        "MarginDiff": margin_diff,
        "MasseyDiff": massey_diff,
        "Last10WinRateDiff": last10_1 - last10_2,
        "SOSDiff": sos_1 - sos_2,
        "SeedMasseyInteraction": seed_massey_interaction,
    }


def predict_game_proba(
    model: Any,
    feature_cols: list[str],
    team1_id: int,
    team2_id: int,
    seed1: int,
    seed2: int,
    season: int,
    regular: pd.DataFrame,
    massey: Optional[pd.DataFrame] = None,
) -> float:
    """
    Return P(lower TeamID wins). Model outputs prob for "team1" (lower ID) winning.
    """
    team1 = min(team1_id, team2_id)
    team2 = max(team1_id, team2_id)
    if team1_id <= team2_id:
        s1, s2 = seed1, seed2
    else:
        s1, s2 = seed2, seed1
    feats = build_matchup_features_for_pair(
        team1, team2, s1, s2, season, regular, massey
    )
    row = np.array([[feats[c] for c in feature_cols]])
    prob = model.predict_proba(row)[0, 1]
    return float(prob)


def run_monte_carlo(
    games: list[dict],
    model: Any,
    feature_cols: list[str],
    season: int,
    regular: pd.DataFrame,
    massey: Optional[pd.DataFrame],
    n_sims: int = 10000,
    rng: Optional[np.random.Generator] = None,
    fixed_winners: Optional[dict[str, int]] = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
) -> tuple[list[dict], dict[int, float], dict]:
    """
    games: list of {slot, team1_id, team2_id, seed1, seed2, region}.
    fixed_winners: optional dict slot -> team_id to force R1 (or later) outcomes for what-if.
    Returns (game_results with prob and sim wins, team_id -> championship prob, advancement).
    Uses full bracket tree when available (MNCAATourneySlots) for true champion/advancement odds.
    """
    rng = rng or np.random.default_rng(42)
    fixed_winners = fixed_winners or {}
    slot_tree, slot_order = load_slot_tree(raw_dir)
    r1_games_by_slot = {str(g["slot"]): g for g in games if str(g.get("slot", "")).startswith("R1")}

    # Team -> seed from R1 games (for later-round predictions)
    team_to_seed: dict[int, int] = {}
    for g in games:
        if str(g.get("slot", "")).startswith("R1"):
            t1, t2 = int(g["team1_id"]), int(g["team2_id"])
            s1, s2 = int(g.get("seed1", 8)), int(g.get("seed2", 8))
            team_to_seed[t1] = s1
            team_to_seed[t2] = s2

    # Valid winner team IDs per slot (for fixed_winners validation)
    valid_winners: dict[str, set[int]] = {}
    for slot in slot_order:
        if slot in r1_games_by_slot:
            g = r1_games_by_slot[slot]
            valid_winners[slot] = {int(g["team1_id"]), int(g["team2_id"])}
        elif slot in slot_tree:
            in1, in2 = slot_tree[slot]
            valid_winners[slot] = valid_winners.get(in1, set()) | valid_winners.get(in2, set())
    for slot, tid in (fixed_winners or {}).items():
        allowed = valid_winners.get(slot, set())
        if allowed and tid not in allowed:
            raise ValueError(f"fixed_winners: team {tid} is not a valid winner for slot {slot} (allowed: {sorted(allowed)})")

    # Precompute R1 game probs and per-game explanation (feature factors)
    game_probs = []
    for g in games:
        t1 = int(g["team1_id"])
        t2 = int(g["team2_id"])
        s1 = int(g.get("seed1", 8))
        s2 = int(g.get("seed2", 8))
        feats = build_matchup_features_for_pair(t1, t2, s1, s2, season, regular, massey)
        p = predict_game_proba(
            model, feature_cols, t1, t2, s1, s2, season, regular, massey
        )
        game_probs.append({
            **g,
            "prob_lower_wins": p,
            "team_lower": min(t1, t2),
            "team_higher": max(t1, t2),
            "explanation": feats,
        })
    r1_probs_by_slot = {}
    for gp in game_probs:
        slot = str(gp.get("slot", ""))
        if slot.startswith("R1"):
            r1_probs_by_slot[slot] = gp

    # Full-bracket simulation when we have slot tree and all 32 R1 slots filled
    r1_slots_in_tree = [s for s in slot_order if s.startswith("R1")]
    has_all_r1 = slot_tree and "R6CH" in slot_tree and all(s in r1_probs_by_slot for s in r1_slots_in_tree)
    if has_all_r1:
        champ_counts = {}
        final4_counts = {}
        elite8_counts = {}
        sweet16_counts = {}
        r2_counts = {}
        report_every = max(1, n_sims // 10)
        for sim_i in range(n_sims):
            if (sim_i + 1) % report_every == 0 or sim_i == 0:
                print(f"   sims {sim_i + 1}/{n_sims}", flush=True)
            winners = {}
            for slot in slot_order:
                if slot in fixed_winners:
                    w = fixed_winners[slot]
                    winners[slot] = w
                    if slot.startswith("R2"):
                        r2_counts[w] = r2_counts.get(w, 0) + 1
                    elif slot.startswith("R3"):
                        sweet16_counts[w] = sweet16_counts.get(w, 0) + 1
                    elif slot.startswith("R4"):
                        elite8_counts[w] = elite8_counts.get(w, 0) + 1
                    elif slot.startswith("R5"):
                        final4_counts[w] = final4_counts.get(w, 0) + 1
                elif slot in r1_probs_by_slot:
                    gp = r1_probs_by_slot[slot]
                    w = gp["team_lower"] if rng.random() < gp["prob_lower_wins"] else gp["team_higher"]
                    winners[slot] = w
                elif slot in slot_tree:
                    sa, sb = slot_tree[slot]
                    ta, tb = winners.get(sa), winners.get(sb)
                    if ta is not None and tb is not None:
                        s1 = team_to_seed.get(ta, 8)
                        s2 = team_to_seed.get(tb, 8)
                        p = predict_game_proba(
                            model, feature_cols, ta, tb, s1, s2, season, regular, massey
                        )
                        w = min(ta, tb) if rng.random() < p else max(ta, tb)
                        winners[slot] = w
                        if slot.startswith("R2"):
                            r2_counts[w] = r2_counts.get(w, 0) + 1
                        elif slot.startswith("R3"):
                            sweet16_counts[w] = sweet16_counts.get(w, 0) + 1
                        elif slot.startswith("R4"):
                            elite8_counts[w] = elite8_counts.get(w, 0) + 1
                        elif slot.startswith("R5"):
                            final4_counts[w] = final4_counts.get(w, 0) + 1
            champ = winners.get("R6CH")
            if champ is not None:
                champ_counts[champ] = champ_counts.get(champ, 0) + 1
        champ_probs = {tid: c / n_sims for tid, c in champ_counts.items()}
        advancement = {
            "champ": champ_probs,
            "final4": {tid: c / n_sims for tid, c in final4_counts.items()},
            "elite8": {tid: c / n_sims for tid, c in elite8_counts.items()},
            "sweet16": {tid: c / n_sims for tid, c in sweet16_counts.items()},
            "r2": {tid: c / n_sims for tid, c in r2_counts.items()},
        }
        return game_probs, champ_probs, advancement
    # Fallback: independent R1 games only, champion = winner of last game in list
    champ_counts = {}
    report_every = max(1, n_sims // 10)
    for sim_i in range(n_sims):
        if (sim_i + 1) % report_every == 0 or sim_i == 0:
            print(f"   sims {sim_i + 1}/{n_sims}", flush=True)
        last_w = None
        for gp in game_probs:
            slot = str(gp.get("slot", ""))
            if slot in fixed_winners:
                w = fixed_winners[slot]
            else:
                w = gp["team_lower"] if rng.random() < gp["prob_lower_wins"] else gp["team_higher"]
            last_w = w
        if last_w is not None:
            champ_counts[last_w] = champ_counts.get(last_w, 0) + 1
    champ_probs = {tid: c / n_sims for tid, c in champ_counts.items()}
    return game_probs, champ_probs, {}


def _team_to_seed_from_game_probs(game_probs: list[dict]) -> dict[int, int]:
    """Build team_id -> seed from R1 games."""
    out: dict[int, int] = {}
    for g in game_probs:
        if str(g.get("slot", "")).startswith("R1"):
            t1, t2 = int(g["team1_id"]), int(g["team2_id"])
            s1, s2 = int(g.get("seed1", 8)), int(g.get("seed2", 8))
            out[t1] = s1
            out[t2] = s2
    return out


def build_pairwise_win_matrix(
    game_probs: list[dict],
    model: Any,
    feature_cols: list[str],
    season: int,
    regular: pd.DataFrame,
    massey: Optional[pd.DataFrame],
) -> dict[str, float]:
    """
    For every pair of teams that appear in the bracket, compute P(lower_id wins).
    Returns dict with key "tid_lo,tid_hi" -> prob (so JSON-serializable).
    Used by dashboard to run exact what-if propagation without the model.
    """
    team_to_seed = _team_to_seed_from_game_probs(game_probs)
    team_ids = sorted(set(team_to_seed.keys()))
    out: dict[str, float] = {}
    for i, t1 in enumerate(team_ids):
        for t2 in team_ids[i + 1 :]:
            s1 = team_to_seed.get(t1, 8)
            s2 = team_to_seed.get(t2, 8)
            p_lo = predict_game_proba(
                model, feature_cols, t1, t2, s1, s2, season, regular, massey
            )
            key = f"{min(t1, t2)},{max(t1, t2)}"
            out[key] = round(p_lo, 6)
    return out


def propagate_exact_whatif(
    pairwise_win_prob: dict[str, float],
    slot_tree: dict[str, list[str]],
    slot_order: list[str],
    r1_slot_probs: dict[str, dict[str, float]],
    fixed_winners: dict[str, int],
) -> tuple[dict[int, float], dict[str, dict[int, float]]]:
    """
    Compute champion and advancement odds by propagating slot winner distributions
    through the bracket using precomputed pairwise win probs. fixed_winners: slot -> team_id.
    Returns (champion_odds, advancement) where advancement has keys champ, final4, elite8, sweet16, r2.
    """

    def pair_key(t1: int, t2: int) -> str:
        return f"{min(t1, t2)},{max(t1, t2)}"

    # Valid winners per slot for validation
    valid_winners: dict[str, set[int]] = {}
    for slot in slot_order:
        if slot in r1_slot_probs:
            valid_winners[slot] = {int(t) for t in r1_slot_probs[slot]}
        elif slot in slot_tree:
            in1, in2 = slot_tree[slot]
            valid_winners[slot] = valid_winners.get(in1, set()) | valid_winners.get(in2, set())
    for slot, tid in fixed_winners.items():
        allowed = valid_winners.get(slot, set())
        if allowed and tid not in allowed:
            raise ValueError(
                f"fixed_winners: team {tid} is not a valid winner for slot {slot} (allowed: {sorted(allowed)})"
            )

    slot_probs: dict[str, dict[str, float]] = {}
    for slot in slot_order:
        if slot in fixed_winners:
            slot_probs[slot] = {str(fixed_winners[slot]): 1.0}
        elif slot in r1_slot_probs:
            slot_probs[slot] = dict(r1_slot_probs[slot])
        elif slot in slot_tree:
            in1, in2 = slot_tree[slot]
            p1 = slot_probs.get(in1)
            p2 = slot_probs.get(in2)
            if not p1 or not p2:
                continue
            slot_probs[slot] = {}
            for t1_str, prob1 in p1.items():
                for t2_str, prob2 in p2.items():
                    if t1_str == t2_str:
                        # Same team won both feeder slots -> they win this slot
                        slot_probs[slot][t1_str] = slot_probs[slot].get(t1_str, 0.0) + prob1 * prob2
                        continue
                    t1, t2 = int(t1_str), int(t2_str)
                    p_match = prob1 * prob2
                    key = pair_key(t1, t2)
                    p_t1_wins = pairwise_win_prob.get(key, 0.5)
                    slot_probs[slot][t1_str] = slot_probs[slot].get(t1_str, 0.0) + p_match * p_t1_wins
                    slot_probs[slot][t2_str] = slot_probs[slot].get(t2_str, 0.0) + p_match * (1.0 - p_t1_wins)

    champ_probs = slot_probs.get("R6CH") or {}
    champion_odds = {int(tid): float(p) for tid, p in champ_probs.items()}

    def round_probs(slots: list[str]) -> dict[int, float]:
        out: dict[int, float] = {}
        for s in slots:
            for tid_str, p in (slot_probs.get(s) or {}).items():
                tid = int(tid_str)
                out[tid] = out.get(tid, 0.0) + p
        return out

    r2_slots = [s for s in slot_order if s.startswith("R2")]
    r3_slots = [s for s in slot_order if s.startswith("R3")]
    r4_slots = [s for s in slot_order if s.startswith("R4")]
    r5_slots = [s for s in slot_order if s.startswith("R5")]

    advancement = {
        "champ": champion_odds,
        "final4": round_probs(r5_slots),
        "elite8": round_probs(r4_slots),
        "sweet16": round_probs(r3_slots),
        "r2": round_probs(r2_slots),
    }
    return champion_odds, advancement


def compute_next_game_probs(
    game_probs: list[dict],
    slot_tree: dict[str, tuple[str, str]],
    slot_order: list[str],
    model: Any,
    feature_cols: list[str],
    season: int,
    regular: pd.DataFrame,
    massey: Optional[pd.DataFrame],
) -> dict[str, dict[int, float]]:
    """
    For each R2+ slot, compute P(team wins this game) by chaining probs from feeder slots.
    Computes in dependency order so R3 uses R2 probs, etc. Returns dict[slot, dict[team_id, prob]].
    """
    team_to_seed = _team_to_seed_from_game_probs(game_probs)
    r1_by_slot = {str(g["slot"]): g for g in game_probs if str(g.get("slot", "")).startswith("R1")}
    slot_probs: dict[str, dict[int, float]] = {}
    for slot in slot_order:
        if slot in r1_by_slot:
            g = r1_by_slot[slot]
            t_lo, t_hi = int(g["team_lower"]), int(g["team_higher"])
            p_lo = float(g["prob_lower_wins"])
            slot_probs[slot] = {t_lo: p_lo, t_hi: 1.0 - p_lo}
            continue
        if slot not in slot_tree:
            continue
        in1, in2 = slot_tree[slot]
        p1 = slot_probs.get(in1)
        p2 = slot_probs.get(in2)
        if not p1 or not p2:
            continue
        slot_probs[slot] = {}
        for t1, prob1 in p1.items():
            for t2, prob2 in p2.items():
                if t1 == t2:
                    continue
                p_match = prob1 * prob2
                s1 = team_to_seed.get(t1, 8)
                s2 = team_to_seed.get(t2, 8)
                p_t1_wins = predict_game_proba(
                    model, feature_cols, t1, t2, s1, s2, season, regular, massey
                )
                slot_probs[slot][t1] = slot_probs[slot].get(t1, 0.0) + p_match * p_t1_wins
                slot_probs[slot][t2] = slot_probs[slot].get(t2, 0.0) + p_match * (1.0 - p_t1_wins)
    return slot_probs


def load_bracket_and_simulate(
    bracket_path: Path,
    raw_dir: Path = DEFAULT_RAW_DIR,
    model_dir: Path = DEFAULT_MODEL_DIR,
    season: int = DEFAULT_SEASON,
    n_sims: int = DEFAULT_N_SIMS,
    fixed_winners: Optional[dict[str, int]] = None,
) -> tuple[list[dict], dict[int, float], dict, dict]:
    """
    Load bracket JSON, load data and model, run Monte Carlo. Returns (game_probs, champ_probs, advancement, next_game_probs).
    next_game_probs: dict[slot, dict[team_id, P(team wins that game)]] for R2+ slots (chained probs).
    fixed_winners: optional slot -> team_id for what-if (e.g. lock R1 outcomes).
    """
    data = load_all(raw_dir)
    if "regular" not in data:
        raise FileNotFoundError("Need regular season data in raw_dir")
    regular = data["regular"]
    # Use latest season if requested season not in data (e.g. 2026 before data release)
    if season not in regular["Season"].values:
        season = int(regular["Season"].max())
    massey = data.get("massey")
    if massey is not None:
        massey = massey[massey["Season"] == season]

    teams_df = data.get("teams")
    bracket = bracket_source_from_json(bracket_path, validate=True, teams_df=teams_df)
    games = bracket.get("games", [])
    if not games:
        raise ValueError("Bracket JSON must contain 'games' list")
    # Normalize keys
    normalized = []
    for g in games:
        ng = dict(g)
        if "team1_id" not in ng and "Team1ID" in ng:
            ng["team1_id"] = ng["Team1ID"]
            ng["team2_id"] = ng["Team2ID"]
            ng["seed1"] = ng.get("Seed1", 8)
            ng["seed2"] = ng.get("Seed2", 8)
        normalized.append(ng)
    games = normalized

    model = load_model(model_dir, "xgb")
    feats = load_feature_columns(model_dir)
    game_probs, champ_probs, advancement = run_monte_carlo(
        games, model, feats, season, data["regular"], massey, n_sims=n_sims, fixed_winners=fixed_winners, raw_dir=raw_dir
    )
    slot_tree, slot_order = load_slot_tree(raw_dir)
    next_game_probs = compute_next_game_probs(
        game_probs, slot_tree, slot_order, model, feats, season, data["regular"], massey
    )
    return game_probs, champ_probs, advancement, next_game_probs


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--bracket", type=Path, default=DEFAULT_RAW_DIR / "bracket_2026.json")
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    p.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    p.add_argument("--season", type=int, default=DEFAULT_SEASON)
    p.add_argument("--n-sims", type=int, default=DEFAULT_N_SIMS)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    if not args.bracket.exists():
        print("Bracket file not found. Use placeholder or fill after release.")
        return
    game_results, champ_probs, advancement, _ = load_bracket_and_simulate(
        args.bracket, args.raw_dir, args.model_dir, args.season, args.n_sims
    )
    print("Game-level probs (first 5):")
    for g in game_results[:5]:
        print(g)
    print("\nTop 5 champion probabilities:")
    for tid, prob in sorted(champ_probs.items(), key=lambda x: -x[1])[:5]:
        print(f"  Team {tid}: {prob:.2%}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(game_results).to_csv(args.out / "game_probs.csv", index=False)
        pd.Series(champ_probs).to_csv(args.out / "champ_probs.csv")
