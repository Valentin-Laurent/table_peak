from __future__ import annotations

from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor
from table_peak.games.quoridor.walls import edge_blocked, is_wall_legal, path_exists


def test_horizontal_wall_blocks_vertical_step() -> None:
    horizontal = frozenset({WallAnchor(col=3, row=0)})
    assert edge_blocked(
        Cell(col=4, row=0),
        Cell(col=4, row=1),
        horizontal_walls=horizontal,
        vertical_walls=frozenset(),
    )


def test_crossing_wall_is_illegal() -> None:
    assert not is_wall_legal(
        anchor=WallAnchor(col=2, row=2),
        orientation=Orientation.HORIZONTAL,
        walls_remaining=10,
        pawns=(Cell(col=4, row=0), Cell(col=4, row=8)),
        horizontal_walls=frozenset(),
        vertical_walls=frozenset({WallAnchor(col=2, row=2)}),
    )


def test_path_exists_detects_fully_trapped_start_in_artificial_wall_layout() -> None:
    horizontal = frozenset({WallAnchor(col=3, row=0)})
    vertical = frozenset({WallAnchor(col=3, row=0), WallAnchor(col=4, row=0)})
    assert not path_exists(
        start=Cell(col=4, row=0),
        goal_row=8,
        horizontal_walls=horizontal,
        vertical_walls=vertical,
    )
