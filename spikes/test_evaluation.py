from spikes.evaluation import aggregate_results


def test_aggregate_winrate_and_margin():
    # (my_return, opp_return) pairs across eval games
    games = [(-10.0, -25.0), (-30.0, -12.0), (-12.0, -12.0)]
    summary = aggregate_results(games)
    # 1 win, 1 loss, 1 tie -> win-rate counts ties as 0.5
    assert summary["win_rate"] == 0.5
    # mean margin = mean of (me - opp): 15 + (-18) + 0 = -3; mean = -1.0
    assert summary["mean_margin"] == -1.0
    assert summary["n_games"] == 3
