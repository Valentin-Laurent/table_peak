"""End-to-end: runner.play_game / play_matches over the adapter-wrapped Skyjo game."""

from __future__ import annotations

import random

from table_peak.agents.random import RandomAgent
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.runner.play import play_game, play_matches


def test_play_game_runs_to_terminal() -> None:
    game = SkyjoGameWrapper(num_players=2, seed=0)
    agents = {0: RandomAgent(rng=random.Random(0)), 1: RandomAgent(rng=random.Random(1))}
    outcome = play_game(game, agents)
    assert outcome.num_moves > 0
    assert set(outcome.returns.keys()) == {0, 1}


def test_play_game_three_players_runs_to_terminal() -> None:
    game = SkyjoGameWrapper(num_players=3, seed=2)
    agents = {p: RandomAgent(rng=random.Random(p)) for p in range(3)}
    outcome = play_game(game, agents)
    assert outcome.num_moves > 0
    assert set(outcome.returns.keys()) == {0, 1, 2}


def test_play_matches_reproducible_with_seed() -> None:
    # Reproducibility requires identically-seeded agents in both runs: play_matches'
    # own `seed` drives only a reserved throwaway draw, not the agents' policies.
    def run() -> object:
        return play_matches(
            SkyjoGameWrapper(num_players=2, seed=0),
            agent_a=RandomAgent(rng=random.Random(1)),
            agent_b=RandomAgent(rng=random.Random(2)),
            n=20,
            swap_sides=True,
            seed=42,
        )

    assert run() == run()
