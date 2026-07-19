"""Tests for the Skyjo web session factory + (Task 7) the app routes."""

from __future__ import annotations

import random
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.web.app import app, get_store
from table_peak.web.renderers.skyjo import render
from table_peak.web.sessions import GameSession, InMemorySessionStore
from table_peak.web.skyjo_play import HUMAN_SEAT, advance_bot_setup, new_skyjo_session


def test_new_session_starts_human_on_their_setup_reveal() -> None:
    session = new_skyjo_session(num_players=4, seed=1)
    assert session.game == "skyjo"
    assert session.agents[HUMAN_SEAT] is None
    assert len(session.agents) == 4
    assert session.last_event is None
    view = render(session.state, session.agents, "g")
    # The human is on their setup turn: 12 face-down cards, each armable as the
    # first reveal; nothing revealed yet (reveal is deferred to end of setup).
    assert view.is_terminal is False
    assert view.is_my_turn is True
    assert len(view.you.cards) == 12
    assert all(c.label == "?" for c in view.you.cards)
    assert all(c.arm_to == i for i, c in enumerate(view.you.cards))


def test_new_session_is_reproducible_for_a_fixed_seed() -> None:
    a = new_skyjo_session(num_players=3, seed=7)
    b = new_skyjo_session(num_players=3, seed=7)
    # Both pick the same two reveal slots, then bots finish setup deterministically.
    reveal = sk.encode_reveal_initial(0, 1)
    a.state = a.state.apply_action(reveal)
    b.state = b.state.apply_action(reveal)
    advance_bot_setup(a)
    advance_bot_setup(b)
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
    # The turn-order strip is always shown for Skyjo.
    assert "Turn order:" in r.text


def _step(client: TestClient, game_id: str, html: str) -> str:
    """Advance the game one interaction from the rendered board fragment.

    - Bot turn ("Next ▶" present) -> POST /next.
    - Human in setup -> arm the first reveal slot, then post the pair.
    - Human in branch-b with a face-down card -> click it (DiscardAndFlip).
    - Human in branch-b with no face-down card -> arm the drawn card, then place it.
    - Human at the main-play root -> draw from the deck (no card is clickable yet).
    """
    import re

    if "Next ▶" in html:
        r = client.post(f"/games/{game_id}/next")
        assert r.status_code == 200, r.text
        return str(r.text)
    matches = re.findall(r'name="action" value="(\d+)"', html)
    if matches:
        r = client.post(f"/games/{game_id}/move", data={"action": matches[0]})
    elif "reveal_first=" in html:
        # setup first-pick: arm slot 0, then post the reveal pair.
        armed_html = client.get(f"/games/{game_id}/board?reveal_first=0").text
        pair = re.findall(r'name="action" value="(\d+)"', armed_html)
        assert pair, f"no second-pick target after arming:\n{armed_html[:500]}"
        r = client.post(f"/games/{game_id}/move", data={"action": pair[0]})
    elif "armed=drawn" in html:
        # branch-b, all face-up: arm the drawn card, then place it on a slot.
        armed_html = client.get(f"/games/{game_id}/board?armed=drawn").text
        place = re.findall(r'name="action" value="(\d+)"', armed_html)
        assert place, f"no place target after arming:\n{armed_html[:500]}"
        r = client.post(f"/games/{game_id}/move", data={"action": place[0]})
    else:
        r = client.post(f"/games/{game_id}/move", data={"action": "78"})  # DrawDeck
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

    # Step through the round: click Next on bot turns, draw + place on human turns.
    # The round is finite, so this terminates. Cap iterations as a safety net.
    for _ in range(2000):
        if "Round over" in html:
            break
        html = _step(client, game_id, html)
    assert "Round over" in html
    # The score table is present (one row per player => at least two <td> score cells).
    assert html.count("</td>") >= 4


def _skyjo_root_state(num_players: int, seed: int) -> Any:
    """A PyspielStateAdapter on seat 0's main-play root turn."""
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()

    def in_setup(s: Any) -> bool:
        legal = list(s.legal_actions())
        return bool(legal) and all(sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal)

    while not state.is_terminal and in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    while not state.is_terminal and state.current_player != 0:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def test_board_route_renders_odds_panel_with_threshold() -> None:
    store = InMemorySessionStore()
    agents: dict[int, Agent | None] = {0: None, 1: RandomAgent(random.Random(1))}
    game_id = store.create(GameSession(game="skyjo", state=_skyjo_root_state(2, 3), agents=agents))
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as c:
            r = c.get(f"/games/{game_id}/board?threshold=3")
            assert r.status_code == 200, r.text
            assert "Draw odds" in r.text
            # Prove the threshold was forwarded: the explorer input is seeded with it
            # (3, no trailing .0) and both probability lines render against that value.
            assert 'value="3"' in r.text
            assert "Chosen card value:" in r.text
            assert "P(new card &lt; 3)" in r.text  # the beats-it line
            assert "P(new card = 3)" in r.text  # the equal-value / column-clear line
    finally:
        app.dependency_overrides.pop(get_store, None)
