"""REINFORCE-with-baseline update step."""

from __future__ import annotations

import torch

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.buffer import Sample, TrajectoryBuffer
from table_peak.training.encoder import TTTEncoder
from table_peak.training.policy_net import PolicyValueNet
from table_peak.training.reinforce import update_step


def _toy_buffer() -> TrajectoryBuffer:
    """Cook up a small batch where the optimal action is always 'cell 0' with
    return +1.0 for the actor. Repeated training on this batch should reduce
    loss monotonically over a few steps."""
    state = TicTacToe().new_initial_state()
    buf = TrajectoryBuffer()
    buf.add(
        [
            Sample(state=state, action=0, ret=1.0),
            Sample(state=state, action=0, ret=1.0),
            Sample(state=state, action=0, ret=1.0),
            Sample(state=state, action=0, ret=1.0),
        ]
    )
    return buf


def test_update_step_returns_required_metric_keys() -> None:
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    buf = _toy_buffer()

    metrics = update_step(net, opt, buf, encoder=TTTEncoder(), value_coef=0.5, entropy_coef=0.01)

    for key in ("policy_loss", "value_loss", "entropy", "mean_return"):
        assert key in metrics


def test_update_step_produces_no_nan() -> None:
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    buf = _toy_buffer()

    metrics = update_step(net, opt, buf, encoder=TTTEncoder(), value_coef=0.5, entropy_coef=0.01)

    for v in metrics.values():
        assert not torch.isnan(torch.tensor(v))
        assert not torch.isinf(torch.tensor(v))


def test_repeated_updates_decrease_policy_loss_on_fixed_batch() -> None:
    """Sanity: training works. With a constant batch where action 0 is the
    only one ever taken with return +1, the policy must move probability mass
    onto action 0, which reduces -log p(a|s) and thus policy_loss."""
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-2)
    buf = _toy_buffer()
    enc = TTTEncoder()

    losses: list[float] = []
    for _ in range(20):
        metrics = update_step(net, opt, buf, encoder=enc, value_coef=0.5, entropy_coef=0.0)
        losses.append(metrics["policy_loss"])

    # Strict monotone-down isn't required; first should be larger than last.
    assert losses[0] > losses[-1]
    # And the last should be substantially smaller, e.g. half-or-less.
    assert losses[-1] <= losses[0] * 0.5
