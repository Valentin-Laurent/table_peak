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


def test_horizontal_wall_overlapping_collinear_neighbour_is_illegal() -> None:
    # A horizontal wall at (1, 0) spans segments h-1-0 and h-2-0. A horizontal
    # wall one anchor to either side shares a segment, so it overlaps.
    existing = frozenset({WallAnchor(col=1, row=0)})
    pawns = (Cell(col=4, row=0), Cell(col=4, row=8))
    for neighbour in (WallAnchor(col=0, row=0), WallAnchor(col=2, row=0)):
        assert not is_wall_legal(
            anchor=neighbour,
            orientation=Orientation.HORIZONTAL,
            walls_remaining=10,
            pawns=pawns,
            horizontal_walls=existing,
            vertical_walls=frozenset(),
        )


def test_vertical_wall_overlapping_collinear_neighbour_is_illegal() -> None:
    # A vertical wall at (0, 1) spans segments v-0-1 and v-0-2. A vertical wall
    # one anchor above or below shares a segment, so it overlaps.
    existing = frozenset({WallAnchor(col=0, row=1)})
    pawns = (Cell(col=4, row=0), Cell(col=4, row=8))
    for neighbour in (WallAnchor(col=0, row=0), WallAnchor(col=0, row=2)):
        assert not is_wall_legal(
            anchor=neighbour,
            orientation=Orientation.VERTICAL,
            walls_remaining=10,
            pawns=pawns,
            horizontal_walls=frozenset(),
            vertical_walls=existing,
        )


def test_collinear_walls_two_anchors_apart_do_not_overlap() -> None:
    # h-1-0/h-2-0 and h-3-0/h-4-0 share no segment, so both are legal.
    assert is_wall_legal(
        anchor=WallAnchor(col=3, row=0),
        orientation=Orientation.HORIZONTAL,
        walls_remaining=10,
        pawns=(Cell(col=4, row=0), Cell(col=4, row=8)),
        horizontal_walls=frozenset({WallAnchor(col=1, row=0)}),
        vertical_walls=frozenset(),
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
