"""Skyjo draw-probability engine: the distribution over the next deck draw.

Odds are common knowledge — no player (owner included) sees any face-down value —
so this module takes the state only and exposes no per-player / viewer variant.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrawOdds:
    """Distribution over the value of the next card drawn from the deck.

    `pmf` maps each possible card value (a subset of -2..12) to its probability;
    keys with zero probability are omitted. All query methods are pure functions
    of `pmf` and never touch game state, so they cannot drift from the distribution.
    """

    pmf: Mapping[int, float]

    def expected_value(self) -> float:
        """Probability-weighted mean of the drawn card value."""
        return sum(value * prob for value, prob in self.pmf.items())

    def prob_at_most(self, threshold: int) -> float:
        """Probability the drawn value is <= threshold (inclusive).

        'Beats a discard top of value t' means drawing strictly less than t, i.e.
        callers use prob_at_most(t - 1).
        """
        return sum(prob for value, prob in self.pmf.items() if value <= threshold)
