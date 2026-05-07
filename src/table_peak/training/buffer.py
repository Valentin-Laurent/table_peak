"""On-policy trajectory buffer + Sample/Episode types."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from table_peak.games.base import Action, State
from table_peak.training.encoder import Encoder


@dataclass(frozen=True, slots=True)
class Sample:
    """One (state, action, return) triple from a single player's perspective."""

    state: State
    action: Action
    ret: float


type Episode = list[Sample]


class TrajectoryBuffer:
    """Collects per-step samples from self-play episodes; batches on demand."""

    def __init__(self) -> None:
        self._samples: list[Sample] = []

    def __len__(self) -> int:
        return len(self._samples)

    def add(self, episode: Episode) -> None:
        self._samples.extend(episode)

    def as_batch(
        self, encoder: Encoder
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        states = torch.stack([encoder.encode_flat(s.state) for s in self._samples])
        actions = torch.tensor([s.action for s in self._samples], dtype=torch.long)
        returns = torch.tensor([s.ret for s in self._samples], dtype=torch.float32)
        masks = torch.stack([encoder.encode_legal_mask(s.state) for s in self._samples])
        return states, actions, returns, masks
