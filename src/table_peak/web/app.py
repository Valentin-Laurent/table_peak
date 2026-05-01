"""FastAPI app — driving adapter for the table_peak web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from table_peak.agents.base import Agent
from table_peak.games.base import PlayerId
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.web.agents import AGENT_REGISTRY
from table_peak.web.renderers.tic_tac_toe import render
from table_peak.web.sessions import GameSession, InMemorySessionStore, advance_bots

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_store = InMemorySessionStore()


def get_store() -> InMemorySessionStore:
    """FastAPI dependency. Tests override via app.dependency_overrides."""
    return _store


app = FastAPI(title="table_peak — TicTacToe Web UI")


def _build_agent(name: str) -> Agent | None:
    if name == "Human":
        return None
    factory = AGENT_REGISTRY.get(name)
    if factory is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {name}")
    return factory()


@app.get("/", response_class=HTMLResponse)
def new_game_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "new_game.html")


@app.post("/games")
def create_game(
    x_agent: Annotated[str, Form()],
    o_agent: Annotated[str, Form()],
    store: Annotated[InMemorySessionStore, Depends(get_store)],
) -> RedirectResponse:
    agents: dict[PlayerId, Agent | None] = {
        0: _build_agent(x_agent),
        1: _build_agent(o_agent),
    }
    session = GameSession(
        state=TicTacToe().new_initial_state(),
        agents=agents,
    )
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
    advance_bots(session)
    # advance_bots may have replaced session.state; persist via the store API
    # so a future non-in-memory backend can hook in here.
    store.save(game_id, session)
    view = render(session.state, session.agents, game_id)
    return templates.TemplateResponse(request, "game.html", {"view": view})
