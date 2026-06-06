"""Render a TicTacToeState into a template-friendly BoardView."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from table_peak.agents.base import Agent
from table_peak.games.base import PlayerId

_MARK: dict[int, str] = {-1: "", 0: "X", 1: "O"}


@dataclass(frozen=True, slots=True)
class BoardView:
    """Everything `_board.html` and `game.html` need to render a TTT board."""

    cells: tuple[str, ...]  # length 9, each "" / "X" / "O"
    is_terminal: bool
    status: str
    cells_clickable: bool
    game_id: str
    partial: str = "_board.html"
    title: str = "Tic-Tac-Toe"


def render(
    state: Any,
    agents: dict[PlayerId, Agent | None],
    game_id: str,
) -> BoardView:
    cells = tuple(_MARK[c] for c in state.board)

    if state.is_terminal:
        returns = state.returns()
        winner: PlayerId | None = next((pid for pid, r in returns.items() if r > 0), None)
        if winner is None:
            status = "Game over — draw"
        else:
            status = f"Game over — {'X' if winner == 0 else 'O'} won"
        clickable = False
    else:
        # advance_bots always runs before render, so on non-terminal pages the
        # current player is human.
        seat = state.current_player
        status = f"Your turn ({'X' if seat == 0 else 'O'})"
        clickable = agents[seat] is None

    return BoardView(
        cells=cells,
        is_terminal=state.is_terminal,
        status=status,
        cells_clickable=clickable,
        game_id=game_id,
    )
