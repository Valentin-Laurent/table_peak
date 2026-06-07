"""FastAPI app — driving adapter for the table_peak web UI."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from table_peak.agents.base import Agent
from table_peak.games.base import PlayerId
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.web.agents import AGENT_REGISTRY
from table_peak.web.renderers import RENDERERS
from table_peak.web.renderers import skyjo as skyjo_renderer
from table_peak.web.sessions import GameSession, InMemorySessionStore, advance_bots
from table_peak.web.skyjo_play import advance_one_bot_turn, new_skyjo_session

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_store = InMemorySessionStore()


def get_store() -> InMemorySessionStore:
    """FastAPI dependency. Tests override via app.dependency_overrides."""
    return _store


app = FastAPI(title="table_peak — Web UI")


def _build_agent(name: str) -> Agent | None:
    if name == "Human":
        return None
    factory = AGENT_REGISTRY.get(name)
    if factory is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {name}")
    return factory()


def _render(session: GameSession, game_id: str, *, armed: bool = False) -> Any:
    if session.game == "skyjo":
        return skyjo_renderer.render(
            session.state,
            session.agents,
            game_id,
            armed=armed,
            last_event=session.last_event,
        )
    render_fn = RENDERERS.get(session.game)
    if render_fn is None:
        raise HTTPException(status_code=500, detail=f"No renderer for game: {session.game}")
    return render_fn(session.state, session.agents, game_id)


@app.get("/", response_class=HTMLResponse)
def new_game_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "new_game.html")


@app.post("/games")
def create_game(
    store: Annotated[InMemorySessionStore, Depends(get_store)],
    game: Annotated[str, Form()] = "tic_tac_toe",
    x_agent: Annotated[str, Form()] = "Human",
    o_agent: Annotated[str, Form()] = "Random",
    num_players: Annotated[int, Form()] = 2,
) -> RedirectResponse:
    if game == "skyjo":
        if not 2 <= num_players <= 8:
            raise HTTPException(status_code=400, detail="num_players must be in [2, 8]")
        session = new_skyjo_session(num_players=num_players, seed=secrets.randbelow(2**31))
    elif game == "tic_tac_toe":
        agents: dict[PlayerId, Agent | None] = {
            0: _build_agent(x_agent),
            1: _build_agent(o_agent),
        }
        session = GameSession(
            game="tic_tac_toe",
            state=TicTacToe().new_initial_state(),
            agents=agents,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown game: {game}")
    game_id = store.create(session)
    return RedirectResponse(url=f"/games/{game_id}", status_code=303)


@app.get("/games/{game_id}", response_class=HTMLResponse)
def game_page(
    game_id: str,
    request: Request,
    store: Annotated[InMemorySessionStore, Depends(get_store)],
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    # Skyjo steps bots one turn at a time via the "Next" button; TTT fast-forwards.
    if session.game != "skyjo":
        advance_bots(session)
        store.save(game_id, session)
    view = _render(session, game_id)
    return templates.TemplateResponse(request, "game.html", {"view": view})


@app.post("/games/{game_id}/move", response_class=HTMLResponse)
def submit_move(
    game_id: str,
    request: Request,
    action: Annotated[int, Form()],
    store: Annotated[InMemorySessionStore, Depends(get_store)],
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    if session.state.is_terminal:
        raise HTTPException(status_code=409, detail="Game is over")
    if session.agents[session.state.current_player] is not None:
        raise HTTPException(status_code=409, detail="Not your turn")
    if action not in session.state.legal_actions():
        raise HTTPException(status_code=400, detail=f"Illegal action: {action}")
    session.state = session.state.apply_action(action)
    if session.game != "skyjo":
        advance_bots(session)
    else:
        session.last_event = None  # a human move clears the stale bot note
    store.save(game_id, session)
    view = _render(session, game_id)
    partial = view.partial
    return templates.TemplateResponse(request, partial, {"view": view})


@app.post("/games/{game_id}/next", response_class=HTMLResponse)
def next_turn(
    game_id: str,
    request: Request,
    store: Annotated[InMemorySessionStore, Depends(get_store)],
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    if session.state.is_terminal:
        raise HTTPException(status_code=409, detail="Game is over")
    if session.agents[session.state.current_player] is None:
        raise HTTPException(status_code=409, detail="It is your turn")
    advance_one_bot_turn(session)
    store.save(game_id, session)
    view = _render(session, game_id)
    return templates.TemplateResponse(request, view.partial, {"view": view})


@app.get("/games/{game_id}/board", response_class=HTMLResponse)
def board_fragment(
    game_id: str,
    request: Request,
    store: Annotated[InMemorySessionStore, Depends(get_store)],
    armed: str | None = None,
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    view = _render(session, game_id, armed=(armed == "discard"))
    return templates.TemplateResponse(request, view.partial, {"view": view})
