"""Tests for bracket simulation: fixed_winners validation, next_game_probs shape."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mm.bracket.simulate import (
    run_monte_carlo,
    load_slot_tree,
    compute_next_game_probs,
    _team_to_seed_from_game_probs,
    propagate_exact_whatif,
)
from mm.features.build_matchups import feature_columns


@pytest.fixture
def mock_model():
    m = MagicMock()
    m.predict_proba.return_value = np.array([[0.6, 0.4]])  # P(lower wins) = 0.6
    return m


@pytest.fixture
def r1_games():
    """Two R1 games (minimal) for slot tree that might have R2W1 = (R1W1, R1W2)."""
    return [
        {"slot": "R1W1", "team1_id": 1001, "team2_id": 1002, "seed1": 1, "seed2": 16, "region": "W"},
        {"slot": "R1W2", "team1_id": 1003, "team2_id": 1004, "seed1": 8, "seed2": 9, "region": "W"},
    ]


@pytest.fixture
def regular_df():
    import pandas as pd
    return pd.DataFrame({
        "Season": [2024],
        "DayNum": [1],
        "WTeamID": [1001],
        "LTeamID": [1002],
        "WScore": [80],
        "LScore": [70],
    })


def test_run_monte_carlo_fixed_winners_invalid_team(r1_games, mock_model, regular_df):
    """Fixed winner must be one of the two teams in that slot."""
    feats = feature_columns()
    raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    if not (raw_dir / "MNCAATourneySlots.csv").exists():
        pytest.skip("MNCAATourneySlots.csv not found")
    with pytest.raises(ValueError, match="not a valid winner"):
        run_monte_carlo(
            r1_games,
            mock_model,
            feats,
            season=2024,
            regular=regular_df,
            massey=None,
            n_sims=2,
            fixed_winners={"R1W1": 9999},
            raw_dir=raw_dir,
        )


def test_team_to_seed_from_game_probs():
    game_probs = [
        {"slot": "R1W1", "team1_id": 1001, "team2_id": 1002, "seed1": 1, "seed2": 16},
    ]
    out = _team_to_seed_from_game_probs(game_probs)
    assert out[1001] == 1 and out[1002] == 16


def test_compute_next_game_probs_slot_order():
    """compute_next_game_probs accepts slot_order and returns dict keyed by slot."""
    game_probs = [
        {"slot": "R1W1", "team1_id": 1001, "team2_id": 1002, "team_lower": 1001, "team_higher": 1002, "prob_lower_wins": 0.6, "seed1": 1, "seed2": 16},
        {"slot": "R1W2", "team1_id": 1003, "team2_id": 1004, "team_lower": 1003, "team_higher": 1004, "prob_lower_wins": 0.5, "seed1": 8, "seed2": 9},
    ]
    slot_tree = {"R2W1": ("R1W1", "R1W2")}
    slot_order = ["R1W1", "R1W2", "R2W1"]
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[0.5, 0.5]])
    import pandas as pd
    regular = pd.DataFrame({"Season": [2024], "DayNum": [1], "WTeamID": [1001], "LTeamID": [1002], "WScore": [80], "LScore": [70]})
    out = compute_next_game_probs(
        game_probs, slot_tree, slot_order, mock_model,
        feature_columns(),
        2024, regular, None,
    )
    assert "R2W1" in out
    assert isinstance(out["R2W1"], dict)
    assert 1001 in out["R2W1"] or 1002 in out["R2W1"]


def test_propagate_exact_whatif():
    """Exact propagation with no fixed winners returns champ and advancement from R1 probs."""
    # Minimal bracket: 4 R1 -> 2 R2 -> 1 R6CH
    pairwise = {
        "1001,1002": 0.6, "1001,1003": 0.55, "1001,1004": 0.5,
        "1002,1003": 0.45, "1002,1004": 0.5, "1003,1004": 0.5,
    }
    slot_tree = {"R2W1": ["R1W1", "R1W2"], "R2W2": ["R1W3", "R1W4"], "R6CH": ["R2W1", "R2W2"]}
    slot_order = ["R1W1", "R1W2", "R1W3", "R1W4", "R2W1", "R2W2", "R6CH"]
    r1_slot_probs = {
        "R1W1": {"1001": 0.6, "1002": 0.4},
        "R1W2": {"1003": 0.5, "1004": 0.5},
        "R1W3": {"1001": 0.5, "1002": 0.5},
        "R1W4": {"1003": 0.5, "1004": 0.5},
    }
    champ, adv = propagate_exact_whatif(
        pairwise, slot_tree, slot_order, r1_slot_probs, {}
    )
    assert "champ" in adv
    assert adv["champ"] == champ
    assert set(adv.keys()) == {"champ", "final4", "elite8", "sweet16", "r2"}
    assert sum(champ.values()) == pytest.approx(1.0, abs=1e-5)


def test_propagate_exact_whatif_fixed_winner():
    """Exact propagation with one fixed R1 winner forces that outcome."""
    pairwise = {
        "1001,1002": 0.6, "1001,1003": 0.55, "1001,1004": 0.5,
        "1002,1003": 0.45, "1002,1004": 0.5, "1003,1004": 0.5,
    }
    slot_tree = {"R2W1": ["R1W1", "R1W2"], "R2W2": ["R1W3", "R1W4"], "R6CH": ["R2W1", "R2W2"]}
    slot_order = ["R1W1", "R1W2", "R1W3", "R1W4", "R2W1", "R2W2", "R6CH"]
    r1_slot_probs = {
        "R1W1": {"1001": 0.6, "1002": 0.4},
        "R1W2": {"1003": 0.5, "1004": 0.5},
        "R1W3": {"1001": 0.5, "1002": 0.5},
        "R1W4": {"1003": 0.5, "1004": 0.5},
    }
    champ, adv = propagate_exact_whatif(
        pairwise, slot_tree, slot_order, r1_slot_probs, {"R1W1": 1002}
    )
    assert champ.get(1002, 0) > 0
    assert sum(champ.values()) == pytest.approx(1.0, abs=1e-5)
