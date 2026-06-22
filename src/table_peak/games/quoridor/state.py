from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.quoridor.actions import decode, encode_move, encode_wall
from table_peak.games.quoridor.geometry import GOAL_ROWS, START_CELLS, Orientation, WallAnchor
from table_peak.games.quoridor.moves import legal_pawn_destinations
from table_peak.games.quoridor.walls import is_wall_legal


class QuoridorState(pyspiel.State):  # type: ignore[misc]
    def __init__(self, game: pyspiel.Game, seed: int):
        super().__init__(game)
        self._seed = seed
        self._current_player_index = 0
        self._pawn_positions = {0: START_CELLS[0], 1: START_CELLS[1]}
        self._walls_remaining = {0: 10, 1: 10}
        self._horizontal_walls: frozenset[WallAnchor] = frozenset()
        self._vertical_walls: frozenset[WallAnchor] = frozenset()
        self._winner: int | None = None

    def current_player(self) -> int:
        if self._winner is not None:
            return int(pyspiel.PlayerId.TERMINAL)
        return self._current_player_index

    def is_terminal(self) -> bool:
        return self._winner is not None

    def _legal_actions(self, player: int = -1) -> list[int]:
        if self.is_terminal():
            return []
        me = self._current_player_index
        other = 1 - me
        moves = [
            encode_move(cell)
            for cell in legal_pawn_destinations(
                player=self._pawn_positions[me],
                opponent=self._pawn_positions[other],
                horizontal_walls=self._horizontal_walls,
                vertical_walls=self._vertical_walls,
            )
        ]
        walls: list[int] = []
        for row in range(8):
            for col in range(8):
                anchor = WallAnchor(col=col, row=row)
                for orientation in (Orientation.HORIZONTAL, Orientation.VERTICAL):
                    if is_wall_legal(
                        anchor=anchor,
                        orientation=orientation,
                        walls_remaining=self._walls_remaining[me],
                        pawns=(self._pawn_positions[0], self._pawn_positions[1]),
                        horizontal_walls=self._horizontal_walls,
                        vertical_walls=self._vertical_walls,
                    ):
                        walls.append(encode_wall(anchor, orientation))
        return sorted(moves + walls)

    def _is_legal(self, action: int) -> bool:
        """Check legality of a single action without enumerating all of them.

        Equivalent to `action in self._legal_actions()` but ~256x cheaper: it
        runs at most the path-condition BFS for the one wall being placed,
        instead of for every wall anchor on the board. This matters because the
        adapter clones (history-replay) on every move, so each replayed action
        is validated here -- enumerating all legal actions per replay step made
        clone O(n^2) over the game length.
        """
        if self.is_terminal():
            return False
        decoded = decode(action)
        me = self._current_player_index
        other = 1 - me
        if decoded.kind == "move":
            return decoded.destination in legal_pawn_destinations(
                player=self._pawn_positions[me],
                opponent=self._pawn_positions[other],
                horizontal_walls=self._horizontal_walls,
                vertical_walls=self._vertical_walls,
            )
        assert decoded.anchor is not None
        assert decoded.orientation is not None
        return is_wall_legal(
            anchor=decoded.anchor,
            orientation=decoded.orientation,
            walls_remaining=self._walls_remaining[me],
            pawns=(self._pawn_positions[0], self._pawn_positions[1]),
            horizontal_walls=self._horizontal_walls,
            vertical_walls=self._vertical_walls,
        )

    def _apply_action(self, action: int) -> None:
        if not self._is_legal(action):
            raise ValueError(f"Illegal action {action} for player {self._current_player_index}")
        decoded = decode(action)
        if decoded.kind == "move":
            assert decoded.destination is not None
            self._pawn_positions[self._current_player_index] = decoded.destination
            if decoded.destination.row == GOAL_ROWS[self._current_player_index]:
                self._winner = self._current_player_index
            else:
                self._current_player_index = 1 - self._current_player_index
            return
        assert decoded.anchor is not None
        assert decoded.orientation is not None
        if decoded.orientation is Orientation.HORIZONTAL:
            self._horizontal_walls = self._horizontal_walls | {decoded.anchor}
        else:
            self._vertical_walls = self._vertical_walls | {decoded.anchor}
        self._walls_remaining[self._current_player_index] -= 1
        self._current_player_index = 1 - self._current_player_index

    def _action_to_string(self, player: int, action: int) -> str:
        decoded = decode(action)
        if decoded.kind == "move":
            assert decoded.destination is not None
            return f"MovePawn({decoded.destination.col},{decoded.destination.row})"
        assert decoded.anchor is not None
        assert decoded.orientation is not None
        return f"PlaceWall({decoded.anchor.col},{decoded.anchor.row},{decoded.orientation.value})"

    def returns(self) -> list[float]:
        if self._winner is None:
            return [0.0, 0.0]
        return [1.0, -1.0] if self._winner == 0 else [-1.0, 1.0]

    def clone(self) -> QuoridorState:
        """Deep copy for pyspiel tree expansion.

        copy.deepcopy does NOT work for pybind11-trampoline pyspiel states: the
        C++->Python link is lost, so a later apply_action on the copy mutates a
        throwaway instance rather than the clone (this bit us on Skyjo). We rebuild
        by replaying the action history through the normal apply path, which
        preserves the trampoline linkage. Quoridor is deterministic (no chance
        nodes), so the replay is exact.

        The wrapper layer relies on this: PyspielStateAdapter.apply_action calls
        inner.clone() on every move, so an engine without clone() fails the Task 5
        conformance tests.
        """
        fresh: QuoridorState = self.get_game().new_initial_state()
        for action in self.history():
            fresh.apply_action(action)
        return fresh

    def __str__(self) -> str:
        """God's-eye state string (pyspiel's State::ToString), a required virtual."""
        return (
            f"player={self._current_player_index} "
            f"p0={self._pawn_positions[0].col},{self._pawn_positions[0].row} "
            f"p1={self._pawn_positions[1].col},{self._pawn_positions[1].row} "
            f"walls0={self._walls_remaining[0]} walls1={self._walls_remaining[1]} "
            f"H={sorted((a.col, a.row) for a in self._horizontal_walls)} "
            f"V={sorted((a.col, a.row) for a in self._vertical_walls)}"
        )
