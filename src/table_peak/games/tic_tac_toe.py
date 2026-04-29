"""TicTacToe: 3x3, 2-player, deterministic, perfect-information."""

from __future__ import annotations

from dataclasses import dataclass, field

from table_peak.games.base import Action, PlayerId

_EMPTY: int = -1
_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),  # rows
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),  # cols
    (0, 4, 8),
    (2, 4, 6),  # diagonals
)


@dataclass(frozen=True, slots=True)
class TicTacToeState:
    """Immutable, hashable. Cells: -1 empty, 0 = P0, 1 = P1."""

    board: tuple[int, ...] = field(default=(_EMPTY,) * 9)
    _current_player: PlayerId = 0

    @property
    def current_player(self) -> PlayerId:
        return self._current_player

    def legal_actions(self) -> tuple[Action, ...]:
        return tuple(i for i, v in enumerate(self.board) if v == _EMPTY)

    def apply_action(self, action: Action) -> TicTacToeState:
        if self.is_terminal:
            raise ValueError("Cannot apply action to a terminal state")
        if not 0 <= action < 9 or self.board[action] != _EMPTY:
            raise ValueError(f"Illegal action {action} for board {self.board}")
        new_board = list(self.board)
        new_board[action] = self._current_player
        return TicTacToeState(
            board=tuple(new_board),
            _current_player=1 - self._current_player,
        )

    @property
    def is_terminal(self) -> bool:
        return self._winner() is not None or all(c != _EMPTY for c in self.board)

    def returns(self) -> dict[PlayerId, float]:
        winner = self._winner()
        if winner is None:
            return {0: 0.0, 1: 0.0}
        return {0: 1.0 if winner == 0 else -1.0, 1: 1.0 if winner == 1 else -1.0}

    def _winner(self) -> PlayerId | None:
        for a, b, c in _LINES:
            if self.board[a] != _EMPTY and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None


class TicTacToe:
    """TicTacToe game definition."""

    @property
    def num_players(self) -> int:
        return 2

    def new_initial_state(self) -> TicTacToeState:
        return TicTacToeState()
