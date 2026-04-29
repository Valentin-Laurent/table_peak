"""Game and match runner. Imperative shell over the functional core."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from table_peak.agents.base import Agent
from table_peak.games.base import Action, Game, PlayerId, State


@dataclass(frozen=True, slots=True)
class Outcome:
    """Result of a single game."""

    returns: dict[PlayerId, float]
    trajectory: list[tuple[State, Action]]
    num_moves: int


def play_game(game: Game, agents: Mapping[PlayerId, Agent]) -> Outcome:
    """Run one game to completion and return its outcome."""
    if set(agents.keys()) != set(range(game.num_players)):
        raise ValueError(
            f"agents keys {sorted(agents.keys())} must equal "
            f"{list(range(game.num_players))} (game.num_players={game.num_players})"
        )

    state = game.new_initial_state()
    history: list[tuple[State, Action]] = []
    while not state.is_terminal:
        player = state.current_player
        action = agents[player].act(state)
        history.append((state, action))
        state = state.apply_action(action)
    return Outcome(returns=state.returns(), trajectory=history, num_moves=len(history))
