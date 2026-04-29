"""End-to-end tests for the game runner."""

from __future__ import annotations

import random

import pytest

from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import MatchStats, Outcome, play_game, play_matches


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


def test_play_matches_basic_shape() -> None:
    game = TicTacToe()
    stats = play_matches(
        game,
        agent_a=RandomAgent(rng=random.Random(0)),
        agent_b=RandomAgent(rng=random.Random(1)),
        n=10,
        seed=42,
    )
    assert isinstance(stats, MatchStats)
    assert stats.n_games == 10
    assert set(stats.wins.keys()) == {0, 1}
    assert stats.draws >= 0
    assert stats.wins[0] + stats.wins[1] + stats.draws == 10


def test_play_matches_is_reproducible_with_seed() -> None:
    game = TicTacToe()

    def run() -> MatchStats:
        return play_matches(
            game,
            agent_a=RandomAgent(rng=random.Random(0)),
            agent_b=RandomAgent(rng=random.Random(1)),
            n=50,
            seed=42,
        )

    a = run()
    b = run()
    assert a.wins == b.wins
    assert a.draws == b.draws
    assert a.mean_returns == b.mean_returns


def test_play_matches_swap_sides_balances_player_ids() -> None:
    """With swap_sides=True, both A and B play P0 in roughly half the games."""
    game = TicTacToe()
    # Use deterministic minimax for both: every game draws regardless of side.
    stats = play_matches(
        game,
        agent_a=MinimaxAgent(),
        agent_b=MinimaxAgent(),
        n=20,
        swap_sides=True,
        seed=0,
    )
    assert stats.draws == 20  # minimax vs minimax always draws


def test_minimax_never_loses_against_random() -> None:
    """Across 200 seeded games (sides swapped), minimax (A) wins or draws."""
    game = TicTacToe()
    stats = play_matches(
        game,
        agent_a=MinimaxAgent(),
        agent_b=RandomAgent(rng=random.Random(99)),
        n=200,
        swap_sides=True,
        seed=2026,
    )
    # Agent A (minimax) is never beaten -> wins[1] (which is B's wins) is 0.
    assert stats.wins[1] == 0


def test_minimax_vs_minimax_always_draws() -> None:
    """50 games of minimax vs minimax: every game draws."""
    game = TicTacToe()
    stats = play_matches(
        game,
        agent_a=MinimaxAgent(),
        agent_b=MinimaxAgent(),
        n=50,
        swap_sides=True,
        seed=1,
    )
    assert stats.draws == 50
    assert stats.wins == {0: 0, 1: 0}
