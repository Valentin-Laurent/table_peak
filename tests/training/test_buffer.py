"""TrajectoryBuffer: on-policy collection, batched on demand."""

from __future__ import annotations

import torch

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.buffer import Episode, Sample, TrajectoryBuffer
from table_peak.training.encoder import TTTEncoder


def _trivial_episode() -> Episode:
    state = TicTacToe().new_initial_state()
    s1 = state
    s2 = s1.apply_action(0)
    s3 = s2.apply_action(1)
    return [
        Sample(state=s1, action=0, ret=1.0),
        Sample(state=s2, action=1, ret=-1.0),
        Sample(state=s3, action=2, ret=1.0),
    ]


def test_empty_buffer_reports_zero_size() -> None:
    buf = TrajectoryBuffer()
    assert len(buf) == 0


def test_add_episode_increases_size_by_sample_count() -> None:
    buf = TrajectoryBuffer()
    buf.add(_trivial_episode())
    buf.add(_trivial_episode())
    assert len(buf) == 6


def test_as_batch_returns_tensors_of_correct_shape() -> None:
    buf = TrajectoryBuffer()
    buf.add(_trivial_episode())  # 3 samples
    buf.add(_trivial_episode())  # 3 more

    states, actions, returns, masks = buf.as_batch(TTTEncoder())

    assert states.shape == (6, 27)
    assert actions.shape == (6,)
    assert returns.shape == (6,)
    assert masks.shape == (6, 9)
    assert states.dtype == torch.float32
    assert actions.dtype == torch.long
    assert returns.dtype == torch.float32
    assert masks.dtype == torch.bool


def test_as_batch_preserves_action_and_return_order() -> None:
    buf = TrajectoryBuffer()
    ep = _trivial_episode()
    buf.add(ep)

    _, actions, returns, _ = buf.as_batch(TTTEncoder())

    assert actions.tolist() == [s.action for s in ep]
    assert returns.tolist() == [s.ret for s in ep]
