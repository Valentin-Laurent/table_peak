"""Minimax with memoisation. TTT-sized search space; exact solver."""

from __future__ import annotations

import math

from table_peak.games.base import Action, PlayerId, State


class MinimaxAgent:
    """Plays the minimax-optimal action from the perspective of state.current_player.

    Stateless across games apart from the lookup cache, which accelerates repeated
    play. Requires State implementations to be hashable (e.g. frozen dataclasses).
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[State, PlayerId], tuple[float, Action | None]] = {}

    def act(self, state: State) -> Action:
        _, action = self._minimax(state, perspective=state.current_player)
        if action is None:
            raise ValueError("Cannot act on a terminal state")
        return action

    def _minimax(self, state: State, perspective: PlayerId) -> tuple[float, Action | None]:
        key = (state, perspective)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if state.is_terminal:
            result: tuple[float, Action | None] = (state.returns()[perspective], None)
            self._cache[key] = result
            return result

        is_maximising = state.current_player == perspective
        best_score = -math.inf if is_maximising else math.inf
        best_action: Action | None = None

        for action in state.legal_actions():
            child_score, _ = self._minimax(state.apply_action(action), perspective)
            if is_maximising:
                if best_action is None or child_score > best_score:
                    best_score, best_action = child_score, action
            else:
                if best_action is None or child_score < best_score:
                    best_score, best_action = child_score, action

        result = (best_score, best_action)
        self._cache[key] = result
        return result
