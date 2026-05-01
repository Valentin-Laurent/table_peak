"""Black-box tests for the web session store and game session."""

from __future__ import annotations

from table_peak.agents.base import Agent
from table_peak.agents.minimax import MinimaxAgent
from table_peak.games.base import PlayerId
from table_peak.games.tic_tac_toe import TicTacToe, TicTacToeState
from table_peak.web.sessions import GameSession, InMemorySessionStore, advance_bots


def _initial_state() -> TicTacToeState:
    return TicTacToe().new_initial_state()


def _session(agents: dict[PlayerId, Agent | None]) -> GameSession:
    return GameSession(state=_initial_state(), agents=agents)


def test_store_create_returns_unique_ids() -> None:
    store = InMemorySessionStore()
    a: dict[PlayerId, Agent | None] = {0: None, 1: None}
    b: dict[PlayerId, Agent | None] = {0: None, 1: None}
    id1 = store.create(_session(a))
    id2 = store.create(_session(b))
    assert id1 != id2
    assert isinstance(id1, str) and len(id1) > 0


def test_store_get_returns_stored_session() -> None:
    store = InMemorySessionStore()
    agents: dict[PlayerId, Agent | None] = {0: None, 1: None}
    session = _session(agents)
    game_id = store.create(session)
    assert store.get(game_id) is session


def test_store_get_unknown_returns_none() -> None:
    store = InMemorySessionStore()
    assert store.get("nonexistent") is None


def test_store_save_overwrites_existing_session() -> None:
    store = InMemorySessionStore()
    agents: dict[PlayerId, Agent | None] = {0: None, 1: None}
    session = _session(agents)
    game_id = store.create(session)
    replaced = _session(agents)
    store.save(game_id, replaced)
    assert store.get(game_id) is replaced


def test_advance_bots_runs_until_human_turn() -> None:
    """X is a bot, O is human: advance_bots makes one move then stops."""
    agents: dict[PlayerId, Agent | None] = {0: MinimaxAgent(), 1: None}
    session = _session(agents)
    advance_bots(session)
    # After one bot move, current_player switches to O (human) -> stop.
    assert session.state.current_player == 1
    # Exactly one cell on the board is occupied by X.
    occupied = sum(1 for c in session.state.board if c != -1)
    assert occupied == 1


def test_advance_bots_runs_to_terminal_when_no_humans() -> None:
    """Two minimax bots: advance_bots plays the whole game."""
    agents: dict[PlayerId, Agent | None] = {0: MinimaxAgent(), 1: MinimaxAgent()}
    session = _session(agents)
    advance_bots(session)
    assert session.state.is_terminal


def test_advance_bots_no_op_when_already_terminal() -> None:
    """Calling advance_bots on a terminal state is a no-op."""
    agents: dict[PlayerId, Agent | None] = {0: MinimaxAgent(), 1: MinimaxAgent()}
    session = _session(agents)
    advance_bots(session)  # plays to end
    state_before = session.state
    advance_bots(session)  # second call: no-op
    assert session.state is state_before


def test_advance_bots_no_op_when_human_already_to_move() -> None:
    """Human seat is current_player: advance_bots does nothing."""
    agents: dict[PlayerId, Agent | None] = {0: None, 1: MinimaxAgent()}
    session = _session(agents)
    state_before = session.state
    advance_bots(session)
    assert session.state is state_before
