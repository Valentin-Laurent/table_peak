"""Agent protocol. A pure policy: state -> action."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from table_peak.games.base import Action, State


@runtime_checkable
class Agent(Protocol):
    """A policy. Pure: must not mutate hidden state during act()."""

    def act(self, state: State) -> Action: ...
