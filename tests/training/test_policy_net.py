"""PolicyValueNet: tiny MLP with policy + value heads."""

from __future__ import annotations

import torch

from table_peak.training.policy_net import PolicyValueNet


def test_forward_shapes_for_batch() -> None:
    net = PolicyValueNet()
    batch = torch.zeros((4, 27))

    logits, value = net(batch)

    assert logits.shape == (4, 9)
    assert value.shape == (4, 1)


def test_value_is_bounded_in_minus_one_to_one() -> None:
    net = PolicyValueNet()
    # Use random inputs to span the input space.
    torch.manual_seed(0)
    batch = torch.randn((32, 27))

    _, value = net(batch)

    assert torch.all(value >= -1.0)
    assert torch.all(value <= 1.0)


def test_forward_is_deterministic_given_seed() -> None:
    torch.manual_seed(123)
    net1 = PolicyValueNet()
    torch.manual_seed(123)
    net2 = PolicyValueNet()
    batch = torch.zeros((1, 27))

    out1 = net1(batch)
    out2 = net2(batch)

    assert torch.equal(out1[0], out2[0])
    assert torch.equal(out1[1], out2[1])
