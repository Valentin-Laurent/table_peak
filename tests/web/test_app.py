"""Macro-fake tests for the web app via FastAPI TestClient.

The TestClient is the fake (in-process, no real socket); the real
TicTacToe / RandomAgent / MinimaxAgent are exercised unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from table_peak.games.quoridor import actions as q
from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor
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
    return str(r.headers["location"]).rsplit("/", 1)[-1]


def test_human_vs_bot_first_move_advances_bot_reply(client: TestClient) -> None:
    """Human X plays cell 4; minimax O replies; response shows both moves."""
    game_id = _create_game(client, "Human", "Minimax")
    r = client.post(f"/games/{game_id}/move", data={"action": "4"})
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
    r1 = client.post(f"/games/{game_id}/move", data={"action": "4"})
    assert r1.status_code == 200
    # Second move on same cell — illegal (occupied by X).
    r2 = client.post(f"/games/{game_id}/move", data={"action": "4"})
    assert r2.status_code == 400


def test_move_when_terminal_rejected(client: TestClient) -> None:
    """Random vs Random auto-completes on first GET; subsequent move -> 409."""
    game_id = _create_game(client, "Random", "Random")
    # Trigger advance_bots via GET; game finishes.
    client.get(f"/games/{game_id}")
    # Any cell now -> 409.
    r = client.post(f"/games/{game_id}/move", data={"action": "0"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Game is over"


def test_move_when_not_humans_turn_rejected(client: TestClient) -> None:
    """Random vs Random session: current_player is a bot -> POST move returns 409."""
    game_id = _create_game(client, "Random", "Random")
    # Don't trigger GET — state is still initial (non-terminal), current bot.
    r = client.post(f"/games/{game_id}/move", data={"action": "0"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Not your turn"


def test_move_on_unknown_game_returns_404(client: TestClient) -> None:
    """POSTing a move to a game id that doesn't exist returns 404."""
    r = client.post("/games/nonexistent/move", data={"action": "0"})
    assert r.status_code == 404


def test_out_of_range_cell_rejected(client: TestClient) -> None:
    """Cell 99 is not in legal_actions() -> 400."""
    game_id = _create_game(client, "Human", "Minimax")
    r = client.post(f"/games/{game_id}/move", data={"action": "99"})
    assert r.status_code == 400


def _create_quoridor(client: TestClient, x_agent: str, o_agent: str) -> str:
    """Helper: create a Quoridor game, return its id."""
    r = client.post(
        "/games",
        data={"game": "quoridor", "x_agent": x_agent, "o_agent": o_agent},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return str(r.headers["location"]).rsplit("/", 1)[-1]


def test_new_game_page_offers_quoridor(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'value="quoridor"' in r.text


def test_quoridor_game_page_renders_board(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    r = client.get(f"/games/{game_id}")
    assert r.status_code == 200
    assert 'id="board"' in r.text
    assert "Player 1" in r.text
    assert "pawn p0" in r.text


def test_quoridor_human_pawn_move_applies(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    # P0 steps forward from (4,0) to (4,1).
    action = q.encode_move(Cell(col=4, row=1))
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 200
    assert 'id="board"' in r.text  # response is the board fragment


def test_quoridor_human_wall_move_applies(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    # A resolved wall action (what the 2-click JS ultimately POSTs).
    action = q.encode_wall(WallAnchor(col=2, row=3), Orientation.HORIZONTAL)
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 200
    # The wall renders solid: assert the rendered class attribute, not the bare
    # substring "placed" (the partial's inline <style> always contains .seg.placed).
    assert 'class="seg placed"' in r.text


def test_quoridor_illegal_action_rejected(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    # Teleporting P0 across the board is not a legal action.
    action = q.encode_move(Cell(col=0, row=8))
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 400


def test_quoridor_human_vs_random_bot_replies(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Random")
    # GET fast-forwards nothing (P0/human is first); human moves, bot replies.
    action = q.encode_move(Cell(col=4, row=1))
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 200
    # After the human move + bot reply it is the human's turn again, or game over.
    assert "Player 1" in r.text or "Game over" in r.text
