"""REINFORCE-with-baseline update step."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from table_peak.training.buffer import TrajectoryBuffer
from table_peak.training.encoder import Encoder


def update_step(
    net: nn.Module,
    optimizer: torch.optim.Optimizer,
    buffer: TrajectoryBuffer,
    *,
    encoder: Encoder,
    value_coef: float,
    entropy_coef: float,
) -> dict[str, float]:
    """One REINFORCE-with-baseline gradient step. Returns scalar metrics."""
    states, actions, returns, masks = buffer.as_batch(encoder)
    net.train()

    logits, values = net(states)
    masked_logits = logits.masked_fill(~masks, float("-inf"))
    log_probs = F.log_softmax(masked_logits, dim=-1)
    chosen_log_probs = log_probs.gather(-1, actions.unsqueeze(-1)).squeeze(-1)

    values_flat = values.squeeze(-1)
    advantages = returns - values_flat.detach()

    policy_loss = -(chosen_log_probs * advantages).mean()
    value_loss = F.mse_loss(values_flat, returns)
    # Entropy: -sum p log p, computed safely on the masked distribution.
    probs = log_probs.exp()
    entropy = -(probs * log_probs.clamp_min(-1e9)).sum(dim=-1).mean()

    loss = policy_loss + value_coef * value_loss - entropy_coef * entropy

    if torch.isnan(loss) or torch.isinf(loss):
        raise RuntimeError(f"Loss is non-finite: {loss.item()}")

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    return {
        "policy_loss": float(policy_loss.item()),
        "value_loss": float(value_loss.item()),
        "entropy": float(entropy.item()),
        "mean_return": float(returns.mean().item()),
    }
