# Skyjo open_spiel training spike — findings

Episode length (random vs random): median 55, max 119 (cap 2000).

## RL cells (signal gate: win-rate > 0.55 vs random)

| Algorithm | Payoff | Win-rate | Mean margin |
| --- | --- | --- | --- |
| NFSP | win_loss | 0.477 (fail) | -0.8 |
| NFSP | score_margin | 0.490 (fail) | +2.3 |
| DQN | win_loss | 0.665 (PASS) | +53.0 |
| DQN | score_margin | 0.745 (PASS) | +58.3 |

## Deep CFR feasibility

Verdict: **errored** after 2s —  File "/Users/valentinlaurent/code/perso/table_peak/.venv/lib/python3.12/site-packages/torch/nn/modules/module.py", line 1762, in _call_impl
    return forward_call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/valentinlaurent/code/perso/table_peak/.venv/lib/python3.12/site-packages/torch/nn/modules/linear.py", line 125, in forward
    return F.linear(input, self.weight, self.bias)
                           ^^^^^^^^^^^
RecursionError: maximum recursion depth exceeded


