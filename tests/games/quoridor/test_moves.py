from __future__ import annotations

from table_peak.games.quoridor.geometry import Cell, WallAnchor
from table_peak.games.quoridor.moves import legal_pawn_destinations


def test_start_position_has_three_pawn_moves() -> None:
    assert set(
        legal_pawn_destinations(
            player=Cell(col=4, row=0),
            opponent=Cell(col=4, row=8),
            horizontal_walls=frozenset(),
            vertical_walls=frozenset(),
        )
    ) == {Cell(col=3, row=0), Cell(col=5, row=0), Cell(col=4, row=1)}


def test_adjacent_opponent_allows_straight_jump() -> None:
    legal = set(
        legal_pawn_destinations(
            player=Cell(col=4, row=0),
            opponent=Cell(col=4, row=1),
            horizontal_walls=frozenset(),
            vertical_walls=frozenset(),
        )
    )
    assert Cell(col=4, row=2) in legal


def test_blocked_straight_jump_turns_into_lateral_jumps() -> None:
    legal = set(
        legal_pawn_destinations(
            player=Cell(col=4, row=0),
            opponent=Cell(col=4, row=1),
            horizontal_walls=frozenset({WallAnchor(col=3, row=1)}),
            vertical_walls=frozenset(),
        )
    )
    assert Cell(col=4, row=2) not in legal
    assert Cell(col=3, row=1) in legal
    assert Cell(col=5, row=1) in legal
