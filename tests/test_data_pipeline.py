"""Tests for data loaders and schema validation."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from mm.data.kaggle_loader import (
    load_all,
    load_teams,
    load_tourney_seeds,
    load_regular_season_compact,
    load_massey_ordinals,
)
from mm.data.sports_reference import (
    validate_teams_schema,
    validate_seeds_schema,
    validate_results_schema,
    validate_massey_schema,
    load_season_ratings,
)
from mm.data.validate_schema import run_validation


@pytest.fixture
def raw_dir(tmp_path):
    """Create minimal Kaggle-style CSVs in a temp dir."""
    (tmp_path / "MTeams.csv").write_text("TeamID,TeamName\n1001,Duke\n1002,North Carolina\n")
    (tmp_path / "MSeasons.csv").write_text("Season\n2024\n2025\n")
    (tmp_path / "MNCAATourneySeeds.csv").write_text(
        "Season,Seed,TeamID\n2024,W01,1001\n2024,X16,1002\n"
    )
    (tmp_path / "MRegularSeasonCompactResults.csv").write_text(
        "Season,DayNum,WTeamID,LTeamID,WScore,LScore\n"
        "2024,1,1001,1002,80,70\n"
    )
    (tmp_path / "MMasseyOrdinals.csv").write_text(
        "Season,RankingDayNum,SystemName,TeamID,OrdinalRank\n"
        "2024,132,SYS,1001,1\n2024,132,SYS,1002,2\n"
    )
    return tmp_path


def test_load_teams(raw_dir):
    df = load_teams(raw_dir)
    assert "TeamID" in df.columns
    assert len(df) == 2
    assert set(df["TeamID"]) == {1001, 1002}


def test_load_all_returns_partial(raw_dir):
    data = load_all(raw_dir)
    assert "teams" in data
    assert "seasons" in data
    assert "seeds" in data
    assert "regular" in data
    assert "massey" in data


def test_load_teams_missing_raises():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(FileNotFoundError):
            load_teams(Path(d))


def test_validate_teams_schema():
    ok = pd.DataFrame({"TeamID": [1, 2], "TeamName": ["A", "B"]})
    assert validate_teams_schema(ok) == []
    bad = pd.DataFrame({"id": [1], "name": ["A"]})
    assert len(validate_teams_schema(bad)) > 0


def test_validate_seeds_schema():
    ok = pd.DataFrame({"Season": [2024], "Seed": ["W01"], "TeamID": [1001]})
    assert validate_seeds_schema(ok) == []


def test_validate_results_schema():
    ok = pd.DataFrame({
        "Season": [2024], "DayNum": [1],
        "WTeamID": [1001], "LTeamID": [1002],
        "WScore": [80], "LScore": [70],
    })
    assert validate_results_schema(ok, "test") == []


def test_validate_massey_schema():
    ok = pd.DataFrame({
        "Season": [2024], "RankingDayNum": [132],
        "SystemName": ["SYS"], "TeamID": [1001], "OrdinalRank": [1],
    })
    assert validate_massey_schema(ok) == []


def test_run_validation_passes(raw_dir):
    errs = run_validation(raw_dir)
    assert errs == []


def test_load_season_ratings_missing_returns_none():
    with tempfile.TemporaryDirectory() as d:
        out = load_season_ratings(raw_dir=Path(d))
    assert out is None
