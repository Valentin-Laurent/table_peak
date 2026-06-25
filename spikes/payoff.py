"""Pure transform: Skyjo raw (general-sum) returns -> 2-player zero-sum reward."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

# Loose normalization scale for the score-margin payoff. A 2-card-grid Skyjo
# round-score difference rarely exceeds this; the result is clipped to [-1, 1].
_MARGIN_SCALE = 100.0


class PayoffMode(StrEnum):
    WIN_LOSS = "win_loss"
    SCORE_MARGIN = "score_margin"


def zero_sum_returns(raw: Sequence[float], mode: PayoffMode) -> list[float]:
    """Map two raw Skyjo returns (higher == better) to a zero-sum reward pair."""
    if len(raw) != 2:
        raise ValueError(f"spike supports 2 players only, got {len(raw)}")
    r0, r1 = float(raw[0]), float(raw[1])
    if mode is PayoffMode.WIN_LOSS:
        if r0 > r1:
            return [1.0, -1.0]
        if r0 < r1:
            return [-1.0, 1.0]
        return [0.0, 0.0]
    margin = max(-1.0, min(1.0, (r0 - r1) / _MARGIN_SCALE))
    return [margin, -margin]
