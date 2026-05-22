"""Scenario tests for deck recycle when the draw pile runs out."""

from __future__ import annotations

import random

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import encode_draw_deck, encode_reveal_initial

_MAX_STEPS = 20_000


def _advance_to_main_play(num_players: int = 2, seed: int = 0) -> pyspiel.State:
    state = pyspiel.load_game(
        "skyjo", {"num_players": num_players, "seed": seed}
    ).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(num_players):
        state.apply_action(encode_reveal_initial(0, 1))
    return state


def test_draw_deck_recycles_discard_when_draw_pile_empty() -> None:
    """If the draw pile is empty when a player draws, the discard (minus its top) is
    recycled so the draw-chance node has outcomes and play proceeds — rather than
    producing an invalid empty chance node."""
    state = _advance_to_main_play(num_players=2, seed=0)
    # Force the exhaustion edge: empty draw pile, a recyclable discard (3 + top).
    state._remaining_deck_counts.clear()
    state._discard_pile = [5, 6, 7, 8]

    state.apply_action(encode_draw_deck())
    assert state.is_chance_node()
    outcomes = state.chance_outcomes()
    assert len(outcomes) > 0  # recycle replenished the draw pile
    # The top card (8) is preserved; the other three were recycled into the deck.
    assert state._discard_pile == [8]
    # We can resolve the chance and continue into the Branch-(b) sub-action.
    state.apply_action(outcomes[0][0])
    assert state._phase.value == "branch_b_subaction"


def test_long_eight_player_round_runs_to_terminal() -> None:
    """Broad smoke test: a full 8-player random round reaches terminal without error."""
    state = pyspiel.load_game("skyjo", {"num_players": 8, "seed": 0}).new_initial_state()
    rng = random.Random(0)
    for _ in range(_MAX_STEPS):
        if state.is_terminal():
            break
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            state.apply_action(
                rng.choices([a for a, _ in outcomes], weights=[p for _, p in outcomes], k=1)[0]
            )
        else:
            state.apply_action(rng.choice(state.legal_actions()))
    assert state.is_terminal()
