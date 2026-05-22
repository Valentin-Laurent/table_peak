"""Round-end scoring and doubling rules.

Round-ender penalty: if the round-ender's score is not strictly the lowest among all
players, it is doubled, with the result capped at zero: penalized = max(2 * raw, 0).
Tie at lowest triggers the doubling (rules-doc CHOSEN reading). The zero cap ensures
the penalty never improves a negative round-ender's score.
"""

from __future__ import annotations


def compute_round_scores(raw_scores: dict[int, int], *, round_ender: int) -> dict[int, int]:
    """Apply the round-ender doubling rule (with zero-cap) to raw per-player sums.

    `raw_scores` is the sum of face-up card values per player (after final reveal),
    with eliminated columns contributing 0.

    Returns a new dict with the penalty applied where appropriate.
    """
    if round_ender not in raw_scores:
        raise ValueError(f"round_ender {round_ender} not in raw_scores")
    ender_score = raw_scores[round_ender]
    others = [s for p, s in raw_scores.items() if p != round_ender]
    is_strictly_lowest = all(ender_score < s for s in others)
    if is_strictly_lowest:
        return dict(raw_scores)
    return {p: (max(s * 2, 0) if p == round_ender else s) for p, s in raw_scores.items()}
