"""PolicyValueNet: small MLP with policy and value heads. Pure forward pass."""

from __future__ import annotations

import torch
from torch import nn


class PolicyValueNet(nn.Module):
    """27 -> 64 -> 64, split into 9-logit policy head and tanh-bounded value head."""

    def __init__(self, hidden: int = 64) -> None:
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(27, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
        )
        self.policy_head = nn.Linear(hidden, 9)
        self.value_head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.trunk(x)
        logits = self.policy_head(h)
        value = torch.tanh(self.value_head(h))
        return logits, value
