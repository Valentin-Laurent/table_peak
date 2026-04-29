"""Uniformly-random policy. RNG is injected — never uses module-level random."""

from __future__ import annotations

import random

from table_peak.games.base import Action, State


class RandomAgent:
    """Uniform-random over legal actions. Stateless across calls (apart from RNG)."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random()

    def act(self, state: State) -> Action:
        return self._rng.choice(list(state.legal_actions()))
