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
