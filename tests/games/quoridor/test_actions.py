from __future__ import annotations

from table_peak.games.quoridor.actions import (
    NUM_DISTINCT_ACTIONS,
    decode,
    encode_move,
    encode_wall,
)
from table_peak.games.quoridor.geometry import BOARD_SIZE, Cell, Orientation, WallAnchor


def test_move_actions_round_trip_through_codec() -> None:
    action = encode_move(Cell(col=4, row=1))
    decoded = decode(action)
    assert decoded.kind == "move"
    assert decoded.destination == Cell(col=4, row=1)
    assert decoded.anchor is None
    assert decoded.orientation is None


def test_wall_actions_round_trip_through_codec() -> None:
    action = encode_wall(WallAnchor(col=3, row=4), Orientation.VERTICAL)
    decoded = decode(action)
    assert decoded.kind == "wall"
    assert decoded.destination is None
    assert decoded.anchor == WallAnchor(col=3, row=4)
    assert decoded.orientation is Orientation.VERTICAL


def test_num_distinct_actions_covers_all_cells_and_wall_anchors() -> None:
    assert BOARD_SIZE == 9
    assert NUM_DISTINCT_ACTIONS == 81 + 64 + 64
