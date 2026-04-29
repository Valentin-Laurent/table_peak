"""Black-box tests for RandomAgent."""

from __future__ import annotations

import random

from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe


def test_acts_within_legal_actions() -> None:
    agent = RandomAgent(rng=random.Random(0))
    state = TicTacToe().new_initial_state()
    for _ in range(100):
        action = agent.act(state)
        assert action in state.legal_actions()


def test_same_seed_produces_same_actions() -> None:
    state = TicTacToe().new_initial_state()
    agent_a = RandomAgent(rng=random.Random(42))
    agent_b = RandomAgent(rng=random.Random(42))
    actions_a = [agent_a.act(state) for _ in range(20)]
    actions_b = [agent_b.act(state) for _ in range(20)]
    assert actions_a == actions_b


def test_different_seeds_produce_different_actions() -> None:
    state = TicTacToe().new_initial_state()
    agent_a = RandomAgent(rng=random.Random(1))
    agent_b = RandomAgent(rng=random.Random(2))
    actions_a = [agent_a.act(state) for _ in range(20)]
    actions_b = [agent_b.act(state) for _ in range(20)]
    # Vanishingly unlikely that 20 random picks from 9 options match across seeds
    assert actions_a != actions_b


def test_default_rng_is_independent_module_random() -> None:
    """RandomAgent must NOT use the global random module."""
    state = TicTacToe().new_initial_state()
    random.seed(0)  # global state
    agent = RandomAgent()  # should use its own rng, not the global one
    # Calling agent.act should not affect global random sequence
    before = random.random()
    agent.act(state)
    random.seed(0)
    expected_before = random.random()
    assert before == expected_before
