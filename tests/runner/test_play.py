"""End-to-end tests for the game runner."""

from __future__ import annotations

import random

import pytest

from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import Outcome, play_game


def test_play_game_returns_well_formed_outcome() -> None:
    game = TicTacToe()
    agents = {0: RandomAgent(rng=random.Random(0)), 1: RandomAgent(rng=random.Random(1))}
    outcome = play_game(game, agents)
    assert isinstance(outcome, Outcome)
    assert set(outcome.returns.keys()) == {0, 1}
    assert outcome.num_moves >= 5  # TTT: minimum game length is 5 moves
    assert outcome.num_moves <= 9
    assert len(outcome.trajectory) == outcome.num_moves


def test_play_game_terminal_state_has_returns() -> None:
    game = TicTacToe()
    agents = {0: RandomAgent(rng=random.Random(7)), 1: RandomAgent(rng=random.Random(8))}
    outcome = play_game(game, agents)
    # Sum of returns is zero-sum for TTT (1 + -1 on win, 0 + 0 on draw)
    assert sum(outcome.returns.values()) in (-1.0 + 1.0, 0.0)  # i.e. 0.0


def test_play_game_trajectory_states_are_pre_action() -> None:
    """Each (state, action) pair in trajectory: action is legal in state."""
    game = TicTacToe()
    agents = {0: RandomAgent(rng=random.Random(3)), 1: RandomAgent(rng=random.Random(4))}
    outcome = play_game(game, agents)
    for state, action in outcome.trajectory:
        assert action in state.legal_actions()


def test_play_game_raises_on_mismatched_agents_dict() -> None:
    game = TicTacToe()  # num_players == 2
    agents = {0: RandomAgent()}  # missing player 1
    with pytest.raises(ValueError):
        play_game(game, agents)
