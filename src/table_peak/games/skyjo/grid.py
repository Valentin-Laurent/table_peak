"""4x3 player grid: positions, face-up/face-down, column elimination.

Slot indexing convention: slot = row * num_columns + col.
The initial grid has num_columns=4 and 3 rows; column elimination shrinks num_columns
(slots are re-indexed 0..num_slots-1 in the same row-major order over surviving columns).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

NUM_ROWS = 3
INITIAL_NUM_COLUMNS = 4
INITIAL_NUM_SLOTS = NUM_ROWS * INITIAL_NUM_COLUMNS


@dataclass(frozen=True, slots=True)
class Grid:
    """Immutable player grid. All transitions return a new Grid.

    `_values[i]` holds the dealt/replaced value at slot i; valid only when `_face_up[i]`
    is True. (Values for face-down slots are also stored — Skyjo's defining property is
    that the OWNER cannot see them, but the engine knows them. Public access is gated
    via `value()` which raises on face-down slots.)
    """

    num_columns: int
    _values: tuple[int, ...]
    _face_up: tuple[bool, ...]

    # ---------- factories ----------

    @classmethod
    def from_dealt(cls, values: Sequence[int]) -> Grid:
        if len(values) != INITIAL_NUM_SLOTS:
            raise ValueError(f"expected {INITIAL_NUM_SLOTS} values, got {len(values)}")
        return cls(
            num_columns=INITIAL_NUM_COLUMNS,
            _values=tuple(values),
            _face_up=tuple(False for _ in values),
        )

    # ---------- accessors ----------

    @property
    def num_slots(self) -> int:
        return len(self._values)

    @property
    def num_face_up(self) -> int:
        return sum(self._face_up)

    @property
    def num_face_down(self) -> int:
        return self.num_slots - self.num_face_up

    def is_face_up(self, slot: int) -> bool:
        self._check_slot(slot)
        return self._face_up[slot]

    def value(self, slot: int) -> int:
        self._check_slot(slot)
        if not self._face_up[slot]:
            raise ValueError(f"slot {slot} is face-down — value not public")
        return self._values[slot]

    def hidden_value(self, slot: int) -> int:
        """Engine-only: return the underlying value regardless of face-up status. Used
        by SkyjoState to apply public reveals when actions resolve. Never expose to
        observers / public information state."""
        self._check_slot(slot)
        return self._values[slot]

    def face_down_slots(self) -> list[int]:
        return [i for i, up in enumerate(self._face_up) if not up]

    def face_up_values(self) -> dict[int, int]:
        pairs = zip(self._values, self._face_up, strict=True)
        return {i: v for i, (v, up) in enumerate(pairs) if up}

    # ---------- transitions ----------

    def reveal(self, slot: int) -> Grid:
        self._check_slot(slot)
        if self._face_up[slot]:
            raise ValueError(f"slot {slot} already face-up")
        face_up = list(self._face_up)
        face_up[slot] = True
        return replace(self, _face_up=tuple(face_up))

    def replace(self, slot: int, new_value: int) -> tuple[Grid, int]:
        """Replace the card at `slot` with `new_value` (face-up). Return (new_grid, old_value).

        The old card always goes to discard face-up, regardless of its prior face-up status.
        """
        self._check_slot(slot)
        old_value = self._values[slot]
        values = list(self._values)
        face_up = list(self._face_up)
        values[slot] = new_value
        face_up[slot] = True
        return replace(self, _values=tuple(values), _face_up=tuple(face_up)), old_value

    def try_eliminate_columns(self) -> tuple[Grid, list[tuple[int, int]]]:
        """If any column has 3 face-up cards of identical value, eliminate it (all columns
        meeting the criterion eliminate simultaneously).

        Returns (new_grid, eliminated) where `eliminated` is a list of
        (column_index_in_old_grid, common_card_value) pairs — callers route those
        values to the discard pile per the rules-doc elimination-ordering rule.
        """
        eliminated: list[tuple[int, int]] = []
        for col in range(self.num_columns):
            slots = [row * self.num_columns + col for row in range(NUM_ROWS)]
            if all(self._face_up[s] for s in slots):
                values = {self._values[s] for s in slots}
                if len(values) == 1:
                    eliminated.append((col, next(iter(values))))
        if not eliminated:
            return self, []
        eliminated_col_indices = {col for col, _ in eliminated}
        keep_cols = [c for c in range(self.num_columns) if c not in eliminated_col_indices]
        new_num_columns = len(keep_cols)
        new_values: list[int] = []
        new_face_up: list[bool] = []
        for row in range(NUM_ROWS):
            for col in keep_cols:
                old_slot = row * self.num_columns + col
                new_values.append(self._values[old_slot])
                new_face_up.append(self._face_up[old_slot])
        return (
            Grid(
                num_columns=new_num_columns,
                _values=tuple(new_values),
                _face_up=tuple(new_face_up),
            ),
            eliminated,
        )

    # ---------- internal ----------

    def _check_slot(self, slot: int) -> None:
        if not 0 <= slot < self.num_slots:
            raise ValueError(f"slot {slot} out of range [0, {self.num_slots})")
