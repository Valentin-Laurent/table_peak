from __future__ import annotations

from table_peak.games.quoridor.geometry import Cell, WallAnchor, cell_on_board
from table_peak.games.quoridor.walls import edge_blocked


def legal_pawn_destinations(
    *,
    player: Cell,
    opponent: Cell,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> tuple[Cell, ...]:
    result: set[Cell] = set()
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        adjacent = Cell(col=player.col + dc, row=player.row + dr)
        if not cell_on_board(adjacent):
            continue
        if edge_blocked(
            player,
            adjacent,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            continue
        if adjacent != opponent:
            result.add(adjacent)
            continue

        straight = Cell(col=opponent.col + dc, row=opponent.row + dr)
        if cell_on_board(straight) and not edge_blocked(
            opponent,
            straight,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            result.add(straight)
            continue

        for ldc, ldr in ((dr, dc), (-dr, -dc)):
            lateral = Cell(col=opponent.col + ldc, row=opponent.row + ldr)
            if cell_on_board(lateral) and not edge_blocked(
                opponent,
                lateral,
                horizontal_walls=horizontal_walls,
                vertical_walls=vertical_walls,
            ):
                result.add(lateral)
    return tuple(sorted(result, key=lambda cell: (cell.row, cell.col)))
