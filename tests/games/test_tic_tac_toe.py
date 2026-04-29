"""Black-box behavioural tests for TicTacToe."""

from __future__ import annotations

import pytest

from table_peak.games.tic_tac_toe import TicTacToe


def test_initial_state_has_nine_legal_actions() -> None:
    state = TicTacToe().new_initial_state()
    assert state.current_player == 0
    assert sorted(state.legal_actions()) == list(range(9))
    assert not state.is_terminal


def test_apply_action_advances_current_player() -> None:
    state = TicTacToe().new_initial_state().apply_action(0)
    assert state.current_player == 1
    assert 0 not in state.legal_actions()


def test_apply_action_returns_new_state_not_mutated() -> None:
    state0 = TicTacToe().new_initial_state()
    state1 = state0.apply_action(4)
    # state0 is unchanged
    assert state0.current_player == 0
    assert sorted(state0.legal_actions()) == list(range(9))
    # state1 reflects the move
    assert state1.current_player == 1
    assert 4 not in state1.legal_actions()


def test_illegal_action_raises() -> None:
    state = TicTacToe().new_initial_state().apply_action(0)
    with pytest.raises(ValueError):
        state.apply_action(0)  # occupied cell
    with pytest.raises(ValueError):
        state.apply_action(9)  # out of range


def test_apply_action_on_terminal_raises() -> None:
    # P0 wins top row; applying any action after must raise
    state = TicTacToe().new_initial_state()
    for action in [0, 3, 1, 4, 2]:
        state = state.apply_action(action)
    assert state.is_terminal
    with pytest.raises(ValueError):
        state.apply_action(5)  # an otherwise empty cell


def test_p0_wins_top_row() -> None:
    # P0: 0, P1: 3, P0: 1, P1: 4, P0: 2 -> top row for P0
    state = TicTacToe().new_initial_state()
    for action in [0, 3, 1, 4, 2]:
        state = state.apply_action(action)
    assert state.is_terminal
    assert state.returns() == {0: 1.0, 1: -1.0}


def test_p1_wins_diagonal() -> None:
    # P0: 1, P1: 0, P0: 2, P1: 4, P0: 5, P1: 8 -> diagonal 0-4-8 for P1
    state = TicTacToe().new_initial_state()
    for action in [1, 0, 2, 4, 5, 8]:
        state = state.apply_action(action)
    assert state.is_terminal
    assert state.returns() == {0: -1.0, 1: 1.0}


def test_full_board_draw() -> None:
    # X O X / X O O / O X X  -> no winner, board full
    moves = [0, 1, 2, 4, 3, 5, 7, 6, 8]
    state = TicTacToe().new_initial_state()
    for action in moves:
        state = state.apply_action(action)
    assert state.is_terminal
    assert state.returns() == {0: 0.0, 1: 0.0}


def test_state_is_hashable_and_value_equal() -> None:
    a = TicTacToe().new_initial_state().apply_action(4)
    b = TicTacToe().new_initial_state().apply_action(4)
    assert a == b
    assert hash(a) == hash(b)
    # Different moves -> different state
    c = TicTacToe().new_initial_state().apply_action(0)
    assert a != c


def test_game_meta() -> None:
    game = TicTacToe()
    assert game.num_players == 2
