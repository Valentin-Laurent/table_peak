"""cross_table: pairwise side-swapped evaluation across named agents."""

from __future__ import annotations

import random

from table_peak.agents.base import Agent
from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import MatchStats
from table_peak.training.eval import cross_table


def test_cross_table_contains_all_ordered_pairs() -> None:
    agents: list[tuple[str, Agent]] = [
        ("rand1", RandomAgent(random.Random(1))),
        ("rand2", RandomAgent(random.Random(2))),
        ("minimax", MinimaxAgent()),
    ]

    table = cross_table(agents, game=TicTacToe(), n_per_pair=20, seed=0)

    # Lower triangle only (i < j) — pair (a, b) is enough since play_matches
    # already swaps sides.
    expected_pairs = {("rand1", "rand2"), ("rand1", "minimax"), ("rand2", "minimax")}
    assert set(table.keys()) == expected_pairs
    for stats in table.values():
        assert isinstance(stats, MatchStats)
        assert stats.n_games == 20


def test_cross_table_minimax_never_loses_to_random() -> None:
    agents: list[tuple[str, Agent]] = [
        ("random", RandomAgent(random.Random(0))),
        ("minimax", MinimaxAgent()),
    ]

    table = cross_table(agents, game=TicTacToe(), n_per_pair=200, seed=0)

    stats = table[("random", "minimax")]
    # play_matches keys: 0 = first agent (random), 1 = second agent (minimax).
    assert stats.wins[0] == 0  # random never beats minimax
