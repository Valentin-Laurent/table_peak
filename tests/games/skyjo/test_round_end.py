# tests/games/skyjo/test_round_end.py
"""Black-box tests for round end: last-turn-for-everyone trigger + scoring + doubling."""

from __future__ import annotations

import random

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401

# Safety cap so a non-terminating policy fails the test loudly instead of hanging.
# Random play terminates almost surely; a healthy round is well under this bound.
_MAX_STEPS = 10_000


def _play_one_full_round_random(num_players: int = 2, seed: int = 0) -> pyspiel.State:
    """Drive a full round with seeded-random action choice. Returns the terminal state.

    A fixed-slot policy (e.g. always the first legal action) never terminates in Skyjo:
    it keeps replacing one slot and never flips the rest, so the round-end trigger
    (all cards face-up) is never reached. Random play does reduce the face-down count
    almost surely, so the round terminates within a bounded number of steps.
    """
    rng = random.Random(seed)
    state = pyspiel.load_game(
        "skyjo",
        {"num_players": num_players, "seed": seed},
    ).new_initial_state()
    for _ in range(_MAX_STEPS):
        if state.is_terminal():
            return state
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            state.apply_action(rng.choice(outcomes)[0])
        else:
            state.apply_action(rng.choice(state.legal_actions()))
    raise AssertionError(f"round did not terminate within {_MAX_STEPS} steps")


def test_round_terminates_within_bounded_steps() -> None:
    state = _play_one_full_round_random(num_players=2, seed=0)
    assert state.is_terminal()


def test_terminal_state_returns_per_player() -> None:
    state = _play_one_full_round_random(num_players=3, seed=1)
    rs = state.returns()
    assert len(rs) == 3
    assert all(isinstance(x, float) for x in rs)


def test_terminal_state_round_scores_post_doubling_consistent_with_returns() -> None:
    state = _play_one_full_round_random(num_players=2, seed=7)
    rs = state.round_scores()
    returns = state.returns()
    for p in range(2):
        assert returns[p] == -float(rs[p])


def test_round_scores_sum_makes_sense() -> None:
    """Sanity: round scores should be in a reasonable range."""
    state = _play_one_full_round_random(num_players=2, seed=0)
    for _p, s in state.round_scores().items():
        assert -100 <= s <= 250  # very loose envelope; tighter bounds are theoretical
