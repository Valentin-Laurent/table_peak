"""Action ID encoding/decoding and action-kind discriminators.

Disjoint integer ranges:
  [0, 66)    RevealInitial(i, j)            (unordered pairs over 12 slots)
  [66, 78)   TakeDiscardAndReplace(slot)
  78         DrawDeck (singleton)
  [79, 91)   ReplaceFromHand(slot)
  [91, 103)  DiscardAndFlip(slot)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

INITIAL_GRID_SLOTS = 12

# Region offsets
_REVEAL_INITIAL_BASE = 0
_TAKE_DISCARD_BASE = 66
_DRAW_DECK_ID = 78
_REPLACE_FROM_HAND_BASE = 79
_DISCARD_AND_FLIP_BASE = 91

NUM_DISTINCT_ACTIONS = 103


class ActionKind(Enum):
    REVEAL_INITIAL = "reveal_initial"
    TAKE_DISCARD_AND_REPLACE = "take_discard_and_replace"
    DRAW_DECK = "draw_deck"
    REPLACE_FROM_HAND = "replace_from_hand"
    DISCARD_AND_FLIP = "discard_and_flip"


@dataclass(frozen=True, slots=True)
class Action:
    kind: ActionKind
    slot: int = -1
    slot_a: int = -1
    slot_b: int = -1


# ---------- pair indexing for RevealInitial ----------


def _pair_index(i: int, j: int) -> int:
    """Lex index of the unordered pair {i, j} over [0, 12). i != j."""
    if i == j:
        raise ValueError("RevealInitial requires i != j")
    if not (0 <= i < INITIAL_GRID_SLOTS and 0 <= j < INITIAL_GRID_SLOTS):
        raise ValueError(f"slots out of range [0, {INITIAL_GRID_SLOTS})")
    a, b = (i, j) if i < j else (j, i)
    # number of pairs (x, y) with x < a is sum_{x=0}^{a-1} (11 - x) = a*(23 - a)/2
    return a * (2 * INITIAL_GRID_SLOTS - 1 - a) // 2 + (b - a - 1)


def _pair_from_index(idx: int) -> tuple[int, int]:
    if not (0 <= idx < 66):
        raise ValueError(f"reveal-initial index {idx} out of range [0, 66)")
    a = 0
    while True:
        block = INITIAL_GRID_SLOTS - 1 - a
        if idx < block:
            return a, a + 1 + idx
        idx -= block
        a += 1


# ---------- encoders ----------


def encode_reveal_initial(i: int, j: int) -> int:
    return _REVEAL_INITIAL_BASE + _pair_index(i, j)


def encode_take_discard_and_replace(slot: int) -> int:
    if not (0 <= slot < INITIAL_GRID_SLOTS):
        raise ValueError(f"slot {slot} out of range")
    return _TAKE_DISCARD_BASE + slot


def encode_draw_deck() -> int:
    return _DRAW_DECK_ID


def encode_replace_from_hand(slot: int) -> int:
    if not (0 <= slot < INITIAL_GRID_SLOTS):
        raise ValueError(f"slot {slot} out of range")
    return _REPLACE_FROM_HAND_BASE + slot


def encode_discard_and_flip(slot: int) -> int:
    if not (0 <= slot < INITIAL_GRID_SLOTS):
        raise ValueError(f"slot {slot} out of range")
    return _DISCARD_AND_FLIP_BASE + slot


# ---------- decoder ----------


def decode(action_id: int) -> Action:
    if not (0 <= action_id < NUM_DISTINCT_ACTIONS):
        raise ValueError(f"action id {action_id} out of range [0, {NUM_DISTINCT_ACTIONS})")
    if action_id < _TAKE_DISCARD_BASE:
        a, b = _pair_from_index(action_id - _REVEAL_INITIAL_BASE)
        return Action(kind=ActionKind.REVEAL_INITIAL, slot_a=a, slot_b=b)
    if action_id < _DRAW_DECK_ID:
        return Action(kind=ActionKind.TAKE_DISCARD_AND_REPLACE, slot=action_id - _TAKE_DISCARD_BASE)
    if action_id == _DRAW_DECK_ID:
        return Action(kind=ActionKind.DRAW_DECK)
    if action_id < _DISCARD_AND_FLIP_BASE:
        return Action(kind=ActionKind.REPLACE_FROM_HAND, slot=action_id - _REPLACE_FROM_HAND_BASE)
    return Action(kind=ActionKind.DISCARD_AND_FLIP, slot=action_id - _DISCARD_AND_FLIP_BASE)


# ---------- pretty printing for _action_to_string ----------


def to_string(action_id: int) -> str:
    a = decode(action_id)
    if a.kind == ActionKind.REVEAL_INITIAL:
        return f"RevealInitial({a.slot_a},{a.slot_b})"
    if a.kind == ActionKind.TAKE_DISCARD_AND_REPLACE:
        return f"TakeDiscardAndReplace({a.slot})"
    if a.kind == ActionKind.DRAW_DECK:
        return "DrawDeck"
    if a.kind == ActionKind.REPLACE_FROM_HAND:
        return f"ReplaceFromHand({a.slot})"
    return f"DiscardAndFlip({a.slot})"
