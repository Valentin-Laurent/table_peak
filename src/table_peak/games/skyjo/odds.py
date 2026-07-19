"""Skyjo draw-probability engine: the distribution over the next deck draw.

Odds are common knowledge — no player (owner included) sees any face-down value —
so this module takes the state only and exposes no per-player / viewer variant.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from table_peak.games.skyjo.deck import DECK_COMPOSITION

if TYPE_CHECKING:
    from table_peak.games.skyjo.state import SkyjoState


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

    def prob_equal(self, value: float) -> float:
        """Probability the drawn value equals `value` exactly (0 outside the support).

        Column-clearing: a Skyjo column of three equal cards is removed and scores
        zero, so when a column already holds two of value v, this is the chance the
        next card is the third v that clears it. A thin selection over the pmf, named
        so the intent is explicit and reusable by the UI and agents. Accepts a float
        (the UI's free-form input): a whole-number float equals its integer card, and
        a .5 boundary equals no card, so its probability is zero.
        """
        return sum(prob for card, prob in self.pmf.items() if card == value)

    def prob_less_than(self, threshold: float) -> float:
        """Probability the drawn value is strictly < threshold.

        Threshold is numeric: card values are integers, but a float threshold is
        well-defined (only the .5 boundaries differ from the nearest integer), so
        the UI's free-form explorer can pass floats. Seeded at a discard top of
        value t, this is exactly 'a deck draw beats taking the t': in Skyjo lower
        is better and a tie does not improve you, so beating t means drawing < t.
        """
        return sum(prob for value, prob in self.pmf.items() if value < threshold)


def _unseen_pool(state: SkyjoState) -> Counter[int]:
    """Multiset of cards the player has not seen: full deck minus every face-up
    grid card minus the entire discard pile. Equals draw pile + face-down grid
    cells. Reads only public information (never a face-down value, never per-value
    draw-pile counts)."""
    pool: Counter[int] = Counter(DECK_COMPOSITION)
    assert state._grids is not None, "draw_odds requires a dealt state"
    for grid in state._grids:
        for value in grid.face_up_values().values():
            pool[value] -= 1
    for value in state._discard_pile:
        pool[value] -= 1
    return pool


def draw_odds(state: SkyjoState) -> DrawOdds:
    """Distribution over the value of the next card drawn from the deck.

    Odds are common knowledge, so no viewer is needed. The next draw is uniform
    over the unseen pool (draw pile + face-down grid cells): a player cannot
    distinguish a draw-pile card from a face-down grid card, so by exchangeability
    the marginal next-draw ranges over the whole pool.

    Recycle boundary: when the draw pile is empty, the next draw instead recycles
    the discard (all but the top card) and draws from it, so the support is the
    known multiset discard[:-1], uniform.
    """
    # The recycle branch returns before _unseen_pool's dealt-state assert; an
    # undealt state with an empty draw pile is unreachable in normal play.
    draw_pile_size = sum(state._remaining_deck_counts.values())
    if draw_pile_size == 0:
        recycled = Counter(state._discard_pile[:-1])
        total = sum(recycled.values())
        if total == 0:
            raise ValueError("no drawable cards: empty draw pile and no recyclable discard")
        pmf = {value: count / total for value, count in recycled.items()}
        return DrawOdds(pmf=pmf)

    pool = _unseen_pool(state)
    total = sum(pool.values())
    pmf = {value: count / total for value, count in pool.items() if count > 0}
    return DrawOdds(pmf=pmf)
