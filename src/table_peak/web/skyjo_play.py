"""Build a web GameSession for Skyjo: human at seat 0, Random bots elsewhere.

The deal is auto-resolved by the adapter, dropping the human onto their own
SETUP_COMMIT turn so they pick which two cards to reveal. Bot setup commits are
resolved for them (see `advance_bot_setup`). Unlike TTT, bots are *not*
fast-forwarded in main play: the human clicks "Next" to step through one bot turn
at a time so every move is visible.
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


def advance_bot_setup(session: GameSession) -> None:
    """Resolve bot SETUP_COMMIT turns, stopping at the human's setup turn or main play.

    Bots pick their two reveal slots via their own agent. No-op once setup is over
    (so it is safe to call after every human move).
    """
    while not session.state.is_terminal and _in_setup(session.state):
        seat = session.state.current_player
        agent = session.agents.get(seat)
        if agent is None:
            return
        session.state = session.state.apply_action(agent.act(session.state))


def new_skyjo_session(num_players: int, seed: int = 0) -> GameSession:
    if not 2 <= num_players <= 8:
        raise ValueError(f"num_players must be in [2, 8], got {num_players}")
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    agents: dict[PlayerId, Agent | None] = {HUMAN_SEAT: None}
    for p in range(num_players):
        if p != HUMAN_SEAT:
            agents[p] = RandomAgent(random.Random(seed + 1 + p))
    session = GameSession(game="skyjo", state=state, agents=agents)
    # Human (seat 0) commits first, so this is a no-op today; kept for robustness
    # if seat order ever changes. Leaves the human on their setup-reveal turn.
    advance_bot_setup(session)
    return session


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
