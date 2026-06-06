"""Tests for the Skyjo web session factory + (Task 7) the app routes."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from table_peak.web.app import app, get_store
from table_peak.web.renderers.skyjo import render
from table_peak.web.sessions import InMemorySessionStore
from table_peak.web.skyjo_play import HUMAN_SEAT, new_skyjo_session


def test_new_session_drops_human_into_main_play_with_two_face_up() -> None:
    session = new_skyjo_session(num_players=4, seed=1)
    assert session.game == "skyjo"
    assert session.agents[HUMAN_SEAT] is None
    assert len(session.agents) == 4
    view = render(session.state, session.agents, "g")
    # Setup is over: the human can either take-discard or draw.
    assert view.is_terminal is False
    assert view.can_draw is True
    your_face_up = [c for c in view.you.cards if c.label != "?"]
    assert len(your_face_up) == 2


def test_new_session_is_reproducible_for_a_fixed_seed() -> None:
    a = new_skyjo_session(num_players=3, seed=7)
    b = new_skyjo_session(num_players=3, seed=7)
    va = render(a.state, a.agents, "g")
    vb = render(b.state, b.agents, "g")
    assert [c.label for c in va.you.cards] == [c.label for c in vb.you.cards]
    assert va.discard_top == vb.discard_top


def test_invalid_player_count_rejected() -> None:
    with pytest.raises(ValueError):
        new_skyjo_session(num_players=1)
    with pytest.raises(ValueError):
        new_skyjo_session(num_players=9)


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = InMemorySessionStore()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_store, None)


def test_new_game_page_offers_skyjo(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="num_players"' in r.text
    assert 'value="skyjo"' in r.text


def test_create_skyjo_game_rejects_bad_player_count(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"game": "skyjo", "num_players": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_create_skyjo_game_renders_board(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"game": "skyjo", "num_players": "3"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert r.text.count("Skyjo") >= 1
    assert 'id="board"' in r.text
    # The human is on a main-play turn: the Draw button is present.
    assert "Draw from deck" in r.text


def _post_first_legal_human_action(client: TestClient, game_id: str, html: str) -> str:
    """Parse the board fragment, post the first legal human action, return new html.

    The renderer puts each legal action in `name="action" value="N"`. We pick the
    first one (any legal move keeps the round progressing toward terminal)."""
    import re

    matches = re.findall(r'name="action" value="(\d+)"', html)
    assert matches, f"no clickable action in board:\n{html[:500]}"
    action = matches[0]
    r = client.post(f"/games/{game_id}/move", data={"action": action})
    assert r.status_code == 200, r.text
    return str(r.text)


def test_full_round_playthrough_reaches_terminal_with_scores(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"game": "skyjo", "num_players": "2"},
        follow_redirects=False,
    )
    game_id = str(r.headers["location"]).rsplit("/", 1)[-1]
    html = client.get(f"/games/{game_id}").text

    # Drive the human by always taking the first offered legal action. The round
    # is finite, so this terminates. Cap iterations as a safety net.
    for _ in range(500):
        if "Round over" in html:
            break
        html = _post_first_legal_human_action(client, game_id, html)
    assert "Round over" in html
    # The score table is present (one row per player => at least two <td> score cells).
    assert html.count("</td>") >= 4
