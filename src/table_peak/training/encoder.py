"""Encoder Port + TTT encoder. Pure: State -> tensors in current-player perspective."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import torch

from table_peak.games.base import State
from table_peak.games.tic_tac_toe import TicTacToeState


@runtime_checkable
class Encoder(Protocol):
    """Port: turn a State into NN inputs from the current player's perspective."""

    def encode(self, state: State) -> torch.Tensor: ...

    def encode_flat(self, state: State) -> torch.Tensor: ...

    def encode_legal_mask(self, state: State) -> torch.Tensor: ...


class TTTEncoder:
    """3x3x3 channel encoding for TicTacToe.

    Channels: [mine, opp, empty] from state.current_player's perspective.
    Assumes exactly 2 players with IDs 0 and 1 (opp = 1 - me).
    """

    def _check_state(self, state: State) -> TicTacToeState:
        if not isinstance(state, TicTacToeState):
            raise TypeError(f"TTTEncoder expects TicTacToeState, got {type(state).__name__}")
        return state

    def encode(self, state: State) -> torch.Tensor:
        s = self._check_state(state)
        me = s.current_player
        opp = 1 - me
        mine = torch.tensor(
            [1.0 if c == me else 0.0 for c in s.board], dtype=torch.float32
        ).reshape(3, 3)
        opp_t = torch.tensor(
            [1.0 if c == opp else 0.0 for c in s.board], dtype=torch.float32
        ).reshape(3, 3)
        empty = torch.tensor(
            [1.0 if c == -1 else 0.0 for c in s.board], dtype=torch.float32
        ).reshape(3, 3)
        return torch.stack([mine, opp_t, empty], dim=0)

    def encode_flat(self, state: State) -> torch.Tensor:
        s = self._check_state(state)
        return self.encode(s).reshape(-1)

    def encode_legal_mask(self, state: State) -> torch.Tensor:
        s = self._check_state(state)
        legal = set(s.legal_actions())
        return torch.tensor([i in legal for i in range(len(s.board))], dtype=torch.bool)
