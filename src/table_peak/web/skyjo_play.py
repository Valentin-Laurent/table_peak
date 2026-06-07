"""Build a web GameSession for Skyjo: human at seat 0, Random bots elsewhere.

Setup (deal + the blind flip-2) is auto-resolved with random reveals for every
seat, including the human. Unlike TTT, bots are *not* fast-forwarded: the human
clicks "Next" to step through one bot turn at a time so every move is visible.
"""

from __future__ import annotations

import random
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.web.sessions import GameSession

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
    # No fast-forward: if a bot opens the round, the human steps it via "Next".
    return GameSession(game="skyjo", state=state, agents=agents)


def advance_one_bot_turn(session: GameSession) -> None:
    """Apply exactly one bot's full turn (1 action, or draw + follow-up).

    Records a human-readable note in `session.last_event`. No-op if the game is
    over or the current seat is the human.
    """
    state = session.state
    if state.is_terminal:
        return
    seat = state.current_player
    agent = session.agents.get(seat)
    if agent is None:
        return
    steps: list[tuple[Any, int]] = []
    while not state.is_terminal and state.current_player == seat:
        action = agent.act(state)
        steps.append((state, action))
        state = state.apply_action(action)
    session.state = state
    session.last_event = _describe_bot_turn(seat, steps)


def _describe_bot_turn(seat: int, steps: list[tuple[Any, int]]) -> str:
    """Turn a captured (state-before, action) sequence into one short sentence."""
    parts: list[str] = []
    for state_before, action_id in steps:
        a = sk.decode(action_id)
        inner = state_before.inner
        if a.kind == sk.ActionKind.TAKE_DISCARD_AND_REPLACE:
            top = inner._discard_pile[-1] if inner._discard_pile else "?"
            parts.append(f"took {top} from the discard into slot {a.slot}")
        elif a.kind == sk.ActionKind.DRAW_DECK:
            parts.append("drew from the deck")
        elif a.kind == sk.ActionKind.REPLACE_FROM_HAND:
            parts.append(f"kept {inner._drawn_card} in slot {a.slot}")
        elif a.kind == sk.ActionKind.DISCARD_AND_FLIP:
            parts.append(f"discarded it and flipped slot {a.slot}")
    if not parts:
        return f"Bot {seat} passed."
    return f"Bot {seat} " + ", then ".join(parts) + "."
