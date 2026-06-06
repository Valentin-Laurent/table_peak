"""Tests for build_public_view: structure + the Skyjo privacy model."""

from __future__ import annotations

import random
from typing import Any

from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.games.skyjo.view import build_public_view


def _in_setup(state: Any) -> bool:
    legal = list(state.legal_actions())
    return bool(legal) and all(sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal)


def _play_to_main(num_players: int, seed: int) -> Any:
    """Create a game and apply random reveals until setup is over."""
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def test_after_setup_each_player_has_two_face_up_and_hidden_values_are_none() -> None:
    state = _play_to_main(num_players=3, seed=11)
    pv = build_public_view(state.inner, viewer=0)
    assert pv.phase == "main_play"
    assert pv.num_players == 3
    for player in pv.players:
        face_up = [c for c in player.cells if c.face_up]
        face_down = [c for c in player.cells if not c.face_up]
        assert len(face_up) == 2
        assert all(c.value is not None for c in face_up)
        # Hidden cards never carry a value — for any seat, owner included.
        assert all(c.value is None for c in face_down)
    assert pv.discard_top is not None
    assert pv.draw_pile_size > 0


def test_drawn_card_visible_only_to_the_drawer() -> None:
    state = _play_to_main(num_players=2, seed=5)
    # Advance to a turn owned by seat 0, then draw from the deck.
    rng = random.Random(5)
    while not state.is_terminal and build_public_view(state.inner, 0).current_player != 0:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    state = state.apply_action(sk.encode_draw_deck())
    drawer_view = build_public_view(state.inner, viewer=0)
    other_view = build_public_view(state.inner, viewer=1)
    assert drawer_view.phase == "branch_b_subaction"
    assert drawer_view.drawn_card is not None
    assert other_view.drawn_card is None


def test_terminal_view_reveals_all_and_matches_round_scores() -> None:
    rng = random.Random(99)
    state = SkyjoGameWrapper(num_players=2, seed=99).new_initial_state()
    while not state.is_terminal:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    pv = build_public_view(state.inner, viewer=0)
    assert pv.is_terminal is True
    assert pv.scores == state.inner.round_scores()
    for player in pv.players:
        assert all(c.face_up for c in player.cells)
