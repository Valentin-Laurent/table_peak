"""Generic adapter: pyspiel.State -> table_peak.games.base.State Protocol.

Auto-resolves chance nodes using a deterministic seeded RNG. Exposes an immutable
view (apply_action returns a new adapter wrapping a cloned underlying state), so the
home-grown agent layer never sees chance nodes and never mutates a shared state.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.base import Action, PlayerId


class PyspielStateAdapter:
    def __init__(self, inner: pyspiel.State, rng: random.Random):
        # Resolve chance nodes immediately so the agent layer only sees decision nodes.
        while inner.is_chance_node():
            outcomes = inner.chance_outcomes()
            values = [v for v, _ in outcomes]
            weights = [p for _, p in outcomes]
            chosen = rng.choices(values, weights=weights, k=1)[0]
            inner.apply_action(chosen)
        self._inner: pyspiel.State = inner
        self._rng: random.Random = rng

    @property
    def current_player(self) -> PlayerId:
        return int(self._inner.current_player())

    def legal_actions(self) -> Sequence[Action]:
        return list(self._inner.legal_actions())

    def apply_action(self, action: Action) -> PyspielStateAdapter:
        cloned = self._inner.clone()
        cloned.apply_action(action)
        # Derive a child seed deterministically so sibling states don't share RNG state.
        child_seed = self._rng.randrange(2**31)
        return PyspielStateAdapter(cloned, random.Random(child_seed))

    @property
    def is_terminal(self) -> bool:
        return bool(self._inner.is_terminal())

    def returns(self) -> dict[PlayerId, float]:
        rs = self._inner.returns()
        return {p: float(rs[p]) for p in range(len(rs))}


class PyspielGameAdapter:
    def __init__(self, inner: pyspiel.Game, *, seed: int):
        self._inner: pyspiel.Game = inner
        self._seed: int = seed

    @property
    def num_players(self) -> int:
        return int(self._inner.num_players())

    def new_initial_state(self) -> PyspielStateAdapter:
        return PyspielStateAdapter(self._inner.new_initial_state(), random.Random(self._seed))
