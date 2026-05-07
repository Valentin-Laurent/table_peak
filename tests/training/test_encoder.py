"""Encoder: State -> tensors in current-player perspective."""

from __future__ import annotations

import pytest
import torch

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.encoder import TTTEncoder


def test_encode_empty_board_p0_to_move() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state()  # P0 to move, empty board

    tensor = enc.encode(state)

    assert tensor.shape == (3, 3, 3)
    assert tensor.dtype == torch.float32
    # ch0 = mine (P0): all zeros. ch1 = opp (P1): all zeros. ch2 = empty: all ones.
    assert torch.equal(tensor[0], torch.zeros(3, 3))
    assert torch.equal(tensor[1], torch.zeros(3, 3))
    assert torch.equal(tensor[2], torch.ones(3, 3))


def test_encode_after_p0_plays_center_now_p1_to_move() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state().apply_action(4)  # P0 plays center; now P1 to move

    tensor = enc.encode(state)

    # current_player is now P1.
    # ch0 = mine (P1's pieces): all zeros (P1 hasn't played).
    # ch1 = opp (P0's pieces): 1 at center, 0 elsewhere.
    # ch2 = empty: 0 at center, 1 elsewhere.
    expected_opp = torch.zeros(3, 3)
    expected_opp[1, 1] = 1.0
    expected_empty = torch.ones(3, 3)
    expected_empty[1, 1] = 0.0
    assert torch.equal(tensor[0], torch.zeros(3, 3))
    assert torch.equal(tensor[1], expected_opp)
    assert torch.equal(tensor[2], expected_empty)


def test_encode_legal_mask_matches_legal_actions() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state().apply_action(4).apply_action(0)
    # board: P1 at 0, P0 at 4. Legal: 1, 2, 3, 5, 6, 7, 8.

    mask = enc.encode_legal_mask(state)

    assert mask.shape == (9,)
    assert mask.dtype == torch.bool
    expected = torch.tensor([False, True, True, True, False, True, True, True, True])
    assert torch.equal(mask, expected)


def test_encode_flat_returns_27d_view() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state()

    flat = enc.encode_flat(state)

    assert flat.shape == (27,)
    assert flat.dtype == torch.float32
    # First 9 (mine) zeros, next 9 (opp) zeros, last 9 (empty) ones.
    assert torch.equal(flat[:9], torch.zeros(9))
    assert torch.equal(flat[9:18], torch.zeros(9))
    assert torch.equal(flat[18:], torch.ones(9))


def test_encoder_protocol_runtime_check() -> None:
    from table_peak.training.encoder import Encoder

    assert isinstance(TTTEncoder(), Encoder)


def test_encode_raises_type_error_for_non_ttt_state() -> None:
    from typing import cast

    from table_peak.games.base import State

    # The encoder's isinstance guard short-circuits before any State method is
    # called, so FakeState's body can stay empty.
    class FakeState:
        pass

    enc = TTTEncoder()
    fake = cast(State, FakeState())
    with pytest.raises(TypeError, match="TTTEncoder expects TicTacToeState"):
        enc.encode(fake)
    with pytest.raises(TypeError, match="TTTEncoder expects TicTacToeState"):
        enc.encode_flat(fake)
    with pytest.raises(TypeError, match="TTTEncoder expects TicTacToeState"):
        enc.encode_legal_mask(fake)
