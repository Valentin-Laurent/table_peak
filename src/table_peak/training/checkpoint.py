"""Checkpoint Port + file-backed adapter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import torch
from torch import nn


@runtime_checkable
class CheckpointStore(Protocol):
    """Port: persist and restore training state keyed by generation."""

    def save(
        self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer, step: int
    ) -> None: ...

    def load(self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer) -> int:
        """Load state into net and optimizer in place; return step."""
        ...

    def list_generations(self) -> list[int]: ...


class FileCheckpointStore:
    """Writes `gen_NNNN.pt` files under a root directory."""

    _PATTERN = re.compile(r"gen_(\d{4,})\.pt$")

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _path(self, gen: int) -> Path:
        return self._root / f"gen_{gen:04d}.pt"

    def save(self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer, step: int) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "net": net.state_dict(),
                "optimizer": optimizer.state_dict(),
                "step": step,
            },
            self._path(gen),
        )

    def load(self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer) -> int:
        payload = torch.load(self._path(gen), weights_only=True)
        net.load_state_dict(payload["net"])
        optimizer.load_state_dict(payload["optimizer"])
        return int(payload["step"])

    def list_generations(self) -> list[int]:
        if not self._root.exists():
            return []
        gens: list[int] = []
        for p in self._root.iterdir():
            m = self._PATTERN.match(p.name)
            if m:
                gens.append(int(m.group(1)))
        return sorted(set(gens))
