"""Black-box tests for Skyjo observer: information privacy + tensor shape."""

from __future__ import annotations

import re

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import encode_draw_deck, encode_reveal_initial


def _new_game(num_players: int = 2, seed: int = 0) -> pyspiel.Game:
    return pyspiel.load_game("skyjo", {"num_players": num_players, "seed": seed})


def _advance_to_main_play(num_players: int = 2, seed: int = 0) -> pyspiel.State:
    state = _new_game(num_players, seed).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(num_players):
        state.apply_action(encode_reveal_initial(0, 1))
    return state


def test_observer_hides_opponents_face_down_values() -> None:
    state = _advance_to_main_play(num_players=2, seed=0)
    info_p0 = state.information_state_string(0)
    info_p1 = state.information_state_string(1)
    # After the initial reveal each player has 10 face-down slots, shown as "?".
    assert info_p0.count("?") >= 10
    assert info_p1.count("?") >= 10


def test_observer_exposes_face_up_values_publicly() -> None:
    state = _advance_to_main_play(num_players=2, seed=0)
    info_p0 = state.information_state_string(0)
    info_p1 = state.information_state_string(1)
    assert len(re.findall(r"-?\d+", info_p0)) > 0
    assert len(re.findall(r"-?\d+", info_p1)) > 0


def test_information_state_tensor_shape_is_fixed_per_num_players() -> None:
    game = _new_game(num_players=3)
    state = game.new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(3):
        state.apply_action(encode_reveal_initial(0, 1))
    tensor = state.information_state_tensor(0)
    assert len(tensor) > 0
    expected_size = 1
    for d in game.information_state_tensor_shape():
        expected_size *= d
    assert len(tensor) == expected_size


def test_observer_during_branch_b_includes_drawn_card_for_active_player_only() -> None:
    state = _advance_to_main_play(num_players=2, seed=0)
    active = state.current_player()
    other = 1 - active
    state.apply_action(encode_draw_deck())
    state.apply_action(state.chance_outcomes()[0][0])  # resolve draw chance
    info_active = state.information_state_string(active)
    info_other = state.information_state_string(other)
    assert "drawn=" in info_active.lower()
    # The other player must not see the concrete drawn value (only the masked "drawn=?").
    assert "drawn=?" in info_other or not re.search(r"drawn=-?\d", info_other)
