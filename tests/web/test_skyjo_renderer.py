"""Tests for the Skyjo board renderer (state -> SkyjoBoardView)."""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.games.skyjo.odds import draw_odds
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
    assert view.odds is None  # odds only surface on the human's own turn


def test_setup_first_pick_arms_each_card() -> None:
    # A fresh state sits at SETUP_COMMIT with the human (seat 0) to commit first.
    state = SkyjoGameWrapper(num_players=2, seed=3).new_initial_state()
    view = render(state, _agents(2), "g1")
    assert view.is_my_turn is True
    assert view.reveal_pending is False
    assert len(view.you.cards) == 12
    # Nothing revealed yet; every card is an arm-the-first-reveal source (GET), not a move.
    for slot, card in enumerate(view.you.cards):
        assert card.label == "?"
        assert card.clickable is False
        assert card.arm_to == slot
    assert "reveal" in view.status.lower()


def test_setup_second_pick_posts_reveal_initial() -> None:
    state = SkyjoGameWrapper(num_players=2, seed=3).new_initial_state()
    view = render(state, _agents(2), "g1", reveal_first=2)
    assert view.reveal_pending is True
    for slot, card in enumerate(view.you.cards):
        if slot == 2:
            assert card.selected is True
            assert card.clickable is False
        else:
            assert card.clickable is True
            assert card.action == sk.encode_reveal_initial(2, slot)


def test_branch_b_unarmed_flips_face_down_cards_and_drawn_card_arms() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    state = state.apply_action(sk.encode_draw_deck())
    view = render(state, _agents(2), "g1")
    assert view.draw_pile_clickable is False
    assert view.drawn_card is not None
    assert view.armed is False
    # The drawn card is the "arm to keep it" source.
    assert view.drawn_clickable is True
    # Unarmed: clicking a face-down card discards the drawn card to reveal it;
    # face-up cards are not clickable (no reveal possible without arming).
    flipped_any = False
    for slot, card in enumerate(view.you.cards):
        if card.label == "?":
            assert card.clickable is True
            assert card.action == sk.encode_discard_and_flip(slot)
            flipped_any = True
        else:
            assert card.clickable is False
    assert flipped_any


def test_branch_b_armed_places_drawn_card_on_any_slot() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    state = state.apply_action(sk.encode_draw_deck())
    view = render(state, _agents(2), "g1", armed=True)
    assert view.armed is True
    assert view.drawn_clickable is False
    # Armed: every slot becomes a place target posting replace-from-hand.
    for slot, card in enumerate(view.you.cards):
        assert card.clickable is True
        assert card.action == sk.encode_replace_from_hand(slot)


def _to_branch_b(num_players: int, seed: int) -> Any:
    """A human root state advanced one DrawDeck into branch-b."""
    state = _to_human_turn(num_players, seed)
    return state.apply_action(sk.encode_draw_deck())


def test_threshold_param_drives_prob_less_than() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1", threshold=3.0)
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.odds.threshold == 3.0
    assert view.odds.prob_less_than == engine.prob_less_than(3.0)


def test_no_threshold_seeds_explorer_at_discard_top() -> None:
    # Seeded at the discard top, the explorer's P(next card < top) is exactly the
    # 'a deck draw beats taking the top' odds.
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1")
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.discard_top is not None  # root turn always has a discard top
    assert view.odds.threshold == view.discard_top
    assert view.odds.prob_less_than == engine.prob_less_than(view.discard_top)


def test_threshold_param_drives_prob_equal() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1", threshold=3.0)
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.odds.prob_equal == engine.prob_equal(3.0)


def test_no_threshold_seeds_prob_equal_at_discard_top() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1")
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.discard_top is not None  # root turn always has a discard top
    assert view.odds.prob_equal == engine.prob_equal(view.discard_top)


def test_branch_b_and_setup_have_no_odds() -> None:
    assert render(_to_branch_b(2, 3), _agents(2), "g1").odds is None
    setup = SkyjoGameWrapper(num_players=2, seed=3).new_initial_state()
    assert render(setup, _agents(2), "g1").odds is None


def test_recycle_boundary_still_renders_odds() -> None:
    # Deterministically force the recycle boundary at a human main-play root:
    # empty the draw pile and set a known discard, mirroring the engine's own
    # test_empty_draw_pile_uses_recycled_discard_minus_top. Odds still render off
    # the recycled pool.
    state = _to_human_turn(num_players=2, seed=3)
    state.inner._remaining_deck_counts = Counter()  # draw pile exhausted
    state.inner._discard_pile = [3, 3, 7, 1]  # top is 1; recycled pool is {3, 3, 7}
    view = render(state, _agents(2), "g1")
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.discard_top is not None
    assert view.odds.prob_less_than == engine.prob_less_than(view.discard_top)


def test_armed_root_hides_odds_panel() -> None:
    # Once the discard is armed (place-mode), the draw-vs-take decision is made;
    # the explorer must vanish so its htmx round-trip can't drop the armed state.
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1", armed=True)
    assert view.armed is True
    assert view.odds is None


def test_empty_discard_root_renders_odds_without_probabilities() -> None:
    # An empty discard (no top card) is rare but legal: EV still shows, but the
    # discard-relative probabilities have no reference value and stay None.
    state = _to_human_turn(num_players=2, seed=3)
    state.inner._discard_pile = []
    view = render(state, _agents(2), "g1")
    assert view.discard_top is None
    assert view.odds is not None
    assert view.odds.threshold is None
    assert view.odds.prob_less_than is None


def test_terminal_shows_sorted_scores_and_no_clickable_cards() -> None:
    rng = random.Random(42)
    state = SkyjoGameWrapper(num_players=2, seed=42).new_initial_state()
    while not state.is_terminal:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    view = render(state, _agents(2), "g1")
    assert view.is_terminal is True
    assert view.odds is None  # no odds panel once the round is over
    assert view.draw_pile_clickable is False
    assert view.awaiting_bot is False
    assert all(not card.clickable for card in view.you.cards)
    scores = [score for _label, score in view.final_scores]
    assert scores == sorted(scores)  # ascending; lowest wins
    assert "Round over" in view.status
