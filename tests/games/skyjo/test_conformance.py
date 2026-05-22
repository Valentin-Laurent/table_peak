"""Conformance: pyspiel's random_sim_test validates State invariants under random rollouts."""

from __future__ import annotations

import random

import pyspiel  # type: ignore[import-not-found]
import pytest

import table_peak.games.skyjo  # noqa: F401

# ---------------------------------------------------------------------------
# pyspiel.random_sim_test harness
# ---------------------------------------------------------------------------
# pyspiel.random_sim_test is bound in the C++ pybind layer (pyspiel.so) — no
# separate Python import is needed.  Signature:
#   pyspiel.random_sim_test(game, num_sims, serialize, verbose, ...)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("num_players", [2, 3, 4, 6, 8])
def test_pyspiel_random_sim_test(num_players: int) -> None:
    """Run pyspiel's built-in C++ random-sim harness for each player count."""
    game = pyspiel.load_game("skyjo", {"num_players": num_players, "seed": 0})
    # serialize=False: skip serialization round-trip (we test that separately)
    # verbose=False: suppress C++ stdout noise in pytest output
    pyspiel.random_sim_test(game, num_sims=3, serialize=False, verbose=False)


# ---------------------------------------------------------------------------
# Manual rollout harness (seed-deterministic, validates core invariants)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("num_players", [2, 3, 4, 6, 8])
@pytest.mark.parametrize("seed", [0, 1, 42])
def test_random_simulations_pass(num_players: int, seed: int) -> None:
    """Roll out random episodes and validate basic invariants.

    Checks:
    - legal_actions non-empty on every non-terminal step
    - game terminates within 5 000 steps
    - returns length matches num_players and contains no NaN
    """
    game = pyspiel.load_game("skyjo", {"num_players": num_players, "seed": seed})
    rng = random.Random(seed)

    for _episode in range(3):
        state = game.new_initial_state()
        steps = 0
        while not state.is_terminal():
            if state.is_chance_node():
                outcomes = state.chance_outcomes()
                values = [o for o, _ in outcomes]
                weights = [p for _, p in outcomes]
                action = rng.choices(values, weights=weights, k=1)[0]
            else:
                legal = state.legal_actions()
                assert legal, "no legal actions but state not terminal"
                action = rng.choice(legal)
            state.apply_action(action)
            steps += 1
            assert steps < 5_000, "round did not terminate within 5 000 steps"

        rs = state.returns()
        assert len(rs) == num_players
        assert all(isinstance(x, float) and x == x for x in rs), "NaN in returns"
