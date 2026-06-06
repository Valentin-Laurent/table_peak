"""Web session storage and the bot-advance step loop.

This module is the heart of Option Y: instead of running play_game in a worker
thread and threading human input through a queue, each HTTP request that
advances state calls `advance_bots` to run bot moves until either the game ends
or the next mover is human (signalled by `agents[seat] is None`).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from table_peak.agents.base import Agent
from table_peak.games.base import PlayerId, State


@dataclass
class GameSession:
    """One in-progress (or finished) game.

    `agents[seat] is None` means a human plays that seat. The web adapter
    applies human actions to `state` directly; bots are called via `Agent.act`.

    `game` selects the renderer (and is the key into the renderer registry).
    Mutable by design: `advance_bots` and the web layer replace `state` after
    each bot move; `agents` and `game` are unchanged after construction.
    """

    state: State
    agents: dict[PlayerId, Agent | None]
    game: str = "tic_tac_toe"


def advance_bots(session: GameSession) -> None:
    """Apply bot moves until the next mover is human or the game ends.

    Mutates `session.state` in place (frozen state is replaced; the dict
    holding it is mutable). Pure with respect to the agents themselves —
    they remain instances of the same `Agent` Protocol.
    """
    while not session.state.is_terminal:
        seat = session.state.current_player
        agent = session.agents[seat]
        if agent is None:
            return
        action = agent.act(session.state)
        session.state = session.state.apply_action(action)


class InMemorySessionStore:
    """Process-memory `dict[game_id, GameSession]`. Single Uvicorn worker only."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}

    def create(self, session: GameSession) -> str:
        game_id = secrets.token_urlsafe(8)
        self._sessions[game_id] = session
        return game_id

    def get(self, game_id: str) -> GameSession | None:
        return self._sessions.get(game_id)

    def save(self, game_id: str, session: GameSession) -> None:
        self._sessions[game_id] = session
