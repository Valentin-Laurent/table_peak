"""Black-box tests for the Skyjo draw-probability engine."""

from __future__ import annotations

from collections import Counter

import pyspiel  # type: ignore[import-not-found]
import pytest

import table_peak.games.skyjo  # noqa: F401  registration side-effect
from table_peak.games.skyjo.actions import encode_reveal_initial
from table_peak.games.skyjo.deck import DECK_COMPOSITION
from table_peak.games.skyjo.odds import DrawOdds, draw_odds


def test_pmf_is_exposed_as_given() -> None:
    odds = DrawOdds(pmf={-2: 0.5, 5: 0.5})
    assert odds.pmf == {-2: 0.5, 5: 0.5}


def test_expected_value_is_probability_weighted_mean() -> None:
    odds = DrawOdds(pmf={-2: 0.25, 0: 0.5, 4: 0.25})
    # 0.25*-2 + 0.5*0 + 0.25*4 = 0.5
    assert odds.expected_value() == pytest.approx(0.5)


def test_prob_less_than_sums_probabilities_strictly_below_threshold() -> None:
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    assert odds.prob_less_than(0) == pytest.approx(0.2)  # only -2 (0 excluded)
    assert odds.prob_less_than(5) == pytest.approx(0.5)  # -2 and 0 (5 excluded)
    assert odds.prob_less_than(13) == pytest.approx(1.0)  # everything
    assert odds.prob_less_than(-2) == pytest.approx(0.0)  # nothing (-2 excluded)


def test_prob_equal_looks_up_probability_of_exact_value() -> None:
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    assert odds.prob_equal(0) == pytest.approx(0.3)
    assert odds.prob_equal(5) == pytest.approx(0.5)
    assert odds.prob_equal(7) == pytest.approx(0.0)  # not in support


def test_prob_equal_accepts_float_threshold() -> None:
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    # A whole-number float equals its integer card (5.0 == 5); a .5 boundary
    # equals no card, so its exact-value probability is zero.
    assert odds.prob_equal(5.0) == pytest.approx(0.5)
    assert odds.prob_equal(4.5) == pytest.approx(0.0)


def make_main_play_state(num_players: int = 2, seed: int = 0) -> pyspiel.State:
    """Build a real SkyjoState driven into Phase.MAIN_PLAY.

    Reuses the pattern from tests/games/skyjo/test_observer.py's
    `_advance_to_main_play`: resolve the deal chance node, then have every
    player reveal their two initial cards (slots 0 and 1).
    """
    game = pyspiel.load_game("skyjo", {"num_players": num_players, "seed": seed})
    state = game.new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(num_players):
        state.apply_action(encode_reveal_initial(0, 1))
    return state


def _expected_pool(state: pyspiel.State) -> Counter[int]:
    pool: Counter[int] = Counter(DECK_COMPOSITION)
    for grid in state._grids:
        for value in grid.face_up_values().values():
            pool[value] -= 1
    for value in state._discard_pile:
        pool[value] -= 1
    return +pool  # drop zero/negative entries


def test_pmf_matches_unseen_pool_normalized() -> None:
    state = make_main_play_state()
    pool = _expected_pool(state)
    total = sum(pool.values())

    odds = draw_odds(state)

    assert odds.pmf.keys() == {v for v, n in pool.items() if n > 0}
    for value, count in pool.items():
        if count > 0:
            assert odds.pmf[value] == pytest.approx(count / total)


def test_pmf_sums_to_one() -> None:
    odds = draw_odds(make_main_play_state())
    assert sum(odds.pmf.values()) == pytest.approx(1.0)


def test_pool_size_invariant_holds() -> None:
    state = make_main_play_state()
    draw_pile_size = sum(state._remaining_deck_counts.values())
    face_down = sum(g.num_face_down for g in state._grids)

    pool = _expected_pool(state)

    assert sum(pool.values()) == draw_pile_size + face_down


def test_prob_less_than_accepts_float_threshold() -> None:
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    # A .5 boundary includes everything strictly below it (no card equals it,
    # so < and <= coincide there).
    assert odds.prob_less_than(0.5) == pytest.approx(0.5)  # -2 and 0
    assert odds.prob_less_than(-1.5) == pytest.approx(0.2)  # only -2


def test_empty_draw_pile_uses_recycled_discard_minus_top() -> None:
    # Build a real MAIN_PLAY state via the suite helper, then (Arrange step only)
    # force an empty draw pile and a known discard pile. draw_odds still reads only
    # public size + discard, so this stays black-box at the API boundary.
    state = make_main_play_state()
    state._remaining_deck_counts = Counter()
    state._discard_pile = [3, 3, 7, 1]  # 1 is the top; recycled pool is {3, 3, 7}

    odds = draw_odds(state)

    # Uniform over the recycled discard-minus-top: two 3s and one 7 out of three.
    assert odds.pmf == pytest.approx({3: 2 / 3, 7: 1 / 3})
