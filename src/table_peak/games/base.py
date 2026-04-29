"""Game and State protocols. Conceptually shaped after open_spiel."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

PlayerId = int
Action = int


@runtime_checkable
class State(Protocol):
    """A snapshot of a game. Immutable: apply_action returns a new state."""

    @property
    def current_player(self) -> PlayerId: ...

    def legal_actions(self) -> Sequence[Action]: ...

    def apply_action(self, action: Action) -> State: ...

    @property
    def is_terminal(self) -> bool: ...

    def returns(self) -> dict[PlayerId, float]: ...


@runtime_checkable
class Game(Protocol):
    """A game definition: a State factory plus meta-information."""

    @property
    def num_players(self) -> int: ...

    def new_initial_state(self) -> State: ...
