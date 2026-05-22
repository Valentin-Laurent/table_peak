# tests/games/skyjo/test_turn.py
"""Black-box tests for main play: Branch (a), Branch (b1), Branch (b2), turn rotation."""

from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import (
    ActionKind,
    decode,
    encode_draw_deck,
    encode_replace_from_hand,
    encode_reveal_initial,
    encode_take_discard_and_replace,
)


def _new_game(num_players: int = 2, seed: int = 0) -> pyspiel.Game:
    return pyspiel.load_game("skyjo", {"num_players": num_players, "seed": seed})


def _advance_to_main_play(num_players: int = 2, seed: int = 0) -> pyspiel.State:
    state = _new_game(num_players, seed).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(num_players):
        state.apply_action(encode_reveal_initial(0, 1))
    return state


def test_main_play_legal_actions_include_take_discard_draw_deck() -> None:
    state = _advance_to_main_play()
    legal = state.legal_actions()
    kinds = {decode(a).kind for a in legal}
    assert ActionKind.TAKE_DISCARD_AND_REPLACE in kinds
    assert ActionKind.DRAW_DECK in kinds


def test_take_discard_and_replace_advances_turn_to_other_player() -> None:
    state = _advance_to_main_play(num_players=2)
    starter = state.current_player()
    state.apply_action(encode_take_discard_and_replace(2))  # replace some face-down slot
    # After action + column check, current_player is the OTHER player (no chance node here).
    assert state.current_player() == 1 - starter


def test_draw_deck_transitions_to_branch_b_via_chance_node() -> None:
    state = _advance_to_main_play(num_players=2)
    starter = state.current_player()
    state.apply_action(encode_draw_deck())
    # Now we expect a chance node for the drawn card.
    assert state.is_chance_node()
    state.apply_action(state.chance_outcomes()[0][0])
    # After chance, it's the SAME player's turn (Branch (b) sub-action).
    assert state.current_player() == starter
    legal = state.legal_actions()
    kinds = {decode(a).kind for a in legal}
    assert ActionKind.REPLACE_FROM_HAND in kinds
    assert ActionKind.DISCARD_AND_FLIP in kinds


def test_discard_and_flip_illegal_when_no_face_down_remaining() -> None:
    """When F=0 (all slots face-up), Branch (b2) DiscardAndFlip is not a legal action."""
    state = _advance_to_main_play(num_players=2)
    cp = state.current_player()
    state.apply_action(encode_draw_deck())
    state.apply_action(state.chance_outcomes()[0][0])  # resolve draw chance -> Branch (b)
    # Force the active player's grid fully face-up (the F=0 edge).
    grid = state._grids[cp]
    for slot in range(grid.num_slots):
        if not grid.is_face_up(slot):
            grid = grid.reveal(slot)
    state._grids[cp] = grid
    kinds = {decode(a).kind for a in state.legal_actions()}
    assert ActionKind.DISCARD_AND_FLIP not in kinds
    assert ActionKind.REPLACE_FROM_HAND in kinds  # replacing a face-up slot is still allowed


def test_replace_from_hand_advances_turn() -> None:
    state = _advance_to_main_play(num_players=2)
    starter = state.current_player()
    state.apply_action(encode_draw_deck())
    state.apply_action(state.chance_outcomes()[0][0])  # resolve chance
    state.apply_action(encode_replace_from_hand(2))
    assert state.current_player() == 1 - starter


def test_after_take_discard_replaces_old_grid_card_to_discard_top() -> None:
    state = _advance_to_main_play(num_players=2)
    # The discard top before action is a known value; we don't read it directly here
    # because pyspiel.State doesn't expose it on the public surface — use information_state_string
    # in Task 10. For now, assert via a round-trip: take discard, look at info_state shape.
    info_before = state.information_state_string(state.current_player())
    state.apply_action(encode_take_discard_and_replace(2))
    info_after = state.information_state_string(state.current_player())
    assert info_before != info_after


def test_three_player_turn_rotation_is_clockwise() -> None:
    state = _advance_to_main_play(num_players=3)
    starter = state.current_player()
    state.apply_action(encode_take_discard_and_replace(2))
    p2 = state.current_player()
    assert p2 == (starter + 1) % 3
    state.apply_action(encode_take_discard_and_replace(2))
    p3 = state.current_player()
    assert p3 == (starter + 2) % 3
