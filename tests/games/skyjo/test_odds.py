"""Black-box tests for the Skyjo draw-probability engine."""

from __future__ import annotations

from collections import Counter

import pyspiel  # type: ignore[import-not-found]
import pytest

import table_peak.games.skyjo  # noqa: F401  registration side-effect
from table_peak.games.skyjo.actions import encode_reveal_initial
from table_peak.games.skyjo.deck import DECK_COMPOSITION
from table_peak.games.skyjo.odds import DrawOdds, draw_odds


def test_pmf_is_exposed_as_given():
    odds = DrawOdds(pmf={-2: 0.5, 5: 0.5})
    assert odds.pmf == {-2: 0.5, 5: 0.5}


def test_expected_value_is_probability_weighted_mean():
    odds = DrawOdds(pmf={-2: 0.25, 0: 0.5, 4: 0.25})
    # 0.25*-2 + 0.5*0 + 0.25*4 = 0.5
    assert odds.expected_value() == pytest.approx(0.5)


def test_prob_at_most_sums_probabilities_up_to_threshold_inclusive():
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    assert odds.prob_at_most(0) == pytest.approx(0.5)  # -2 and 0
    assert odds.prob_at_most(-2) == pytest.approx(0.2)  # only -2
    assert odds.prob_at_most(12) == pytest.approx(1.0)  # everything
    assert odds.prob_at_most(-3) == pytest.approx(0.0)  # nothing


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


def _expected_pool(state) -> Counter[int]:
    pool: Counter[int] = Counter(DECK_COMPOSITION)
    for grid in state._grids:
        for value in grid.face_up_values().values():
            pool[value] -= 1
    for value in state._discard_pile:
        pool[value] -= 1
    return +pool  # drop zero/negative entries


def test_pmf_matches_unseen_pool_normalized():
    state = make_main_play_state()
    pool = _expected_pool(state)
    total = sum(pool.values())

    odds = draw_odds(state)

    assert odds.pmf.keys() == {v for v, n in pool.items() if n > 0}
    for value, count in pool.items():
        if count > 0:
            assert odds.pmf[value] == pytest.approx(count / total)


def test_pmf_sums_to_one():
    odds = draw_odds(make_main_play_state())
    assert sum(odds.pmf.values()) == pytest.approx(1.0)


def test_pool_size_invariant_holds():
    state = make_main_play_state()
    draw_pile_size = sum(state._remaining_deck_counts.values())
    face_down = sum(g.num_face_down for g in state._grids)

    pool = _expected_pool(state)

    assert sum(pool.values()) == draw_pile_size + face_down
