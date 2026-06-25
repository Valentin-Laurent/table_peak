import math

from spikes.payoff import PayoffMode, zero_sum_returns


def test_win_loss_higher_return_wins():
    # player 0 has the higher (less negative) return -> player 0 wins
    assert zero_sum_returns([-10.0, -25.0], PayoffMode.WIN_LOSS) == [1.0, -1.0]
    assert zero_sum_returns([-25.0, -10.0], PayoffMode.WIN_LOSS) == [-1.0, 1.0]


def test_win_loss_tie_is_zero():
    assert zero_sum_returns([-12.0, -12.0], PayoffMode.WIN_LOSS) == [0.0, 0.0]


def test_score_margin_antisymmetric_and_zero_sum():
    out = zero_sum_returns([-10.0, -25.0], PayoffMode.SCORE_MARGIN)
    assert out[0] == -out[1]            # antisymmetric
    assert math.isclose(sum(out), 0.0)  # zero-sum
    assert out[0] > 0                   # player 0 did better


def test_score_margin_clipped_to_unit_range():
    out = zero_sum_returns([-200.0, 0.0], PayoffMode.SCORE_MARGIN)
    assert out[0] == -1.0 and out[1] == 1.0
