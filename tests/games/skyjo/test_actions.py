"""Black-box tests for action ID encoding/decoding."""

from __future__ import annotations

import pytest

from table_peak.games.skyjo.actions import (
    NUM_DISTINCT_ACTIONS,
    ActionKind,
    decode,
    encode_discard_and_flip,
    encode_draw_deck,
    encode_replace_from_hand,
    encode_reveal_initial,
    encode_take_discard_and_replace,
)


def test_num_distinct_actions_is_103() -> None:
    assert NUM_DISTINCT_ACTIONS == 103


def test_reveal_initial_pairs_are_unordered_and_unique() -> None:
    seen: set[int] = set()
    for i in range(12):
        for j in range(i + 1, 12):
            aid = encode_reveal_initial(i, j)
            assert 0 <= aid < 66
            seen.add(aid)
            # Symmetric: same id whether (i,j) or (j,i) — accept either direction
            assert encode_reveal_initial(j, i) == aid
    assert len(seen) == 66


def test_decode_reveal_initial_recovers_ordered_pair() -> None:
    aid = encode_reveal_initial(2, 7)
    a = decode(aid)
    assert a.kind == ActionKind.REVEAL_INITIAL
    assert {a.slot_a, a.slot_b} == {2, 7}


def test_take_discard_and_replace_range() -> None:
    for slot in range(12):
        aid = encode_take_discard_and_replace(slot)
        assert 66 <= aid < 78
        a = decode(aid)
        assert a.kind == ActionKind.TAKE_DISCARD_AND_REPLACE
        assert a.slot == slot


def test_draw_deck_is_singleton_at_78() -> None:
    aid = encode_draw_deck()
    assert aid == 78
    a = decode(aid)
    assert a.kind == ActionKind.DRAW_DECK


def test_replace_from_hand_range() -> None:
    for slot in range(12):
        aid = encode_replace_from_hand(slot)
        assert 79 <= aid < 91
        a = decode(aid)
        assert a.kind == ActionKind.REPLACE_FROM_HAND
        assert a.slot == slot


def test_discard_and_flip_range() -> None:
    for slot in range(12):
        aid = encode_discard_and_flip(slot)
        assert 91 <= aid < 103
        a = decode(aid)
        assert a.kind == ActionKind.DISCARD_AND_FLIP
        assert a.slot == slot


def test_decode_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        decode(NUM_DISTINCT_ACTIONS)
    with pytest.raises(ValueError):
        decode(-1)


def test_reveal_initial_invalid_pair_raises() -> None:
    with pytest.raises(ValueError):
        encode_reveal_initial(0, 0)  # i must differ from j
    with pytest.raises(ValueError):
        encode_reveal_initial(-1, 5)
    with pytest.raises(ValueError):
        encode_reveal_initial(5, 12)
