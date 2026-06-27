"""Render a Quoridor state (PyspielStateAdapter) into a template-friendly view.

Quoridor is perfect-information, so unlike Skyjo there is nothing to mask: the
renderer reads the inner engine state directly (see _read_board). The human plays
from the bottom via a CSS scaleY(-1) flip in the template; engine coordinates are
untouched.

Interaction model:
  - Pawn move = 1 click on a green-tinted legal destination cell -> POST encode_move.
  - Wall = 2 clicks on gutter segments, resolved client-side to one legal
    (anchor, orientation) action -> POST encode_wall (see Task 2 / legal_walls_json).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from table_peak.agents.base import Agent
from table_peak.games._pyspiel_adapter import PyspielStateAdapter
from table_peak.games.base import PlayerId
from table_peak.games.quoridor import actions as q
from table_peak.games.quoridor.geometry import BOARD_SIZE, Cell, Orientation, WallAnchor

PARTIAL = "_quoridor_board.html"
TITLE = "Quoridor"


@dataclass(frozen=True, slots=True)
class QuoridorCell:
    col: int
    row: int
    pawn: int | None  # seat occupying this cell, or None
    is_move_target: bool  # legal pawn destination -> green tint + clickable
    move_action: int  # encode_move id when is_move_target, else -1


@dataclass(frozen=True, slots=True)
class BoardData:
    """Plain projection of the inner engine state (no hidden info to mask)."""

    pawns: dict[int, Cell]
    walls_remaining: dict[int, int]
    horizontal_walls: frozenset[WallAnchor]
    vertical_walls: frozenset[WallAnchor]


@dataclass(frozen=True, slots=True)
class QuoridorBoardView:
    partial: str
    title: str
    game_id: str
    status: str
    is_terminal: bool
    cells: tuple[QuoridorCell, ...]  # row-major, 81 cells
    cells_clickable: bool
    walls_p0: int
    walls_p1: int
    # Wall fields are populated in Task 2; default to empty so Task 1 stays self-contained.
    placed_segs: frozenset[str] = frozenset()
    placed_gaps: frozenset[str] = frozenset()
    candidate_segs: frozenset[str] = frozenset()
    legal_walls_json: str = "[]"


def _read_board(inner: Any) -> BoardData:
    """Read board structure off the inner QuoridorState.

    Reaches single-underscore attributes by design: Quoridor is perfect-info, so
    the renderer needs no masking and the engine exposes no public accessor. This
    is the only place that couples to engine internals.
    """
    return BoardData(
        pawns=dict(inner._pawn_positions),
        walls_remaining=dict(inner._walls_remaining),
        horizontal_walls=inner._horizontal_walls,
        vertical_walls=inner._vertical_walls,
    )


def _status(state: Any, board: BoardData, seat: int) -> str:
    if state.is_terminal:
        returns = state.returns()
        winner = next((pid for pid, r in returns.items() if r > 0), None)
        if winner is None:
            return "Game over — draw"
        return f"Game over — Player {winner + 1} won"
    walls = board.walls_remaining[seat]
    return f"Your turn — Player {seat + 1} ({walls} walls left)"


def _wall_segments(anchor: WallAnchor, orientation: Orientation) -> tuple[str, str]:
    """The two unit gutter segments a wall occupies (see module/plan geometry)."""
    if orientation is Orientation.HORIZONTAL:
        return f"h-{anchor.col}-{anchor.row}", f"h-{anchor.col + 1}-{anchor.row}"
    return f"v-{anchor.col}-{anchor.row}", f"v-{anchor.col}-{anchor.row + 1}"


def _placed(board: BoardData) -> tuple[frozenset[str], frozenset[str]]:
    """Segment ids and intersection-gap ids for every already-placed wall."""
    segs: set[str] = set()
    gaps: set[str] = set()
    for anchor in board.horizontal_walls:
        segs.update(_wall_segments(anchor, Orientation.HORIZONTAL))
        gaps.add(f"g-{anchor.col}-{anchor.row}")
    for anchor in board.vertical_walls:
        segs.update(_wall_segments(anchor, Orientation.VERTICAL))
        gaps.add(f"g-{anchor.col}-{anchor.row}")
    return frozenset(segs), frozenset(gaps)


def _legal_walls(state: Any) -> tuple[list[dict[str, Any]], frozenset[str]]:
    """Legal-wall payload (for client JS) and the union of candidate segment ids."""
    walls: list[dict[str, Any]] = []
    candidates: set[str] = set()
    for action in state.legal_actions():
        decoded = q.decode(action)
        if decoded.kind != "wall":
            continue
        assert decoded.anchor is not None and decoded.orientation is not None
        seg_a, seg_b = _wall_segments(decoded.anchor, decoded.orientation)
        walls.append(
            {
                "action": action,
                "orientation": decoded.orientation.value,
                "seg_a": seg_a,
                "seg_b": seg_b,
            }
        )
        candidates.update((seg_a, seg_b))
    return walls, frozenset(candidates)


def render(
    state: Any,
    agents: dict[PlayerId, Agent | None],
    game_id: str,
) -> QuoridorBoardView:
    assert isinstance(state, PyspielStateAdapter)
    board = _read_board(state.inner)

    pawn_at: dict[tuple[int, int], int] = {
        (c.col, c.row): seat for seat, c in board.pawns.items()
    }

    seat = state.current_player
    clickable = (not state.is_terminal) and agents[seat] is None

    placed_segs, placed_gaps = _placed(board)
    if clickable:
        legal_walls_list, candidate_segs = _legal_walls(state)
    else:
        legal_walls_list, candidate_segs = [], frozenset()

    move_targets: dict[tuple[int, int], int] = {}
    if clickable:
        for action in state.legal_actions():
            decoded = q.decode(action)
            if decoded.kind == "move":
                assert decoded.destination is not None
                move_targets[(decoded.destination.col, decoded.destination.row)] = action

    cells: list[QuoridorCell] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            is_target = (col, row) in move_targets
            cells.append(
                QuoridorCell(
                    col=col,
                    row=row,
                    pawn=pawn_at.get((col, row)),
                    is_move_target=is_target,
                    move_action=move_targets.get((col, row), -1),
                )
            )

    return QuoridorBoardView(
        partial=PARTIAL,
        title=TITLE,
        game_id=game_id,
        status=_status(state, board, seat),
        is_terminal=state.is_terminal,
        cells=tuple(cells),
        cells_clickable=clickable,
        walls_p0=board.walls_remaining[0],
        walls_p1=board.walls_remaining[1],
        placed_segs=placed_segs,
        placed_gaps=placed_gaps,
        candidate_segs=candidate_segs,
        legal_walls_json=json.dumps(legal_walls_list),
    )
