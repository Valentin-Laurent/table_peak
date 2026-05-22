"""Scenario tests for column elimination on three-of-a-kind.

Driven by seeded-random play (a fixed-slot policy never terminates in Skyjo). We
assert the rules-doc elimination-ordering invariant on every elimination that fires
and require that at least one elimination is actually exercised across the seeds.
"""

from __future__ import annotations

import random

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401

_MAX_STEPS = 10_000


def _play_random_watching_eliminations(num_players: int, seed: int) -> int:
    """Play a full round with seeded-random actions; return the elimination count.

    Asserts that whenever a player's grid loses a column, the top of the discard
    pile holds exactly three copies of one identical value (the eliminated trio).
    """
    rng = random.Random(seed)
    state = pyspiel.load_game(
        "skyjo", {"num_players": num_players, "seed": seed}
    ).new_initial_state()
    eliminations = 0
    prev_columns: list[int] | None = None
    for _ in range(_MAX_STEPS):
        if state.is_terminal():
            break
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            state.apply_action(
                rng.choices([a for a, _ in outcomes], weights=[p for _, p in outcomes], k=1)[0]
            )
            continue
        state.apply_action(rng.choice(state.legal_actions()))
        if state._grids is None:
            continue
        new_columns = [g.num_columns for g in state._grids]
        if prev_columns is not None:
            for before, after in zip(prev_columns, new_columns, strict=True):
                if after < before:
                    eliminations += 1
                    top3 = state._discard_pile[-3:]
                    assert len(top3) == 3
                    assert top3[0] == top3[1] == top3[2]
        prev_columns = new_columns
    assert state.is_terminal()
    return eliminations


def test_column_erase_invariant_holds_and_is_exercised() -> None:
    total = 0
    for seed in range(10):
        total += _play_random_watching_eliminations(num_players=4, seed=seed)
    # The invariant is checked inside the helper on every elimination; here we require
    # that the column-erase path was actually hit at least once across the seeds.
    assert total > 0
