"""Tests for the Skyjo board renderer (state -> SkyjoBoardView)."""

from __future__ import annotations

import random
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.web.renderers.skyjo import render


def _in_setup(state: Any) -> bool:
    legal = list(state.legal_actions())
    return bool(legal) and all(sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal)


def _to_human_turn(num_players: int, seed: int) -> Any:
    """State at a main-play root turn owned by seat 0."""
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    while not state.is_terminal and state.current_player != 0:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def _agents(num_players: int) -> dict[PlayerId, Agent | None]:
    a: dict[PlayerId, Agent | None] = {0: None}
    for p in range(1, num_players):
        a[p] = RandomAgent(random.Random(p))
    return a


def test_root_turn_offers_piles_as_sources_cards_not_clickable_until_armed() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1")
    assert view.partial == "_skyjo_board.html"
    assert view.title == "Skyjo"
    assert view.is_my_turn is True
    # At the unarmed root both piles are live sources; cards are not yet clickable.
    assert view.draw_pile_clickable is True
    assert view.discard_clickable is True
    assert view.draw_action == sk.encode_draw_deck()
    assert view.armed is False
    assert all(not card.clickable for card in view.you.cards)
    # Opponent cards are never clickable, and hidden cards show "?".
    for opp in view.opponents:
        assert all(not card.clickable for card in opp.cards)
    assert any(card.label == "?" for card in view.opponents[0].cards)


def test_armed_discard_makes_cards_post_take_discard() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1", armed=True)
    assert view.armed is True
    # Arming the discard hides the pile sources and turns cards into place targets.
    assert view.draw_pile_clickable is False
    assert view.discard_clickable is False
    assert all(card.clickable for card in view.you.cards)
    for slot, card in enumerate(view.you.cards):
        assert card.action == sk.encode_take_discard_and_replace(slot)


def test_turn_order_marks_the_current_player() -> None:
    state = _to_human_turn(num_players=3, seed=3)
    view = render(state, _agents(3), "g1")
    assert [t.label for t in view.turn_order] == ["YOU", "Bot 1", "Bot 2"]
    assert sum(1 for t in view.turn_order if t.is_current) == 1
    assert view.turn_order[0].is_current is True  # human is on turn here


def test_bot_turn_awaits_next_and_carries_last_event() -> None:
    rng = random.Random(5)
    state = SkyjoGameWrapper(num_players=2, seed=5).new_initial_state()
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    # Drive to a bot (seat 1) turn.
    while not state.is_terminal and state.current_player != 1:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    view = render(state, _agents(2), "g1", last_event="Bot 1 drew from the deck.")
    assert view.is_my_turn is False
    assert view.awaiting_bot is True
    assert view.last_event == "Bot 1 drew from the deck."


def test_branch_b_offers_replace_cards_and_flip_buttons() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    state = state.apply_action(sk.encode_draw_deck())
    view = render(state, _agents(2), "g1")
    assert view.draw_pile_clickable is False
    assert view.drawn_card is not None
    # Cards post replace-from-hand.
    for slot, card in enumerate(view.you.cards):
        assert card.clickable is True
        assert card.action == sk.encode_replace_from_hand(slot)
    # There is one flip button per face-down slot, posting discard-and-flip.
    flip_slots = {fb.slot for fb in view.flip_buttons}
    assert len(view.flip_buttons) >= 1
    for fb in view.flip_buttons:
        assert fb.action == sk.encode_discard_and_flip(fb.slot)
    # Flip buttons target only currently-hidden slots.
    for slot, card in enumerate(view.you.cards):
        if card.label != "?":
            assert slot not in flip_slots


def test_terminal_shows_sorted_scores_and_no_clickable_cards() -> None:
    rng = random.Random(42)
    state = SkyjoGameWrapper(num_players=2, seed=42).new_initial_state()
    while not state.is_terminal:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    view = render(state, _agents(2), "g1")
    assert view.is_terminal is True
    assert view.draw_pile_clickable is False
    assert view.awaiting_bot is False
    assert all(not card.clickable for card in view.you.cards)
    scores = [score for _label, score in view.final_scores]
    assert scores == sorted(scores)  # ascending; lowest wins
    assert "Round over" in view.status
