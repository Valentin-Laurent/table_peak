"""Macro-fake tests for the web app via FastAPI TestClient.

The TestClient is the fake (in-process, no real socket); the real
TicTacToe / RandomAgent / MinimaxAgent are exercised unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from table_peak.web.app import app, get_store
from table_peak.web.sessions import InMemorySessionStore


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Each test gets a fresh in-memory store via FastAPI dependency override."""
    store = InMemorySessionStore()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_store, None)


def test_new_game_page_renders(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="x_agent"' in r.text
    assert 'name="o_agent"' in r.text
    # All three options are present.
    for label in ("Human", "Random", "Minimax"):
        assert label in r.text


def test_create_game_redirects_to_game_page(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"x_agent": "Human", "o_agent": "Minimax"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/games/")
    assert len(location.rsplit("/", 1)[-1]) > 0


def test_game_page_renders_board(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"x_agent": "Human", "o_agent": "Minimax"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert 'id="board"' in r.text
    assert "Your turn (X)" in r.text


def test_bot_x_human_o_bot_moves_before_render(client: TestClient) -> None:
    """When X is a bot and O is human, the bot's first move shows on the page."""
    r = client.post(
        "/games",
        data={"x_agent": "Minimax", "o_agent": "Human"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Your turn (O)" in r.text


def test_bot_vs_bot_auto_completes(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"x_agent": "Random", "o_agent": "Random"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Game over" in r.text


def test_unknown_game_id_returns_404(client: TestClient) -> None:
    r = client.get("/games/nonexistent")
    assert r.status_code == 404


def _create_game(client: TestClient, x_agent: str, o_agent: str) -> str:
    """Helper: create a game, return its id."""
    r = client.post(
        "/games",
        data={"x_agent": x_agent, "o_agent": o_agent},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[-1]


def test_human_vs_bot_first_move_advances_bot_reply(client: TestClient) -> None:
    """Human X plays cell 4; minimax O replies; response shows both moves."""
    game_id = _create_game(client, "Human", "Minimax")
    r = client.post(f"/games/{game_id}/move", data={"cell": "4"})
    assert r.status_code == 200
    # Response is the _board.html fragment.
    assert 'id="board"' in r.text
    # Human X is at cell 4 -> the X mark appears at least once.
    # Minimax O has played -> the O mark appears at least once.
    assert ">X<" in r.text
    assert ">O<" in r.text
    # Status reflects that it's now the human's turn again (or game is over).
    assert "Your turn (X)" in r.text or "Game over" in r.text


def test_invalid_move_rejected(client: TestClient) -> None:
    """Re-playing an occupied cell returns 400."""
    game_id = _create_game(client, "Human", "Minimax")
    # First move — legal.
    r1 = client.post(f"/games/{game_id}/move", data={"cell": "4"})
    assert r1.status_code == 200
    # Second move on same cell — illegal (occupied by X).
    r2 = client.post(f"/games/{game_id}/move", data={"cell": "4"})
    assert r2.status_code == 400


def test_move_when_terminal_rejected(client: TestClient) -> None:
    """Random vs Random auto-completes on first GET; subsequent move -> 409."""
    game_id = _create_game(client, "Random", "Random")
    # Trigger advance_bots via GET; game finishes.
    client.get(f"/games/{game_id}")
    # Any cell now -> 409.
    r = client.post(f"/games/{game_id}/move", data={"cell": "0"})
    assert r.status_code == 409


def test_move_when_not_humans_turn_rejected(client: TestClient) -> None:
    """Random vs Random session: current_player is a bot -> POST move returns 409."""
    game_id = _create_game(client, "Random", "Random")
    # Don't trigger GET — state is still initial (non-terminal), current bot.
    r = client.post(f"/games/{game_id}/move", data={"cell": "0"})
    assert r.status_code == 409


def test_move_on_unknown_game_returns_404(client: TestClient) -> None:
    r = client.post("/games/nonexistent/move", data={"cell": "0"})
    assert r.status_code == 404


def test_out_of_range_cell_rejected(client: TestClient) -> None:
    """Cell 99 is not in legal_actions() -> 400."""
    game_id = _create_game(client, "Human", "Minimax")
    r = client.post(f"/games/{game_id}/move", data={"cell": "99"})
    assert r.status_code == 400
