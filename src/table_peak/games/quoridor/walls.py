from __future__ import annotations

from collections import deque

from table_peak.games.quoridor.geometry import (
    GOAL_ROWS,
    Cell,
    Orientation,
    WallAnchor,
    anchor_on_board,
    cell_on_board,
)


def edge_blocked(
    a: Cell,
    b: Cell,
    *,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> bool:
    if a.col == b.col:
        lower_row = min(a.row, b.row)
        return (
            WallAnchor(col=a.col, row=lower_row) in horizontal_walls
            or WallAnchor(col=a.col - 1, row=lower_row) in horizontal_walls
        )
    left_col = min(a.col, b.col)
    return (
        WallAnchor(col=left_col, row=a.row) in vertical_walls
        or WallAnchor(col=left_col, row=a.row - 1) in vertical_walls
    )


def orthogonal_neighbors(
    cell: Cell,
    *,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> tuple[Cell, ...]:
    result: list[Cell] = []
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nxt = Cell(col=cell.col + dc, row=cell.row + dr)
        if cell_on_board(nxt) and not edge_blocked(
            cell,
            nxt,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            result.append(nxt)
    return tuple(result)


def path_exists(
    *,
    start: Cell,
    goal_row: int,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> bool:
    queue: deque[Cell] = deque([start])
    seen = {start}
    while queue:
        cell = queue.popleft()
        if cell.row == goal_row:
            return True
        for nxt in orthogonal_neighbors(
            cell,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def is_wall_legal(
    *,
    anchor: WallAnchor,
    orientation: Orientation,
    walls_remaining: int,
    pawns: tuple[Cell, Cell],
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> bool:
    if walls_remaining <= 0 or not anchor_on_board(anchor):
        return False
    if orientation is Orientation.HORIZONTAL:
        # Reject a cross at this intersection (same-anchor vertical wall) and any
        # collinear horizontal neighbour, which would share a unit segment: a
        # wall at (col, row) spans segments h-col-row and h-(col+1)-row, so
        # (col-1, row) and (col+1, row) overlap it.
        if (
            anchor in horizontal_walls
            or anchor in vertical_walls
            or WallAnchor(col=anchor.col - 1, row=anchor.row) in horizontal_walls
            or WallAnchor(col=anchor.col + 1, row=anchor.row) in horizontal_walls
        ):
            return False
        trial_horizontal = horizontal_walls | {anchor}
        trial_vertical = vertical_walls
    else:
        # Symmetric: a vertical wall at (col, row) spans v-col-row and
        # v-col-(row+1), so (col, row-1) and (col, row+1) overlap it.
        if (
            anchor in vertical_walls
            or anchor in horizontal_walls
            or WallAnchor(col=anchor.col, row=anchor.row - 1) in vertical_walls
            or WallAnchor(col=anchor.col, row=anchor.row + 1) in vertical_walls
        ):
            return False
        trial_horizontal = horizontal_walls
        trial_vertical = vertical_walls | {anchor}
    return all(
        path_exists(
            start=pawns[player],
            goal_row=GOAL_ROWS[player],
            horizontal_walls=trial_horizontal,
            vertical_walls=trial_vertical,
        )
        for player in (0, 1)
    )
