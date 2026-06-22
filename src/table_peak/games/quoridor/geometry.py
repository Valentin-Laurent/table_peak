from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

BOARD_SIZE = 9
WALL_GRID_SIZE = 8


@dataclass(frozen=True, slots=True)
class Cell:
    col: int
    row: int


@dataclass(frozen=True, slots=True)
class WallAnchor:
    col: int
    row: int


class Orientation(StrEnum):
    HORIZONTAL = "h"
    VERTICAL = "v"


START_CELLS = {0: Cell(col=4, row=0), 1: Cell(col=4, row=8)}
GOAL_ROWS = {0: 8, 1: 0}


def cell_on_board(cell: Cell) -> bool:
    return 0 <= cell.col < BOARD_SIZE and 0 <= cell.row < BOARD_SIZE


def anchor_on_board(anchor: WallAnchor) -> bool:
    return 0 <= anchor.col < WALL_GRID_SIZE and 0 <= anchor.row < WALL_GRID_SIZE
