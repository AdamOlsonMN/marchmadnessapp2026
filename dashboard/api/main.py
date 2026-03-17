"""
FastAPI backend for the interactive bracket dashboard.
GET /bracket — bracket structure, game probs, champ/advancement odds.
POST /whatif — body: { "fixed_winners": { "R1W1": 1181, ... } }; returns updated odds.
"""

import os
import sqlite3
import sys
from pathlib import Path

# Ensure project src is on path when run from dashboard/api
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json as _json

from mm.config import (
    BRACKET_PATH,
    HISTORY_DB,
    RAW_DIR,
    PROCESSED_DIR,
    DASHBOARD_N_SIMS,
    DASHBOARD_BRACKET_CACHE,
    DASHBOARD_MATCHUP_MATRIX,
    model_info,
)
from mm.bracket.simulate import load_bracket_and_simulate, load_slot_tree, propagate_exact_whatif

app = FastAPI(title="March Madness Bracket API", version="0.1.0")

_cors_origins = os.environ.get("CORS_ORIGINS", "").strip()
_origins = [x.strip() for x in _cors_origins.split(",") if x.strip()] if _cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WhatIfRequest(BaseModel):
    fixed_winners: dict[str, int] = {}  # slot -> team_id


def _explanation_summary(feats: dict) -> str:
    """One-line summary of why the model favors one side (positive diff = favors team1/lower)."""
    if not feats:
        return ""
    parts = []
    if feats.get("SeedDiff", 0) != 0:
        parts.append("better seed" if feats["SeedDiff"] > 0 else "worse seed")
    if feats.get("WinRateDiff", 0) > 0.05:
        parts.append("higher win rate")
    elif feats.get("WinRateDiff", 0) < -0.05:
        parts.append("lower win rate")
    if feats.get("MarginDiff", 0) > 1:
        parts.append("better margin")
    elif feats.get("MarginDiff", 0) < -1:
        parts.append("worse margin")
    if feats.get("MasseyDiff", 0) < -5:
        parts.append("better ranking")
    elif feats.get("MasseyDiff", 0) > 5:
        parts.append("worse ranking")
    return "; ".join(parts) if parts else "even factors"


def _game_to_response(g, teams_by_id):
    """Convert game_probs item to API game shape with prob_team1, prob_team2 and explanation."""
    slot = g.get("slot", "")
    t1 = int(g["team1_id"])
    t2 = int(g["team2_id"])
    team_lower = min(t1, t2)
    team_higher = max(t1, t2)
    p_lower = g.get("prob_lower_wins", 0.5)
    prob_team1 = p_lower if t1 == team_lower else (1.0 - p_lower)
    prob_team2 = 1.0 - prob_team1
    expl = g.get("explanation") or {}
    out = {
        "slot": slot,
        "team1_id": t1,
        "team2_id": t2,
        "seed1": int(g.get("seed1", 8)),
        "seed2": int(g.get("seed2", 8)),
        "region": g.get("region", ""),
        "prob_team1": round(prob_team1, 4),
        "prob_team2": round(prob_team2, 4),
    }
    if expl:
        out["explanation"] = {
            "seedDiff": expl.get("SeedDiff", 0),
            "winRateDiff": round(expl.get("WinRateDiff", 0), 4),
            "marginDiff": round(expl.get("MarginDiff", 0), 2),
            "masseyDiff": round(expl.get("MasseyDiff", 0), 1),
            "last10WinRateDiff": round(expl.get("Last10WinRateDiff", 0), 4),
            "sosDiff": round(expl.get("SOSDiff", 0), 4),
            "summary": _explanation_summary(expl),
        }
    return out


def _load_bracket_cache(bracket_path: Path):
    """Return cached GET /bracket response if cache exists and bracket mtime matches, else None."""
    if not DASHBOARD_BRACKET_CACHE.exists() or not bracket_path.exists():
        return None
    try:
        with open(DASHBOARD_BRACKET_CACHE) as f:
            data = _json.load(f)
        if data.get("bracket_mtime") != bracket_path.stat().st_mtime:
            return None
        return data.get("response")
    except Exception:
        return None


