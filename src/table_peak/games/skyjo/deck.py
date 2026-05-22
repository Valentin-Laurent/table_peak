"""Skyjo 150-card deck composition and dealing helpers."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from types import MappingProxyType

DECK_COMPOSITION: Mapping[int, int] = MappingProxyType(
    {-2: 5, -1: 10, 0: 15, **{v: 10 for v in range(1, 13)}}
)
"""Card value -> number of copies. Sums to 150."""


def build_shuffled_deck(*, rng: random.Random) -> list[int]:
    """Return a fresh shuffled deck of 150 ints in [-2, 12]. Deterministic given rng."""
    deck = [v for v, n in DECK_COMPOSITION.items() for _ in range(n)]
    rng.shuffle(deck)
    return deck


def deal(
    deck: Sequence[int], *, num_players: int, cards_per_grid: int = 12
) -> tuple[list[list[int]], list[int]]:
    """Deal `cards_per_grid` cards to each of `num_players` players, return remaining deck.

    Raises ValueError if the deck has fewer than num_players * cards_per_grid cards.
    """
    needed = num_players * cards_per_grid
    if len(deck) < needed:
        raise ValueError(f"deck has {len(deck)} cards, need {needed}")
    deck_list = list(deck)
    grids = [deck_list[i * cards_per_grid : (i + 1) * cards_per_grid] for i in range(num_players)]
    remaining = deck_list[needed:]
    return grids, remaining
