"""Black-box tests for the Skyjo draw-probability engine."""

from __future__ import annotations

import pytest

from table_peak.games.skyjo.odds import DrawOdds


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
