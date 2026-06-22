from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]
import pytest

import table_peak.games.quoridor  # noqa: F401
from table_peak.games.quoridor.actions import encode_move
from table_peak.games.quoridor.geometry import Cell


def test_registered_game_starts_with_player_zero_and_forward_move() -> None:
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    legal = set(state.legal_actions())
    assert state.current_player() == 0
    assert not state.is_terminal()
    assert encode_move(Cell(col=4, row=1)) in legal


def test_illegal_action_raises_value_error() -> None:
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    with pytest.raises(ValueError, match="Illegal action"):
        state.apply_action(encode_move(Cell(col=4, row=8)))


def test_straight_race_to_goal_row_returns_win_for_player_zero() -> None:
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    sequence = [
        Cell(col=4, row=1),
        Cell(col=3, row=8),
        Cell(col=4, row=2),
        Cell(col=4, row=8),
        Cell(col=4, row=3),
        Cell(col=3, row=8),
        Cell(col=4, row=4),
        Cell(col=4, row=8),
        Cell(col=4, row=5),
        Cell(col=3, row=8),
        Cell(col=4, row=6),
        Cell(col=4, row=8),
        Cell(col=4, row=7),
        Cell(col=3, row=8),
        Cell(col=4, row=8),
    ]
    for cell in sequence:
        state.apply_action(encode_move(cell))
    assert state.is_terminal()
    assert state.returns() == [1.0, -1.0]
