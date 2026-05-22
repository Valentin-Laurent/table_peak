"""Black-box tests for the Skyjo deck composition and shuffle determinism."""

from __future__ import annotations

import random
from collections import Counter

from table_peak.games.skyjo.deck import DECK_COMPOSITION, build_shuffled_deck, deal


def test_deck_composition_totals_150_cards() -> None:
    assert sum(DECK_COMPOSITION.values()) == 150


def test_deck_composition_matches_published_rules() -> None:
    assert DECK_COMPOSITION[-2] == 5
    assert DECK_COMPOSITION[-1] == 10
    assert DECK_COMPOSITION[0] == 15
    for v in range(1, 13):
        assert DECK_COMPOSITION[v] == 10
    assert set(DECK_COMPOSITION.keys()) == set(range(-2, 13))


def test_build_shuffled_deck_returns_150_cards_with_correct_multiset() -> None:
    deck = build_shuffled_deck(rng=random.Random(0))
    assert len(deck) == 150
    assert Counter(deck) == Counter(DECK_COMPOSITION)


def test_build_shuffled_deck_is_deterministic_under_fixed_seed() -> None:
    a = build_shuffled_deck(rng=random.Random(42))
    b = build_shuffled_deck(rng=random.Random(42))
    assert a == b


def test_build_shuffled_deck_differs_under_different_seeds() -> None:
    a = build_shuffled_deck(rng=random.Random(1))
    b = build_shuffled_deck(rng=random.Random(2))
    assert a != b


def test_deal_returns_per_player_grids_and_remaining_deck() -> None:
    deck = list(range(150))  # synthetic deck for traceability
    grids, remaining = deal(deck, num_players=4, cards_per_grid=12)
    assert len(grids) == 4
    assert all(len(g) == 12 for g in grids)
    assert len(remaining) == 150 - 48
    # cards are dealt in order, no overlap
    flat = [c for g in grids for c in g] + remaining
    assert flat == list(range(150))


def test_deal_raises_when_deck_too_small() -> None:
    import pytest

    deck = list(range(10))
    with pytest.raises(ValueError):
        deal(deck, num_players=2, cards_per_grid=12)
