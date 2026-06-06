"""Tests for the Skyjo web session factory + (Task 7) the app routes."""

from __future__ import annotations

from table_peak.web.renderers.skyjo import render
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
    import pytest

    with pytest.raises(ValueError):
        new_skyjo_session(num_players=1)
    with pytest.raises(ValueError):
        new_skyjo_session(num_players=9)
