"""Tests for bracket loading and validation."""

import json
from pathlib import Path

import pytest

from mm.bracket.official_bracket import (
    validate_bracket,
    normalize_bracket,
    load_and_validate,
    resolve_team_name,
)


@pytest.fixture
def minimal_bracket():
    return {
        "teams": [
            {"id": 1001, "name": "Duke"},
            {"id": 1002, "name": "North Carolina"},
        ],
        "games": [
            {"slot": "R1W1", "team1_id": 1001, "team2_id": 1002, "seed1": 1, "seed2": 16, "region": "W"},
        ],
    }


def test_validate_bracket_minimal(minimal_bracket):
    errs = validate_bracket(minimal_bracket)
    assert errs == []


def test_validate_bracket_no_games():
    errs = validate_bracket({"teams": [{"id": 1}, {"id": 2}], "games": []})
    assert any("No games" in e for e in errs)


def test_validate_bracket_duplicate_matchup():
    b = {
        "teams": [{"id": 1}, {"id": 2}],
        "games": [
            {"slot": "R1W1", "team1_id": 1, "team2_id": 2},
            {"slot": "R1W2", "team1_id": 1, "team2_id": 2},
        ],
    }
    errs = validate_bracket(b)
    assert any("duplicate" in e.lower() for e in errs)


def test_normalize_bracket_preserves_ids(minimal_bracket):
    out = normalize_bracket(minimal_bracket, teams_df=None)
    assert out["teams"] == minimal_bracket["teams"]
    g = out["games"][0]
    assert g["team1_id"] == 1001 and g["team2_id"] == 1002
    assert g["seed1"] == 1 and g["seed2"] == 16


def test_load_and_validate(tmp_path, minimal_bracket):
    path = tmp_path / "bracket.json"
    path.write_text(json.dumps(minimal_bracket))
    bracket, errs = load_and_validate(path, teams_df=None, normalize=True)
    assert errs == []
    assert len(bracket["games"]) == 1
    assert bracket["games"][0]["team1_id"] == 1001