def _save_bracket_cache(response: dict, bracket_path: Path) -> None:
    """Write GET /bracket response to cache keyed by bracket mtime."""
    DASHBOARD_BRACKET_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_BRACKET_CACHE, "w") as f:
        _json.dump({"bracket_mtime": bracket_path.stat().st_mtime, "response": response}, f, indent=0)


def _load_matchup_matrix():
    """Load dashboard matchup matrix artifact for exact what-if. Returns None if missing."""
    if not DASHBOARD_MATCHUP_MATRIX.exists():
        return None
    try:
        with open(DASHBOARD_MATCHUP_MATRIX) as f:
            return _json.load(f)
    except Exception:
        return None


def _build_bracket_response(bracket: dict, game_probs: list, champ_probs: dict, advancement: dict, next_game_probs: dict, slot_tree: dict, slot_order: list) -> dict:
    """Build full GET /bracket response from sim outputs."""
    teams = bracket.get("teams", [])
    teams_by_id = {t["id"]: t for t in teams}
    slot_tree_json = {slot: list(pair) for slot, pair in slot_tree.items()}
    games = [_game_to_response(g, teams_by_id) for g in game_probs]
    champion_odds = {str(tid): round(p, 4) for tid, p in champ_probs.items()}
    advancement_json = {}
    for key in ("champ", "final4", "elite8", "sweet16", "r2"):
        advancement_json[key] = {str(tid): round(p, 4) for tid, p in advancement.get(key, {}).items()}
    next_game_probs_json = {slot: {str(tid): round(p, 4) for tid, p in probs.items()} for slot, probs in next_game_probs.items()}
    strongest = [gg for gg in games if max(gg["prob_team1"], gg["prob_team2"]) >= 0.70]
    coin_flips = [gg for gg in games if 0.45 <= min(gg["prob_team1"], gg["prob_team2"]) <= 0.55]
    pick_summary = {"strongestPicks": strongest[:15], "coinFlips": coin_flips[:15]}
    return {
        "teams": teams,
        "games": games,
        "slotTree": slot_tree_json,
        "slotOrder": slot_order,
        "championOdds": champion_odds,
        "advancement": advancement_json,
        "nextGameProbs": next_game_probs_json,
        "pickSummary": pick_summary,
        "modelInfo": model_info(DASHBOARD_N_SIMS),
    }


@app.get("/health")
def get_health():
    """Health check for load balancers and Docker. Returns 200 when the API is up."""
    return {"status": "ok"}


@app.get("/bracket")
def get_bracket():
    """Return bracket structure and predictions from cache. Run scripts/refresh.py to generate or update."""
    if not BRACKET_PATH.exists():
        raise HTTPException(status_code=404, detail="Bracket file not found. Add data/raw/bracket_2026.json")
    cached = _load_bracket_cache(BRACKET_PATH)
    if cached is not None:
        return cached
    raise HTTPException(
        status_code=503,
        detail="Bracket cache missing. Run: python scripts/refresh.py",
    )


