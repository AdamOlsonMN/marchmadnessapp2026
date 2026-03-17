"""Tests for value recommendations: team resolution and side-aware output."""

import pandas as pd
import pytest

from mm.value.recommendations import build_recommendations
from mm.bracket.official_bracket import resolve_team_name


@pytest.fixture
def teams_df():
    return pd.DataFrame({"TeamID": [1001, 1002], "TeamName": ["Duke", "North Carolina"]})


@pytest.fixture
def game_probs():
    return [
        {"slot": "R1W1", "team_lower": 1001, "team_higher": 1002, "prob_lower_wins": 0.65},
    ]


def test_build_recommendations_empty_odds(game_probs):
    recs = build_recommendations(game_probs, pd.DataFrame(), teams_df=None, threshold=0.05)
    assert recs.empty
    assert "model_pick" in recs.columns or recs.columns.empty


def test_build_recommendations_match_and_edge(game_probs, teams_df):
    odds = pd.DataFrame([
        {"home_team": "Duke", "away_team": "North Carolina", "implied_prob": 0.55},
    ])
    recs = build_recommendations(game_probs, odds, teams_df=teams_df, threshold=0.05)
    assert len(recs) == 1
    assert recs.iloc[0]["model_pick"] == "Duke"
    assert recs.iloc[0]["edge"] > 0
    assert "team1" in recs.columns and "team2" in recs.columns


def test_build_recommendations_no_match_below_threshold(game_probs, teams_df):
    odds = pd.DataFrame([
        {"home_team": "Duke", "away_team": "North Carolina", "implied_prob": 0.64},
    ])
    recs = build_recommendations(game_probs, odds, teams_df=teams_df, threshold=0.05)
    assert len(recs) == 0


def test_resolve_team_name_alias(teams_df):
    """resolve_team_name from official_bracket used by recommendations."""
    assert resolve_team_name("Duke", teams_df) == 1001
    assert resolve_team_name("north carolina", teams_df) == 1002
