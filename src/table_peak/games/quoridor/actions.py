from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from table_peak.games.quoridor.geometry import BOARD_SIZE, Cell, Orientation, WallAnchor

MOVE_OFFSET = 0
HORIZONTAL_WALL_OFFSET = BOARD_SIZE * BOARD_SIZE
VERTICAL_WALL_OFFSET = HORIZONTAL_WALL_OFFSET + 64
NUM_DISTINCT_ACTIONS = VERTICAL_WALL_OFFSET + 64


@dataclass(frozen=True, slots=True)
class DecodedAction:
    kind: Literal["move", "wall"]
    destination: Cell | None = None
    anchor: WallAnchor | None = None
    orientation: Orientation | None = None


def encode_move(cell: Cell) -> int:
    return MOVE_OFFSET + cell.row * BOARD_SIZE + cell.col


def encode_wall(anchor: WallAnchor, orientation: Orientation) -> int:
    index = anchor.row * 8 + anchor.col
    if orientation is Orientation.HORIZONTAL:
        return HORIZONTAL_WALL_OFFSET + index
    return VERTICAL_WALL_OFFSET + index


def decode(action: int) -> DecodedAction:
    if 0 <= action < HORIZONTAL_WALL_OFFSET:
        col = action % BOARD_SIZE
        row = action // BOARD_SIZE
        return DecodedAction(kind="move", destination=Cell(col=col, row=row))
    if HORIZONTAL_WALL_OFFSET <= action < VERTICAL_WALL_OFFSET:
        index = action - HORIZONTAL_WALL_OFFSET
        return DecodedAction(
            kind="wall",
            anchor=WallAnchor(col=index % 8, row=index // 8),
            orientation=Orientation.HORIZONTAL,
        )
    if VERTICAL_WALL_OFFSET <= action < NUM_DISTINCT_ACTIONS:
        index = action - VERTICAL_WALL_OFFSET
        return DecodedAction(
            kind="wall",
            anchor=WallAnchor(col=index % 8, row=index // 8),
            orientation=Orientation.VERTICAL,
        )
    raise ValueError(f"Unknown Quoridor action id: {action}")
