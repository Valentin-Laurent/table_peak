"""Black-box tests for the Skyjo player grid: layout, reveals, eliminations."""

from __future__ import annotations

import pytest

from table_peak.games.skyjo.grid import Grid


def test_initial_grid_has_12_face_down_slots() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    assert g.num_slots == 12
    assert g.num_face_down == 12
    assert g.num_face_up == 0
    assert g.num_columns == 4


def test_reveal_marks_face_up() -> None:
    g = Grid.from_dealt(values=[5, 4, 3, 2, 1, 0, -1, -2, 6, 7, 8, 9])
    g2 = g.reveal(slot=0)
    assert g2.is_face_up(slot=0)
    assert g2.value(slot=0) == 5
    assert g2.num_face_down == 11
    assert not g.is_face_up(slot=0)  # original immutable


def test_replace_face_down_reveals_new_value_and_returns_old() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    g2, replaced_value = g.replace(slot=3, new_value=9)
    assert g2.is_face_up(slot=3)
    assert g2.value(slot=3) == 9
    assert replaced_value == 5  # the dealt card came up


def test_replace_face_up_returns_old_face_up_value() -> None:
    g = Grid.from_dealt(values=list(range(12)))
    g = g.reveal(0)
    g2, replaced_value = g.replace(slot=0, new_value=99)
    assert replaced_value == 0
    assert g2.value(slot=0) == 99


def test_three_face_up_identical_in_column_eliminates_column() -> None:
    g = Grid.from_dealt(values=[7, 0, 0, 0, 7, 0, 0, 0, 7, 0, 0, 0])
    # Layout: slot = row * 4 + col, with row in {0,1,2}, col in {0,1,2,3}.
    # column 0 -> slots 0, 4, 8.
    g = g.reveal(0).reveal(4).reveal(8)
    g2, eliminated = g.try_eliminate_columns()
    # Return shape: list of (column_index, common_value) pairs so callers can route
    # the trio values to the discard pile per the rules-doc's elimination-ordering rule.
    assert eliminated == [(0, 7)]
    assert g2.num_columns == 3
    assert g2.num_slots == 9
    # The remaining slots are re-indexed 0..8 in the same row-major order over surviving columns.
    # Validate face-up/down preservation for surviving slots.
    assert g2.num_face_up == 0  # only 3 reveals existed, all eliminated


def test_eliminate_does_not_fire_on_two_of_three_identical() -> None:
    g = Grid.from_dealt(values=[7, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0, 0])
    g = g.reveal(0).reveal(8)  # only two of three
    g2, eliminated = g.try_eliminate_columns()
    assert eliminated == []
    assert g2.num_columns == 4


def test_multiple_simultaneous_eliminations() -> None:
    # All four columns are 5,5,5 face-up.
    g = Grid.from_dealt(values=[5] * 12)
    for s in range(12):
        g = g.reveal(s)
    g2, eliminated = g.try_eliminate_columns()
    assert sorted(eliminated) == [(0, 5), (1, 5), (2, 5), (3, 5)]
    assert g2.num_slots == 0


def test_after_elimination_round_end_predicate_uses_face_down_count_not_grid_size() -> None:
    # All columns eliminated -> face_down=0 even though num_slots=0.
    g = Grid.from_dealt(values=[5] * 12)
    for s in range(12):
        g = g.reveal(s)
    g, _ = g.try_eliminate_columns()
    assert g.num_face_down == 0


def test_face_down_slots_are_invalid_for_value_lookup() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    with pytest.raises(ValueError):
        g.value(slot=0)  # face-down -> hidden, no value access


def test_reveal_face_up_slot_raises() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    g = g.reveal(0)
    with pytest.raises(ValueError):
        g.reveal(0)


def test_reveal_invalid_slot_raises() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    with pytest.raises(ValueError):
        g.reveal(99)


def test_face_down_slots_helper_returns_correct_indices() -> None:
    g = Grid.from_dealt(values=list(range(12)))
    g = g.reveal(0).reveal(5)
    assert sorted(g.face_down_slots()) == [1, 2, 3, 4, 6, 7, 8, 9, 10, 11]


def test_face_up_values_helper() -> None:
    g = Grid.from_dealt(values=list(range(12)))
    g = g.reveal(2).reveal(7)
    assert g.face_up_values() == {2: 2, 7: 7}
