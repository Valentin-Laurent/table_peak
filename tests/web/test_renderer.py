"""Tests for the TTT board renderer (state -> BoardView)."""

from __future__ import annotations

from table_peak.agents.base import Agent
from table_peak.agents.minimax import MinimaxAgent
from table_peak.games.base import PlayerId
from table_peak.games.tic_tac_toe import TicTacToe, TicTacToeState
from table_peak.web.renderers.tic_tac_toe import render


def _state_from_moves(moves: list[int]) -> TicTacToeState:
    state = TicTacToe().new_initial_state()
    for m in moves:
        state = state.apply_action(m)
    return state


def test_initial_state_renders_empty_cells_and_x_to_move() -> None:
    state = TicTacToe().new_initial_state()
    agents: dict[PlayerId, Agent | None] = {0: None, 1: MinimaxAgent()}
    view = render(state, agents=agents, game_id="abc")
    assert view.cells == ("", "", "", "", "", "", "", "", "")
    assert view.is_terminal is False
    assert view.status == "Your turn (X)"
    assert view.cells_clickable is True
    assert view.game_id == "abc"


def test_after_one_move_o_to_play() -> None:
    state = _state_from_moves([4])
    agents: dict[PlayerId, Agent | None] = {0: MinimaxAgent(), 1: None}
    view = render(state, agents=agents, game_id="g")
    assert view.cells[4] == "X"
    assert view.status == "Your turn (O)"
    assert view.cells_clickable is True


def test_x_wins_terminal_status() -> None:
    # P0 (X) wins top row.
    state = _state_from_moves([0, 3, 1, 4, 2])
    agents: dict[PlayerId, Agent | None] = {0: None, 1: MinimaxAgent()}
    view = render(state, agents=agents, game_id="g")
    assert view.is_terminal is True
    assert view.status == "Game over — X won"
    assert view.cells_clickable is False


def test_o_wins_terminal_status() -> None:
    # P1 (O) wins diagonal 0-4-8.
    state = _state_from_moves([1, 0, 2, 4, 5, 8])
    agents: dict[PlayerId, Agent | None] = {0: None, 1: MinimaxAgent()}
    view = render(state, agents=agents, game_id="g")
    assert view.is_terminal is True
    assert view.status == "Game over — O won"


def test_draw_terminal_status() -> None:
    state = _state_from_moves([0, 4, 8, 2, 6, 3, 5, 7, 1])
    agents: dict[PlayerId, Agent | None] = {0: None, 1: None}
    view = render(state, agents=agents, game_id="g")
    assert view.is_terminal is True
    assert view.status == "Game over — draw"


def test_cells_not_clickable_when_bot_to_move() -> None:
    """If current player's seat is a bot, cells should not be clickable.

    In the production flow advance_bots prevents this state from being
    rendered, but render() is a pure function and must produce a correct
    view if called directly.
    """
    state = TicTacToe().new_initial_state()
    agents: dict[PlayerId, Agent | None] = {0: MinimaxAgent(), 1: None}
    view = render(state, agents=agents, game_id="g")
    assert view.is_terminal is False
    assert view.cells_clickable is False


def test_cells_use_x_o_and_blank_marks() -> None:
    state = _state_from_moves([0, 4])  # X at 0, O at 4
    agents: dict[PlayerId, Agent | None] = {0: None, 1: None}
    view = render(state, agents=agents, game_id="g")
    assert view.cells[0] == "X"
    assert view.cells[4] == "O"
    assert view.cells[1] == ""
