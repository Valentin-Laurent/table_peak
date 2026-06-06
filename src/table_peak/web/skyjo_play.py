"""Build a web GameSession for Skyjo: human at seat 0, Random bots elsewhere.

Setup (deal + the blind flip-2) is auto-resolved with random reveals for every
seat, including the human, so the human is handed their first main-play turn.
"""

from __future__ import annotations

import random
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.web.sessions import GameSession, advance_bots

HUMAN_SEAT = 0


def _in_setup(state: Any) -> bool:
    legal = list(state.legal_actions())
    return bool(legal) and all(sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal)


def _auto_resolve_setup(state: Any, rng: random.Random) -> Any:
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def new_skyjo_session(num_players: int, seed: int = 0) -> GameSession:
    if not 2 <= num_players <= 8:
        raise ValueError(f"num_players must be in [2, 8], got {num_players}")
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    state = _auto_resolve_setup(state, rng)
    agents: dict[PlayerId, Agent | None] = {HUMAN_SEAT: None}
    for p in range(num_players):
        if p != HUMAN_SEAT:
            agents[p] = RandomAgent(random.Random(seed + 1 + p))
    session = GameSession(game="skyjo", state=state, agents=agents)
    advance_bots(session)
    return session
