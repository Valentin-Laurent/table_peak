"""Black-box tests for round scoring + doubling."""

from __future__ import annotations

from table_peak.games.skyjo.scoring import compute_round_scores


def test_no_doubling_when_round_ender_strictly_lowest() -> None:
    raw = {0: 10, 1: 20, 2: 30}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 10, 1: 20, 2: 30}


def test_doubling_when_round_ender_not_lowest() -> None:
    raw = {0: 50, 1: 20, 2: 30}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 100, 1: 20, 2: 30}


def test_doubling_on_tie_at_lowest() -> None:
    # round-ender ties at lowest -> still doubled per the rules-doc CHOSEN reading
    raw = {0: 10, 1: 10, 2: 30}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 20, 1: 10, 2: 30}


def test_doubling_caps_at_zero_when_round_ender_negative_and_not_strictly_lowest() -> None:
    # negative round-ender, tied at lowest with another player -> doubling cap kicks in.
    # max(2*-4, 0) = 0, so the penalized ender ends at 0 rather than improving to -8.
    raw = {0: -4, 1: -4, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 0, 1: -4, 2: 5}


def test_doubling_caps_at_zero_when_round_ender_negative_and_not_lowest_at_all() -> None:
    # negative round-ender, strictly above another negative -> doubling cap still kicks in.
    raw = {0: -2, 1: -6, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 0, 1: -6, 2: 5}


def test_doubling_of_zero_round_ender_when_tied_at_lowest_stays_zero() -> None:
    # round-ender at 0 tied with another player at 0 -> max(2*0, 0) = 0.
    raw = {0: 0, 1: 0, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 0, 1: 0, 2: 5}


def test_doubling_with_strictly_lowest_negative() -> None:
    # round-ender is strictly lowest with -10 -> no doubling
    raw = {0: -10, 1: -4, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: -10, 1: -4, 2: 5}


def test_two_player_doubling_when_tied() -> None:
    raw = {0: 5, 1: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 10, 1: 5}


def test_two_player_no_doubling_when_strictly_lowest() -> None:
    raw = {0: 5, 1: 6}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 5, 1: 6}