@app.get("/history/upsets")
def get_history_upsets(seed_matchup: str | None = None):
    """Return upset rate for a seed matchup (e.g. 5v12) or all matchups."""
    if not HISTORY_DB.exists():
        return {"matchups": [], "detail": "History DB not built. Run scripts/ingest_history.py"}
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    try:
        if seed_matchup:
            parts = seed_matchup.replace("v", " ").replace("V", " ").split()
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Use seed_matchup e.g. 5v12")
            try:
                s_high, s_low = int(parts[0]), int(parts[1])
                if s_high > s_low:
                    s_high, s_low = s_low, s_high
            except ValueError:
                raise HTTPException(status_code=400, detail="Seeds must be integers")
            cur = conn.execute(
                """
                SELECT COUNT(*) as n, SUM(upset) as upsets FROM tourney_games
                WHERE ((winner_seed = ? AND loser_seed = ?) OR (winner_seed = ? AND loser_seed = ?))
                AND winner_seed > 0 AND loser_seed > 0
                """,
                (s_high, s_low, s_low, s_high),
            )
            row = cur.fetchone()
            n = row["n"] or 0
            upsets = row["upsets"] or 0
            rate = (upsets / n * 100) if n else 0
            return {"seed_matchup": f"{s_high}v{s_low}", "games": n, "upsets": upsets, "upset_rate_pct": round(rate, 1)}
        cur = conn.execute(
            """
            SELECT
                CASE WHEN winner_seed < loser_seed THEN winner_seed ELSE loser_seed END AS seed_high,
                CASE WHEN winner_seed < loser_seed THEN loser_seed ELSE winner_seed END AS seed_low,
                COUNT(*) AS n, SUM(upset) AS upsets
            FROM tourney_games
            WHERE winner_seed > 0 AND loser_seed > 0
            GROUP BY seed_high, seed_low
            HAVING n >= 5
            ORDER BY seed_high, seed_low
            """
        )
        matchups = []
        for row in cur.fetchall():
            sh, sl = row["seed_high"], row["seed_low"]
            n, u = row["n"], row["upsets"] or 0
            matchups.append({"seed_matchup": f"{sh}v{sl}", "games": n, "upsets": u, "upset_rate_pct": round(u / n * 100, 1)})
        return {"matchups": matchups}
    finally:
        conn.close()


@app.get("/history/round")
def get_history_round(round_day: int | None = None):
    """Return summary by round (day_num). If round_day omitted, return counts by round."""
    if not HISTORY_DB.exists():
        return {"rounds": [], "detail": "History DB not built. Run scripts/ingest_history.py"}
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    try:
        if round_day is not None:
            cur = conn.execute(
                "SELECT season, COUNT(*) as games, SUM(upset) as upsets FROM tourney_games WHERE round_day = ? GROUP BY season",
                (round_day,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            return {"round_day": round_day, "by_season": rows}
        cur = conn.execute(
            "SELECT round_day, COUNT(*) as games FROM tourney_games GROUP BY round_day ORDER BY round_day"
        )
        rounds = [{"round_day": r["round_day"], "games": r["games"]} for r in cur.fetchall()]
        return {"rounds": rounds}
    finally:
        conn.close()


@app.get("/value")
def get_value(threshold: float = 0.05):
    """Return value recommendations (model vs market) for bracket games. Requires odds data in raw_dir."""
    if not BRACKET_PATH.exists():
        raise HTTPException(status_code=404, detail="Bracket file not found")
    try:
        from mm.value.recommendations import run_value_pipeline
        recs = run_value_pipeline(BRACKET_PATH, raw_dir=RAW_DIR, threshold=threshold)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {
        "recommendations": recs.to_dict("records") if not recs.empty else [],
        "threshold": threshold,
    }


@app.post("/whatif")
def post_whatif(body: WhatIfRequest):
    """Update champion and advancement odds using precomputed matchup matrix (exact propagation)."""
    if not BRACKET_PATH.exists():
        raise HTTPException(status_code=404, detail="Bracket file not found")
    fixed = body.fixed_winners or {}
    matrix = _load_matchup_matrix()
    if matrix is not None:
        try:
            champ_probs, advancement = propagate_exact_whatif(
                pairwise_win_prob=matrix["pairwise_win_prob"],
                slot_tree=matrix["slot_tree"],
                slot_order=matrix["slot_order"],
                r1_slot_probs=matrix["r1_slot_probs"],
                fixed_winners=fixed,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        try:
            _, champ_probs, advancement, _ = load_bracket_and_simulate(
                BRACKET_PATH,
                raw_dir=RAW_DIR,
                model_dir=PROCESSED_DIR,
                n_sims=DASHBOARD_N_SIMS,
                fixed_winners=fixed,
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    champion_odds = {str(tid): round(p, 4) for tid, p in champ_probs.items()}
    advancement_json = {}
    for key in ("champ", "final4", "elite8", "sweet16", "r2"):
        if key in advancement and advancement[key]:
            advancement_json[key] = {str(tid): round(p, 4) for tid, p in advancement[key].items()}
        else:
            advancement_json[key] = {}

    return {
        "championOdds": champion_odds,
        "advancement": advancement_json,
    }
