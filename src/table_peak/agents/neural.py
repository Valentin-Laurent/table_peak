"""NeuralAgent: inference-only policy backed by a PolicyValueNet + Encoder."""

from __future__ import annotations

import random

import torch

from table_peak.games.base import Action, State
from table_peak.training.encoder import Encoder
from table_peak.training.policy_net import PolicyValueNet


class NeuralAgent:
    """Wraps a PolicyValueNet + Encoder. Implements the Agent Protocol.

    temperature == 0 -> greedy argmax over masked logits.
    temperature  > 0 -> sample from softmax(logits / T) over legal actions.
    """

    def __init__(
        self,
        net: PolicyValueNet,
        encoder: Encoder,
        *,
        temperature: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self._net = net
        self._encoder = encoder
        self._temperature = float(temperature)
        self._rng = rng if rng is not None else random.Random()

    def act(self, state: State) -> Action:
        self._net.eval()
        with torch.no_grad():
            x = self._encoder.encode_flat(state).unsqueeze(0)
            logits, _ = self._net(x)
            mask = self._encoder.encode_legal_mask(state).unsqueeze(0)
            masked = logits.masked_fill(~mask, float("-inf"))

        if self._temperature == 0.0:
            return int(masked.argmax(dim=-1).item())

        probs = torch.softmax(masked / self._temperature, dim=-1).squeeze(0).tolist()
        # rng.choices with weights matches torch.multinomial draws but stays in
        # Python's RNG so reproducibility is governed by the injected rng.
        return int(self._rng.choices(range(9), weights=probs, k=1)[0])
