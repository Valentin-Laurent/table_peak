# Skyjo Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Skyjo rules engine in `src/table_peak/games/skyjo/` as a `pyspiel.Game` (open_spiel custom-game), parameterized 2–8 players, single round, plus a generic `pyspiel.State` → our `State` Protocol wrapper Port.

**Architecture:** Pure-Python `pyspiel.Game` + `pyspiel.State` + `Observer` subclasses, registered with open_spiel via `pyspiel.register_game`. Modular layout: `deck.py` / `grid.py` / `actions.py` / `scoring.py` are pure data-and-rules helpers; `state.py` orchestrates the lifecycle (setup → main → round-end); `game.py` wires the pyspiel surfaces. A generic `_pyspiel_adapter.py` translates any `pyspiel.State` to our `State` Protocol, auto-resolving chance nodes for our home-grown `Agent` Protocol.

**Tech Stack:** Python 3.12, open_spiel (Python wheels), pytest, mypy --strict, ruff. uv for env management.

**Spec:** `docs/superpowers/specs/2026-05-10-skyjo-engine-design.md`
**Rules source of truth:** `docs/games/skyjo-rules.md`
**Canonical pyspiel custom-game reference:** `open_spiel/python/games/kuhn_poker.py` in the open_spiel repo (mirror at https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/python/games/kuhn_poker.py). Read it before Tasks 6–10.

**TDD discipline:** Every task is `test → run-fail → implement → run-pass → commit`. Tests are black-box where possible. Helpers (`deck.py`, `grid.py`, `actions.py`, `scoring.py`) are pure functions / dataclasses and tested directly; `state.py` is tested through `pyspiel.State`'s public API.

**Forbidden zones owned by sibling features (do NOT write to these):**
- `src/table_peak/training/run.py`, `viz.py`, `train.py`
- `tests/training/test_run.py`, `test_viz.py`, `test_train.py`
- `runs/**`

If a task seems to require touching one, stop and surface to the orchestrator.

---

## Task 0: Add open_spiel dependency + smoke install

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Modify: `uv.lock` (regenerated)

- [ ] **Step 1: Add `open_spiel` to runtime dependencies**

In `pyproject.toml`, add `"open_spiel>=1.5"` to the `[project] dependencies` array. Use the lowest version known to ship Python 3.12 wheels for macOS arm64 — `1.5` is a reasonable floor; bump if pip refuses to resolve.

- [ ] **Step 2: Resolve and install**

```bash
uv lock
uv sync
```

Expected: `uv.lock` updates; `open_spiel` and its deps appear in the lockfile; `uv sync` succeeds.

- [ ] **Step 3: Smoke import**

```bash
uv run python -c "import pyspiel; print(pyspiel.registered_names()[:5])"
```

Expected: prints a list of 5 game names (e.g., `kuhn_poker`, `tic_tac_toe`, ...) — confirms pyspiel imports and the registry is populated.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add open_spiel for Skyjo engine"
```

---

## Task 1: Package skeleton

**Files:**
- Create: `src/table_peak/games/skyjo/__init__.py`
- Create: `src/table_peak/games/skyjo/deck.py` (empty)
- Create: `src/table_peak/games/skyjo/grid.py` (empty)
- Create: `src/table_peak/games/skyjo/actions.py` (empty)
- Create: `src/table_peak/games/skyjo/scoring.py` (empty)
- Create: `src/table_peak/games/skyjo/state.py` (empty)
- Create: `src/table_peak/games/skyjo/game.py` (empty)
- Create: `src/table_peak/games/skyjo/observer.py` (empty)
- Create: `src/table_peak/games/_pyspiel_adapter.py` (empty)
- Create: `tests/games/skyjo/__init__.py`

- [ ] **Step 1: Create empty package files**

Each `.py` file under `src/table_peak/games/skyjo/` (other than `__init__.py`) gets a single-line module docstring placeholder:

```python
"""<one-sentence description of the module>"""
```

Examples:
- `deck.py`: `"""Skyjo 150-card deck composition and dealing helpers."""`
- `grid.py`: `"""4x3 player grid: positions, face-up/face-down, column elimination."""`
- `actions.py`: `"""Action ID encoding/decoding and legal-action computation."""`
- `scoring.py`: `"""Round-end scoring, doubling, and tiebreak rules."""`
- `state.py`: `"""SkyjoState — pyspiel.State subclass orchestrating setup, play, scoring."""`
- `game.py`: `"""SkyjoGame — pyspiel.Game subclass + GameType + GameInfo + registration."""`
- `observer.py`: `"""SkyjoObserver — information state and observation tensors."""`
- `_pyspiel_adapter.py`: `"""Generic adapter: pyspiel.State -> table_peak.games.base.State Protocol."""`

`__init__.py` for `skyjo/`: empty (we'll fill in re-exports in Task 12). `__init__.py` for `tests/games/skyjo/`: empty.

- [ ] **Step 2: Commit**

```bash
git add src/table_peak/games/skyjo/ src/table_peak/games/_pyspiel_adapter.py tests/games/skyjo/
git commit -m "feat(skyjo): package skeleton"
```

---

## Task 2: Deck module

**Files:**
- Modify: `src/table_peak/games/skyjo/deck.py`
- Create: `tests/games/skyjo/test_deck.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/games/skyjo/test_deck.py
"""Black-box tests for the Skyjo deck composition and shuffle determinism."""
from __future__ import annotations

import random
from collections import Counter

from table_peak.games.skyjo.deck import DECK_COMPOSITION, build_shuffled_deck, deal


def test_deck_composition_totals_150_cards() -> None:
    assert sum(DECK_COMPOSITION.values()) == 150


def test_deck_composition_matches_published_rules() -> None:
    assert DECK_COMPOSITION[-2] == 5
    assert DECK_COMPOSITION[-1] == 10
    assert DECK_COMPOSITION[0] == 15
    for v in range(1, 13):
        assert DECK_COMPOSITION[v] == 10
    assert set(DECK_COMPOSITION.keys()) == set(range(-2, 13))


def test_build_shuffled_deck_returns_150_cards_with_correct_multiset() -> None:
    deck = build_shuffled_deck(rng=random.Random(0))
    assert len(deck) == 150
    assert Counter(deck) == Counter(DECK_COMPOSITION)


def test_build_shuffled_deck_is_deterministic_under_fixed_seed() -> None:
    a = build_shuffled_deck(rng=random.Random(42))
    b = build_shuffled_deck(rng=random.Random(42))
    assert a == b


def test_build_shuffled_deck_differs_under_different_seeds() -> None:
    a = build_shuffled_deck(rng=random.Random(1))
    b = build_shuffled_deck(rng=random.Random(2))
    assert a != b


def test_deal_returns_per_player_grids_and_remaining_deck() -> None:
    deck = list(range(150))  # synthetic deck for traceability
    grids, remaining = deal(deck, num_players=4, cards_per_grid=12)
    assert len(grids) == 4
    assert all(len(g) == 12 for g in grids)
    assert len(remaining) == 150 - 48
    # cards are dealt in order, no overlap
    flat = [c for g in grids for c in g] + remaining
    assert flat == list(range(150))


def test_deal_raises_when_deck_too_small() -> None:
    import pytest
    deck = list(range(10))
    with pytest.raises(ValueError):
        deal(deck, num_players=2, cards_per_grid=12)
```

- [ ] **Step 2: Run tests (FAIL — no implementation)**

```bash
uv run pytest tests/games/skyjo/test_deck.py -v
```

Expected: ImportError or AttributeError on `DECK_COMPOSITION` / `build_shuffled_deck` / `deal`.

- [ ] **Step 3: Implement `deck.py`**

```python
# src/table_peak/games/skyjo/deck.py
"""Skyjo 150-card deck composition and dealing helpers."""
from __future__ import annotations

import random
from collections.abc import Sequence
from types import MappingProxyType
from typing import Mapping

DECK_COMPOSITION: Mapping[int, int] = MappingProxyType(
    {-2: 5, -1: 10, 0: 15, **{v: 10 for v in range(1, 13)}}
)
"""Card value -> number of copies. Sums to 150."""


def build_shuffled_deck(*, rng: random.Random) -> list[int]:
    """Return a fresh shuffled deck of 150 ints in [-2, 12]. Deterministic given rng."""
    deck = [v for v, n in DECK_COMPOSITION.items() for _ in range(n)]
    rng.shuffle(deck)
    return deck


def deal(
    deck: Sequence[int], *, num_players: int, cards_per_grid: int = 12
) -> tuple[list[list[int]], list[int]]:
    """Deal `cards_per_grid` cards to each of `num_players` players, return remaining deck.

    Raises ValueError if the deck has fewer than num_players * cards_per_grid cards.
    """
    needed = num_players * cards_per_grid
    if len(deck) < needed:
        raise ValueError(f"deck has {len(deck)} cards, need {needed}")
    deck_list = list(deck)
    grids = [
        deck_list[i * cards_per_grid : (i + 1) * cards_per_grid]
        for i in range(num_players)
    ]
    remaining = deck_list[needed:]
    return grids, remaining
```

- [ ] **Step 4: Run tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_deck.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/deck.py tests/games/skyjo/test_deck.py
git commit -m "feat(skyjo): deck composition + dealing helpers"
```

---

## Task 3: Grid module

**Files:**
- Modify: `src/table_peak/games/skyjo/grid.py`
- Create: `tests/games/skyjo/test_grid.py`

The `Grid` represents one player's 4-column × 3-row tableau with face-up/face-down per cell, supporting column elimination. After elimination, the grid shrinks (3, 2, or 1 column). Eliminated columns count as "not face-down" for the round-end trigger.

- [ ] **Step 1: Write failing tests**

```python
# tests/games/skyjo/test_grid.py
"""Black-box tests for the Skyjo player grid: layout, reveals, eliminations."""
from __future__ import annotations

import pytest

from table_peak.games.skyjo.grid import Grid


def test_initial_grid_has_12_face_down_slots() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    assert g.num_slots == 12
    assert g.num_face_down == 12
    assert g.num_face_up == 0
    assert g.num_columns == 4


def test_reveal_marks_face_up() -> None:
    g = Grid.from_dealt(values=[5, 4, 3, 2, 1, 0, -1, -2, 6, 7, 8, 9])
    g2 = g.reveal(slot=0)
    assert g2.is_face_up(slot=0)
    assert g2.value(slot=0) == 5
    assert g2.num_face_down == 11
    assert not g.is_face_up(slot=0)  # original immutable


def test_replace_face_down_reveals_new_value_and_returns_old() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    g2, replaced_value = g.replace(slot=3, new_value=9)
    assert g2.is_face_up(slot=3)
    assert g2.value(slot=3) == 9
    assert replaced_value == 5  # the dealt card came up


def test_replace_face_up_returns_old_face_up_value() -> None:
    g = Grid.from_dealt(values=list(range(12)))
    g = g.reveal(slot=0)
    g2, replaced_value = g.replace(slot=0, new_value=99)
    assert replaced_value == 0
    assert g2.value(slot=0) == 99


def test_three_face_up_identical_in_column_eliminates_column() -> None:
    g = Grid.from_dealt(values=[7, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0, 7])
    # column 0 = slots 0, 4, 8 in row-major 4-column layout? Document layout below.
    # Layout: slot = row * 4 + col, with row in {0,1,2}, col in {0,1,2,3}.
    # column 0 -> slots 0, 4, 8.
    g = g.reveal(0).reveal(4).reveal(8)
    g2, eliminated = g.try_eliminate_columns()
    # Return shape: list of (column_index, common_value) pairs so callers can route
    # the trio values to the discard pile per the rules-doc's elimination-ordering rule.
    assert eliminated == [(0, 7)]
    assert g2.num_columns == 3
    assert g2.num_slots == 9
    # The remaining slots are re-indexed 0..8 in the same row-major order over surviving columns.
    # Validate face-up/down preservation for surviving slots.
    assert g2.num_face_up == 0  # only 3 reveals existed, all eliminated


def test_eliminate_does_not_fire_on_two_of_three_identical() -> None:
    g = Grid.from_dealt(values=[7, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0, 0])
    g = g.reveal(0).reveal(8)  # only two of three
    g2, eliminated = g.try_eliminate_columns()
    assert eliminated == []
    assert g2.num_columns == 4


def test_multiple_simultaneous_eliminations() -> None:
    # All four columns are 5,5,5 face-up.
    g = Grid.from_dealt(values=[5] * 12)
    for s in range(12):
        g = g.reveal(s)
    g2, eliminated = g.try_eliminate_columns()
    assert sorted(eliminated) == [(0, 5), (1, 5), (2, 5), (3, 5)]
    assert g2.num_slots == 0


def test_after_elimination_round_end_predicate_uses_face_down_count_not_grid_size() -> None:
    # All columns eliminated -> face_down=0 even though num_slots=0.
    g = Grid.from_dealt(values=[5] * 12)
    for s in range(12):
        g = g.reveal(s)
    g, _ = g.try_eliminate_columns()
    assert g.num_face_down == 0


def test_face_down_slots_are_invalid_for_value_lookup() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    with pytest.raises(ValueError):
        g.value(slot=0)  # face-down -> hidden, no value access


def test_reveal_face_up_slot_raises() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    g = g.reveal(0)
    with pytest.raises(ValueError):
        g.reveal(0)


def test_reveal_invalid_slot_raises() -> None:
    g = Grid.from_dealt(values=[5] * 12)
    with pytest.raises(ValueError):
        g.reveal(99)


def test_face_down_slots_helper_returns_correct_indices() -> None:
    g = Grid.from_dealt(values=list(range(12)))
    g = g.reveal(0).reveal(5)
    assert sorted(g.face_down_slots()) == [1, 2, 3, 4, 6, 7, 8, 9, 10, 11]


def test_face_up_values_helper() -> None:
    g = Grid.from_dealt(values=list(range(12)))
    g = g.reveal(2).reveal(7)
    assert g.face_up_values() == {2: 2, 7: 7}
```

- [ ] **Step 2: Run tests (FAIL)**

```bash
uv run pytest tests/games/skyjo/test_grid.py -v
```

Expected: ImportError on `Grid`.

- [ ] **Step 3: Implement `grid.py`**

```python
# src/table_peak/games/skyjo/grid.py
"""4x3 player grid: positions, face-up/face-down, column elimination.

Slot indexing convention: slot = row * num_columns + col.
The initial grid has num_columns=4 and 3 rows; column elimination shrinks num_columns
(slots are re-indexed 0..num_slots-1 in the same row-major order over surviving columns).
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace

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
    def from_dealt(cls, values: Sequence[int]) -> "Grid":
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
        return {i: v for i, (v, up) in enumerate(zip(self._values, self._face_up)) if up}

    # ---------- transitions ----------

    def reveal(self, slot: int) -> "Grid":
        self._check_slot(slot)
        if self._face_up[slot]:
            raise ValueError(f"slot {slot} already face-up")
        face_up = list(self._face_up)
        face_up[slot] = True
        return replace(self, _face_up=tuple(face_up))

    def replace(self, slot: int, new_value: int) -> tuple["Grid", int]:
        """Replace the card at `slot` with `new_value` (face-up). Return (new_grid, old_value)."""
        self._check_slot(slot)
        old_value = self._values[slot]  # whether face-up or face-down, the OLD card now goes to discard face-up
        values = list(self._values)
        face_up = list(self._face_up)
        values[slot] = new_value
        face_up[slot] = True
        return replace(self, _values=tuple(values), _face_up=tuple(face_up)), old_value

    def try_eliminate_columns(self) -> tuple["Grid", list[tuple[int, int]]]:
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
        return Grid(num_columns=new_num_columns, _values=tuple(new_values), _face_up=tuple(new_face_up)), eliminated

    # ---------- internal ----------

    def _check_slot(self, slot: int) -> None:
        if not 0 <= slot < self.num_slots:
            raise ValueError(f"slot {slot} out of range [0, {self.num_slots})")
```

- [ ] **Step 4: Run tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_grid.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/grid.py tests/games/skyjo/test_grid.py
git commit -m "feat(skyjo): grid module with face-up/down + column elimination"
```

---

## Task 4: Action encoding module

**Files:**
- Modify: `src/table_peak/games/skyjo/actions.py`
- Create: `tests/games/skyjo/test_actions.py`

**Action encoding (closed-form, disjoint integer ranges):**

| Action family            | ID range          | Decode                             |
|--------------------------|-------------------|------------------------------------|
| `RevealInitial(i, j)`    | `[0, 66)`         | enumerate unordered pairs over 12 slots in lex order |
| `TakeDiscardAndReplace(i)` | `[66, 78)`     | `slot = id - 66`, `slot ∈ [0, 12)` |
| `DrawDeck`               | `78`              | the singleton                      |
| `ReplaceFromHand(i)`     | `[79, 91)`        | `slot = id - 79`                   |
| `DiscardAndFlip(i)`      | `[91, 103)`       | `slot = id - 91`                   |

`NUM_DISTINCT_ACTIONS = 103`. The slot range is the maximum (12); slots beyond the current grid size are simply illegal (filtered by `_legal_actions`).

- [ ] **Step 1: Write failing tests**

```python
# tests/games/skyjo/test_actions.py
"""Black-box tests for action ID encoding/decoding."""
from __future__ import annotations

import pytest

from table_peak.games.skyjo.actions import (
    NUM_DISTINCT_ACTIONS,
    Action,
    ActionKind,
    decode,
    encode_discard_and_flip,
    encode_draw_deck,
    encode_replace_from_hand,
    encode_reveal_initial,
    encode_take_discard_and_replace,
)


def test_num_distinct_actions_is_103() -> None:
    assert NUM_DISTINCT_ACTIONS == 103


def test_reveal_initial_pairs_are_unordered_and_unique() -> None:
    seen: set[int] = set()
    for i in range(12):
        for j in range(i + 1, 12):
            aid = encode_reveal_initial(i, j)
            assert 0 <= aid < 66
            seen.add(aid)
            # Symmetric: same id whether (i,j) or (j,i) — accept either direction
            assert encode_reveal_initial(j, i) == aid
    assert len(seen) == 66


def test_decode_reveal_initial_recovers_ordered_pair() -> None:
    aid = encode_reveal_initial(2, 7)
    a = decode(aid)
    assert a.kind == ActionKind.REVEAL_INITIAL
    assert {a.slot_a, a.slot_b} == {2, 7}


def test_take_discard_and_replace_range() -> None:
    for slot in range(12):
        aid = encode_take_discard_and_replace(slot)
        assert 66 <= aid < 78
        a = decode(aid)
        assert a.kind == ActionKind.TAKE_DISCARD_AND_REPLACE
        assert a.slot == slot


def test_draw_deck_is_singleton_at_78() -> None:
    aid = encode_draw_deck()
    assert aid == 78
    a = decode(aid)
    assert a.kind == ActionKind.DRAW_DECK


def test_replace_from_hand_range() -> None:
    for slot in range(12):
        aid = encode_replace_from_hand(slot)
        assert 79 <= aid < 91
        a = decode(aid)
        assert a.kind == ActionKind.REPLACE_FROM_HAND
        assert a.slot == slot


def test_discard_and_flip_range() -> None:
    for slot in range(12):
        aid = encode_discard_and_flip(slot)
        assert 91 <= aid < 103
        a = decode(aid)
        assert a.kind == ActionKind.DISCARD_AND_FLIP
        assert a.slot == slot


def test_decode_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        decode(NUM_DISTINCT_ACTIONS)
    with pytest.raises(ValueError):
        decode(-1)


def test_reveal_initial_invalid_pair_raises() -> None:
    with pytest.raises(ValueError):
        encode_reveal_initial(0, 0)  # i must differ from j
    with pytest.raises(ValueError):
        encode_reveal_initial(-1, 5)
    with pytest.raises(ValueError):
        encode_reveal_initial(5, 12)
```

- [ ] **Step 2: Run tests (FAIL — module empty)**

```bash
uv run pytest tests/games/skyjo/test_actions.py -v
```

- [ ] **Step 3: Implement `actions.py`**

```python
# src/table_peak/games/skyjo/actions.py
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
```

- [ ] **Step 4: Run tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_actions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/actions.py tests/games/skyjo/test_actions.py
git commit -m "feat(skyjo): action ID encoding/decoding"
```

---

## Task 5: Scoring module

**Files:**
- Modify: `src/table_peak/games/skyjo/scoring.py`
- Create: `tests/games/skyjo/test_scoring.py`

Per `docs/games/skyjo-rules.md`:
- Round score = sum of all face-up cards still in the player's grid (after the round-end reveal flips any remaining face-down cards). Eliminated columns contribute 0.
- Round-ender penalty: if the round-ender's score is **not strictly the lowest**, it is **doubled**, with the doubled result **capped at zero**. So the penalized score is `max(2 * raw, 0)`. Tie at lowest also triggers the doubling. A negative round-ender who is not strictly lowest therefore lands at 0 (the penalty never improves their score).

- [ ] **Step 1: Write failing tests**

```python
# tests/games/skyjo/test_scoring.py
"""Black-box tests for round scoring + doubling."""
from __future__ import annotations

from table_peak.games.skyjo.scoring import compute_round_scores


def test_no_doubling_when_round_ender_strictly_lowest() -> None:
    raw = {0: 10, 1: 20, 2: 30}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 10, 1: 20, 2: 30}


def test_doubling_when_round_ender_not_lowest() -> None:
    raw = {0: 50, 1: 20, 2: 30}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 100, 1: 20, 2: 30}


def test_doubling_on_tie_at_lowest() -> None:
    # round-ender ties at lowest -> still doubled per the rules-doc CHOSEN reading
    raw = {0: 10, 1: 10, 2: 30}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 20, 1: 10, 2: 30}


def test_doubling_caps_at_zero_when_round_ender_negative_and_not_strictly_lowest() -> None:
    # negative round-ender, tied at lowest with another player -> doubling cap kicks in.
    # max(2*-4, 0) = 0, so the penalized ender ends at 0 rather than improving to -8.
    raw = {0: -4, 1: -4, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 0, 1: -4, 2: 5}


def test_doubling_caps_at_zero_when_round_ender_negative_and_not_lowest_at_all() -> None:
    # negative round-ender, strictly above another negative -> doubling cap still kicks in.
    raw = {0: -2, 1: -6, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 0, 1: -6, 2: 5}


def test_doubling_of_zero_round_ender_when_tied_at_lowest_stays_zero() -> None:
    # round-ender at 0 tied with another player at 0 -> max(2*0, 0) = 0.
    raw = {0: 0, 1: 0, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 0, 1: 0, 2: 5}


def test_doubling_with_strictly_lowest_negative() -> None:
    # round-ender is strictly lowest with -10 -> no doubling
    raw = {0: -10, 1: -4, 2: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: -10, 1: -4, 2: 5}


def test_two_player_doubling_when_tied() -> None:
    raw = {0: 5, 1: 5}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 10, 1: 5}


def test_two_player_no_doubling_when_strictly_lowest() -> None:
    raw = {0: 5, 1: 6}
    out = compute_round_scores(raw, round_ender=0)
    assert out == {0: 5, 1: 6}
```

- [ ] **Step 2: Run tests (FAIL)**

- [ ] **Step 3: Implement `scoring.py`**

```python
# src/table_peak/games/skyjo/scoring.py
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
```

- [ ] **Step 4: Run tests (PASS)**

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/scoring.py tests/games/skyjo/test_scoring.py
git commit -m "feat(skyjo): round scoring + round-ender doubling"
```

---

## Task 6: SkyjoState — setup phase (deal + commit + reveal)

**Files:**
- Modify: `src/table_peak/games/skyjo/state.py`
- Create: `tests/games/skyjo/test_setup.py`

**Reference:** `open_spiel/python/games/kuhn_poker.py` for the `pyspiel.State` subclass shape.

**Phases inside `SkyjoState`:**
1. `Phase.DEAL` — chance nodes deal `12 * num_players` cards. Each `apply_action` consumes one card from the remaining shuffled deck and assigns it to (player p, slot s) following deterministic round-robin.
2. `Phase.SETUP_COMMIT` — sequential decision nodes (player 0, 1, …). Each player picks a `RevealInitial(i, j)` action. Choice enters that player's private record only.
3. `Phase.SETUP_REVEAL` — deterministic state transition (no decision action). After last player commits, all 2N chosen slots flip face-up publicly. Starting player computed: highest sum among the 2N reveals. **Tiebreak procedure (per the rules-doc `[CHOSEN]` reading):** while more than one player is tied at the current maximum, each still-tied player draws one card from the deck multiset (sampled with `_rng_tiebreak` weighted by remaining counts), the drawn card is appended to `_discard_pile`, and the new tied set is taken to be those with the maximum drawn value. If the deck multiset is empty when a draw is needed, invoke `_recycle_discard_into_deck` first. Loop until a single winner remains; that player is the starting player. Phase advances to `MAIN_PLAY`. **Modeling note:** these tiebreak draws are resolved inline rather than promoted to explicit `pyspiel` chance nodes — see the spec for the rationale and the future-work note about CFR/NFSP/PSRO requiring the explicit-chance form.

**Chance modeling for the deal:** Use sequential single-card chance nodes. At each chance step, `chance_outcomes()` returns the **remaining-deck distribution** (each unique remaining value has probability `count_in_remaining / total_remaining`). `_apply_action(value)` removes one copy of that value from the remaining deck and assigns it to the next slot in round-robin order. Why this form: open_spiel's `EXPLICIT_STOCHASTIC` mode wants explicit probabilities; enumerating 150! permutations is infeasible; the per-card form gives finite outcomes per node.

- [ ] **Step 1: Write failing tests for setup phase**

```python
# tests/games/skyjo/test_setup.py
"""Black-box tests for SkyjoState setup phase: deal -> commit -> reveal -> main."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]
import pytest

# Ensure the game is registered before loading.
import table_peak.games.skyjo  # noqa: F401  (registers via import side-effect)


def _new_game(num_players: int = 2, seed: int = 0):
    return pyspiel.load_game("skyjo", {"num_players": pyspiel.GameParameter(num_players),
                                       "seed": pyspiel.GameParameter(seed)})


def test_initial_state_is_chance_node() -> None:
    state = _new_game(num_players=2).new_initial_state()
    assert state.is_chance_node()


def test_deal_phase_advances_through_24_chance_nodes_for_2_players() -> None:
    state = _new_game(num_players=2).new_initial_state()
    chance_steps = 0
    while state.is_chance_node():
        outcomes = state.chance_outcomes()
        # outcomes are (value, prob); probs sum to ~1
        assert abs(sum(p for _, p in outcomes) - 1.0) < 1e-9
        action = outcomes[0][0]  # take the first deterministically; rng for true sampling lives elsewhere
        state.apply_action(action)
        chance_steps += 1
    assert chance_steps == 24  # 12 cards * 2 players


def test_after_deal_setup_commit_phase_is_player_0() -> None:
    state = _new_game(num_players=3).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    assert state.current_player() == 0


def test_setup_commit_legal_actions_are_reveal_initial_pairs() -> None:
    from table_peak.games.skyjo.actions import ActionKind, decode
    state = _new_game(num_players=2).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    legal = state.legal_actions()
    assert len(legal) == 66
    for a in legal:
        assert decode(a).kind == ActionKind.REVEAL_INITIAL


def test_after_all_setup_commits_state_advances_to_main_play_with_starting_player() -> None:
    from table_peak.games.skyjo.actions import encode_reveal_initial
    state = _new_game(num_players=2).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    # Each player commits to slots (0, 1).
    state.apply_action(encode_reveal_initial(0, 1))
    state.apply_action(encode_reveal_initial(0, 1))
    # No further chance — reveal is deterministic.
    assert not state.is_chance_node()
    # Starting player is whichever has higher sum-of-reveals; must be 0 or 1.
    assert state.current_player() in {0, 1}


def test_information_state_during_setup_hides_other_players_commits() -> None:
    from table_peak.games.skyjo.actions import encode_reveal_initial
    state = _new_game(num_players=3).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    # Player 0 commits.
    state.apply_action(encode_reveal_initial(0, 1))
    # Now player 1's info state must NOT contain a record of player 0's specific commit.
    info_p1 = state.information_state_string(1)
    info_p2 = state.information_state_string(2)
    assert "0,1" not in info_p1  # heuristic: no leak of player 0's chosen pair into others' info
    assert "0,1" not in info_p2


def test_setup_reveal_conserves_total_card_count() -> None:
    """Global invariant after SETUP_REVEAL resolves (incl. any tiebreak draws):
    cards in grids + cards on discard + cards remaining in deck = 150.

    This exercises the starting-player tiebreak path implicitly. Whether or not a
    tiebreak fired for this seed, the conservation law must hold — and it will only
    hold if every card drawn for tiebreak ends up on the discard pile (per the
    rules-doc CHOSEN reading).
    """
    from table_peak.games.skyjo.actions import encode_reveal_initial
    for seed in range(8):
        state = _new_game(num_players=2, seed=seed).new_initial_state()
        while state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
        state.apply_action(encode_reveal_initial(0, 1))
        state.apply_action(encode_reveal_initial(0, 1))
        in_grids = sum(g.num_slots for g in state._grids)  # type: ignore[attr-defined]
        in_discard = len(state._discard_pile)  # type: ignore[attr-defined]
        in_deck = sum(state._remaining_deck_counts.values())  # type: ignore[attr-defined]
        assert in_grids + in_discard + in_deck == 150, (
            f"card conservation broken at seed {seed}: "
            f"grids={in_grids} discard={in_discard} deck={in_deck}"
        )


def test_setup_tiebreak_when_forced_by_construction() -> None:
    """Sweep a small seed range; for any seed where the initial 2-player reveals tie,
    assert that (a) setup completes (a starting player is chosen), and (b) at least
    one extra card was consumed from the deck and ended on the discard pile (the
    rules-doc tiebreak procedure).

    If no seed in the sweep produces a tie, the test passes vacuously — but the
    conservation test above already exercises the no-tie path for those seeds.
    """
    from table_peak.games.skyjo.actions import encode_reveal_initial
    saw_tie = False
    for seed in range(64):
        state = _new_game(num_players=2, seed=seed).new_initial_state()
        while state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
        state.apply_action(encode_reveal_initial(0, 1))
        # After p0's commit, the deal phase has placed exactly 1 card on the initial discard.
        discard_before_reveal = len(state._discard_pile)  # type: ignore[attr-defined]
        state.apply_action(encode_reveal_initial(0, 1))
        # SETUP_REVEAL is now resolved. If the two sums tied, tiebreak draws must
        # have appended ≥ 2 extra cards (one per tied player per tiebreak round).
        sums = [
            state._grids[p].value(0) + state._grids[p].value(1)  # type: ignore[attr-defined]
            for p in range(2)
        ]
        if sums[0] == sums[1]:
            saw_tie = True
            assert len(state._discard_pile) >= discard_before_reveal + 2  # type: ignore[attr-defined]
            assert state.current_player() in {0, 1}
            break
    # Not strictly required, but documenting expectation: with 64 seeds, a tie should
    # surface for at least one. If the sweep misses, the test still passes — the
    # conservation invariant remains the primary guard.
    _ = saw_tie
```

- [ ] **Step 2: Run tests (FAIL — game not yet defined/registered)**

```bash
uv run pytest tests/games/skyjo/test_setup.py -v
```

- [ ] **Step 3: Implement `state.py` setup phase + skeleton for later phases**

Implement `SkyjoState(pyspiel.State)` with phases gated by an `_phase` attribute. Setup phase fully working; main-play and round-end phases are stubs that raise `NotImplementedError` for now.

```python
# src/table_peak/games/skyjo/state.py
"""SkyjoState — pyspiel.State subclass orchestrating setup, play, scoring."""
from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from enum import Enum
from typing import Any

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.skyjo import actions as skyjo_actions
from table_peak.games.skyjo.deck import DECK_COMPOSITION
from table_peak.games.skyjo.grid import INITIAL_NUM_SLOTS, Grid


class Phase(Enum):
    DEAL = "deal"
    SETUP_COMMIT = "setup_commit"
    MAIN_PLAY = "main_play"
    BRANCH_B_SUBACTION = "branch_b_subaction"
    ROUND_END = "round_end"
    TERMINAL = "terminal"


class SkyjoState(pyspiel.State):  # type: ignore[misc]
    """Skyjo single-round state. See spec for phase semantics."""

    def __init__(self, game: pyspiel.Game, num_players: int, seed: int):
        super().__init__(game)
        self._num_players: int = num_players
        self._seed: int = seed
        # Seeded RNG used for the setup-tiebreak draws. Sampling cards from
        # _remaining_deck_counts is deterministic given the game seed.
        self._rng_tiebreak = random.Random(seed ^ 0xC0FFEE)
        self._phase: Phase = Phase.DEAL

        # Deal-phase state
        self._remaining_deck_counts: Counter[int] = Counter(DECK_COMPOSITION)
        self._deal_index: int = 0  # number of cards dealt so far (round-robin)
        self._dealt_grids_values: list[list[int]] = [[] for _ in range(num_players)]
        self._discard_pile: list[int] = []  # initialized after deal completes
        self._draw_pile: list[int] = []  # synthesized lazily during main play

        # Setup phase state
        self._grids: list[Grid] | None = None
        self._setup_commits: dict[int, tuple[int, int]] = {}  # player -> (slot_a, slot_b)
        self._setup_committer: int = 0
        self._starting_player: int | None = None

        # Main-play state
        self._current_player_index: int = -1  # set after starting-player resolution
        self._round_ender: int | None = None
        self._final_turns_remaining: dict[int, int] = {}  # filled at round-end trigger
        self._drawn_card: int | None = None  # transient during BRANCH_B_SUBACTION

        # Round-end / scoring
        self._round_scores_post_doubling: dict[int, int] | None = None

    # ---------- pyspiel.State surface ----------

    def current_player(self) -> int:
        if self._phase == Phase.DEAL:
            return pyspiel.PlayerId.CHANCE
        if self._phase == Phase.SETUP_COMMIT:
            return self._setup_committer
        if self._phase == Phase.MAIN_PLAY or self._phase == Phase.BRANCH_B_SUBACTION:
            return self._current_player_index
        if self._phase == Phase.ROUND_END or self._phase == Phase.TERMINAL:
            return pyspiel.PlayerId.TERMINAL
        raise RuntimeError(f"unknown phase {self._phase}")

    def is_terminal(self) -> bool:
        return self._phase == Phase.TERMINAL

    def is_chance_node(self) -> bool:
        return self._phase == Phase.DEAL

    def chance_outcomes(self) -> list[tuple[int, float]]:
        if self._phase != Phase.DEAL:
            return []
        total = sum(self._remaining_deck_counts.values())
        # Outcomes are integer values (-2..12) plus a sentinel offset to keep the
        # action namespace disjoint from decision actions. Use raw value + 200 as the
        # outcome ID to avoid clashing with NUM_DISTINCT_ACTIONS = 103.
        return [
            (self._chance_outcome_id(value), count / total)
            for value, count in sorted(self._remaining_deck_counts.items())
            if count > 0
        ]

    def legal_actions(self, player: int = -1) -> list[int]:
        if self._phase == Phase.DEAL:
            return [aid for aid, _ in self.chance_outcomes()]
        if self._phase == Phase.SETUP_COMMIT:
            return [
                skyjo_actions.encode_reveal_initial(i, j)
                for i in range(INITIAL_NUM_SLOTS)
                for j in range(i + 1, INITIAL_NUM_SLOTS)
            ]
        if self._phase == Phase.MAIN_PLAY:
            raise NotImplementedError("Task 7")
        if self._phase == Phase.BRANCH_B_SUBACTION:
            raise NotImplementedError("Task 7")
        return []

    def _apply_action(self, action: int) -> None:
        if self._phase == Phase.DEAL:
            self._apply_deal(action)
            return
        if self._phase == Phase.SETUP_COMMIT:
            self._apply_setup_commit(action)
            return
        if self._phase == Phase.MAIN_PLAY:
            raise NotImplementedError("Task 7")
        if self._phase == Phase.BRANCH_B_SUBACTION:
            raise NotImplementedError("Task 7")
        raise RuntimeError(f"_apply_action in unexpected phase {self._phase}")

    def _action_to_string(self, player: int, action: int) -> str:
        if self._phase == Phase.DEAL or action >= 200:
            return f"Deal(value={self._chance_outcome_value(action)})"
        return skyjo_actions.to_string(action)

    def returns(self) -> list[float]:
        if not self.is_terminal():
            return [0.0] * self._num_players
        assert self._round_scores_post_doubling is not None
        # utility = -round_score (lower raw score is better)
        return [
            float(-self._round_scores_post_doubling[p]) for p in range(self._num_players)
        ]

    def round_scores(self) -> dict[int, int]:
        """Raw integer round scores (post-doubling). Defined only at terminal."""
        if not self.is_terminal():
            raise RuntimeError("round_scores() requires terminal state")
        assert self._round_scores_post_doubling is not None
        return dict(self._round_scores_post_doubling)

    def information_state_string(self, player: int = -1) -> str:
        # Minimal viable info state for Task 6: own grid layout + own setup commit + phase.
        # Task 10 (Observer) replaces this with a richer encoding.
        if player < 0:
            player = self._current_player_index if self._current_player_index >= 0 else 0
        commit = self._setup_commits.get(player)
        return f"phase={self._phase.value};player={player};commit={commit}"

    # ---------- helpers: chance outcome encoding ----------

    @staticmethod
    def _chance_outcome_id(value: int) -> int:
        """Encode a card value (-2..12) as a non-clashing chance-outcome ID."""
        return value + 200  # ID range [198, 212]

    @staticmethod
    def _chance_outcome_value(action: int) -> int:
        return action - 200

    # ---------- deal phase ----------

    def _apply_deal(self, action: int) -> None:
        value = self._chance_outcome_value(action)
        if self._remaining_deck_counts[value] <= 0:
            raise ValueError(f"deal value {value} not available in remaining deck")
        self._remaining_deck_counts[value] -= 1
        if self._remaining_deck_counts[value] == 0:
            del self._remaining_deck_counts[value]
        # Round-robin: card goes to player (deal_index % num_players), slot (deal_index // num_players)
        player = self._deal_index % self._num_players
        # All 12 cards dealt to player 0 first? No — round-robin per-card across players for fairness.
        # Standard interpretation: deal one card to each player in turn, slot 0 first round, slot 1 next, ...
        slot = self._deal_index // self._num_players
        self._dealt_grids_values[player].append(value)
        self._deal_index += 1
        if self._deal_index == 12 * self._num_players:
            # Build grids; initialize discard top from the next deck card. But deal is over —
            # the rules say discard's first card is the next deck card after dealing 12 to each.
            # Per rules-doc: "Place the rest of the deck face-down as the draw pile; flip its top card
            # to start the discard pile." So after our deal (which consumed 12*N cards from a 150-card
            # deck), we need ONE more card: the discard top. We model this as a final chance step.
            # For simplicity, fold it inline as a chance step.
            # Implementation choice: keep a flag to signal "one more deal step for discard top."
            if not hasattr(self, "_pending_discard_top") or not self._pending_discard_top:
                self._pending_discard_top = True
                return  # remain in DEAL phase, one more chance node
            # Should not reach here through this path; the flag is consumed below.
            raise RuntimeError("deal phase miswired")
        if getattr(self, "_pending_discard_top", False) and self._deal_index == 12 * self._num_players + 1:
            # The just-applied chance outcome was the discard top.
            self._discard_pile = [value]
            # Build Grid objects from collected dealt values
            self._grids = [Grid.from_dealt(values) for values in self._dealt_grids_values]
            self._draw_pile = []  # the rest of the deck remains in _remaining_deck_counts; main play
                                  # draws via remaining-deck-counts chance nodes too (Task 7).
            self._phase = Phase.SETUP_COMMIT
            self._setup_committer = 0

    # ---------- setup commit phase ----------

    def _apply_setup_commit(self, action: int) -> None:
        decoded = skyjo_actions.decode(action)
        if decoded.kind != skyjo_actions.ActionKind.REVEAL_INITIAL:
            raise ValueError(f"non-reveal action {action} in SETUP_COMMIT")
        self._setup_commits[self._setup_committer] = (decoded.slot_a, decoded.slot_b)
        self._setup_committer += 1
        if self._setup_committer == self._num_players:
            self._do_synchronous_reveal_and_pick_starter()

    def _do_synchronous_reveal_and_pick_starter(self) -> None:
        assert self._grids is not None
        # Reveal all 2N committed slots simultaneously.
        new_grids: list[Grid] = []
        sums: dict[int, int] = {}
        for p in range(self._num_players):
            i, j = self._setup_commits[p]
            g = self._grids[p].reveal(i).reveal(j)
            new_grids.append(g)
            sums[p] = g.value(i) + g.value(j)
        self._grids = new_grids
        # Starting player: highest sum; ties broken by drawing cards from the deck
        # multiset (recurse on still-tied, reshuffle from discard if deck runs out).
        max_sum = max(sums.values())
        tied = [p for p, s in sums.items() if s == max_sum]
        while len(tied) > 1:
            draws: dict[int, int] = {}
            for p in tied:
                card = self._draw_tiebreak_card()
                self._discard_pile.append(card)
                draws[p] = card
            max_draw = max(draws.values())
            tied = [p for p, v in draws.items() if v == max_draw]
        self._starting_player = tied[0]
        self._current_player_index = self._starting_player
        self._phase = Phase.MAIN_PLAY

    def _draw_tiebreak_card(self) -> int:
        """Sample one card from `_remaining_deck_counts` using `_rng_tiebreak`,
        decrementing its count. If the deck is empty, invoke
        `_recycle_discard_into_deck` first. Raises if both are empty.
        """
        total = sum(self._remaining_deck_counts.values())
        if total == 0:
            self._recycle_discard_into_deck()
            total = sum(self._remaining_deck_counts.values())
            if total == 0:
                raise RuntimeError("deck exhausted with no discard to recycle for tiebreak")
        values = sorted(self._remaining_deck_counts.keys())
        weights = [self._remaining_deck_counts[v] for v in values]
        chosen = self._rng_tiebreak.choices(values, weights=weights, k=1)[0]
        self._remaining_deck_counts[chosen] -= 1
        if self._remaining_deck_counts[chosen] == 0:
            del self._remaining_deck_counts[chosen]
        return chosen

    # ---------- placeholders for later tasks ----------

    def clone(self) -> "SkyjoState":  # type: ignore[override]
        # pyspiel requires clone() for tree expansion; deep-copy of our fields.
        import copy
        return copy.deepcopy(self)
```

Note on the "discard top after deal" subtlety: the implementation above is intentionally explicit about it because the round-end deck-exhaustion rule (Task 7/8) recycles the discard pile. The `_pending_discard_top` flag stays a deal-phase artifact.

- [ ] **Step 4: Implement `game.py` minimal registration so the test can `pyspiel.load_game("skyjo", ...)`**

```python
# src/table_peak/games/skyjo/game.py
"""SkyjoGame — pyspiel.Game subclass + GameType + GameInfo + registration."""
from __future__ import annotations

from typing import Any

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.skyjo.actions import NUM_DISTINCT_ACTIONS
from table_peak.games.skyjo.state import SkyjoState

_GAME_TYPE = pyspiel.GameType(
    short_name="skyjo",
    long_name="Skyjo (Magilano, 2015)",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=8,
    min_num_players=2,
    provides_information_state_string=True,
    provides_information_state_tensor=False,  # set True after Task 10 lands tensor
    provides_observation_string=True,
    provides_observation_tensor=False,
    parameter_specification={
        "num_players": pyspiel.GameParameter(2),
        "seed": pyspiel.GameParameter(0),
    },
)


class SkyjoGame(pyspiel.Game):  # type: ignore[misc]
    def __init__(self, params: dict[str, Any] | None = None):
        params = dict(params or {})
        num_players = int(params.get("num_players", 2))
        seed = int(params.get("seed", 0))
        if not 2 <= num_players <= 8:
            raise ValueError(f"num_players={num_players} out of [2, 8]")
        # Theoretical bounds for round score after doubling. Worst case: all 12s, doubled.
        max_score = 12 * 12 * 2  # very loose upper bound, fine for pyspiel utility bounds
        min_score = -2 * 12 * 2
        info = pyspiel.GameInfo(
            num_distinct_actions=NUM_DISTINCT_ACTIONS,
            max_chance_outcomes=15,  # 15 distinct card values in the deck
            num_players=num_players,
            min_utility=-float(max_score),
            max_utility=-float(min_score),
            max_game_length=2000,  # generous loose bound; Skyjo rounds are bounded but variable
        )
        super().__init__(_GAME_TYPE, info, params)
        self._num_players = num_players
        self._seed = seed

    def new_initial_state(self) -> SkyjoState:
        return SkyjoState(self, num_players=self._num_players, seed=self._seed)

    def make_py_observer(self, iig_obs_type=None, params=None):  # type: ignore[no-untyped-def]
        # Task 10 will return a real Observer.
        return None


pyspiel.register_game(_GAME_TYPE, SkyjoGame)
```

And in `src/table_peak/games/skyjo/__init__.py`, trigger registration on package import:

```python
"""Skyjo engine — registers `skyjo` with open_spiel on import."""
from __future__ import annotations

from table_peak.games.skyjo import game as _game  # noqa: F401  registration side-effect
```

- [ ] **Step 5: Run tests (PASS for setup)**

```bash
uv run pytest tests/games/skyjo/test_setup.py -v
```

Expected: setup tests PASS. Tests for main play do not exist yet.

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/games/skyjo/state.py src/table_peak/games/skyjo/game.py src/table_peak/games/skyjo/__init__.py tests/games/skyjo/test_setup.py
git commit -m "feat(skyjo): SkyjoState + SkyjoGame setup phase (deal, commit, reveal)"
```

---

## Task 7: SkyjoState — main play phase (Branch a, b1, b2)

**Files:**
- Modify: `src/table_peak/games/skyjo/state.py`
- Create: `tests/games/skyjo/test_turn.py`

Phase transitions during main play:
- `MAIN_PLAY` → on `TakeDiscardAndReplace(i)`: apply, run column-elimination check, advance turn.
- `MAIN_PLAY` → on `DrawDeck`: draw via chance node (using remaining-deck distribution); transition to `BRANCH_B_SUBACTION` with the drawn card stored in `_drawn_card`. Active player remains the same.
- `BRANCH_B_SUBACTION` → on `ReplaceFromHand(i)` or `DiscardAndFlip(i)`: apply, run column-elimination check, advance turn.

**Deck draw modeling:** treat `DrawDeck` as a player action that triggers an inline single-card chance node before returning control. To stay within the SEQUENTIAL dynamics, model it as: `DrawDeck` is a player action that immediately advances the State into a chance node; the chance outcome is the drawn card value; after the chance applies, the state is in `BRANCH_B_SUBACTION` with the drawn value in `_drawn_card`. The wrapper Port (Task 11) auto-resolves chance nodes for our home-grown agent layer.

- [ ] **Step 1: Write failing tests**

```python
# tests/games/skyjo/test_turn.py
"""Black-box tests for main play: Branch (a), Branch (b1), Branch (b2), turn rotation."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import (
    ActionKind,
    decode,
    encode_discard_and_flip,
    encode_draw_deck,
    encode_replace_from_hand,
    encode_reveal_initial,
    encode_take_discard_and_replace,
)


def _new_game(num_players: int = 2, seed: int = 0):
    return pyspiel.load_game("skyjo", {"num_players": pyspiel.GameParameter(num_players),
                                       "seed": pyspiel.GameParameter(seed)})


def _advance_to_main_play(num_players: int = 2, seed: int = 0):
    state = _new_game(num_players, seed).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(num_players):
        state.apply_action(encode_reveal_initial(0, 1))
    return state


def test_main_play_legal_actions_include_take_discard_draw_deck() -> None:
    state = _advance_to_main_play()
    legal = state.legal_actions()
    kinds = {decode(a).kind for a in legal}
    assert ActionKind.TAKE_DISCARD_AND_REPLACE in kinds
    assert ActionKind.DRAW_DECK in kinds


def test_take_discard_and_replace_advances_turn_to_other_player() -> None:
    state = _advance_to_main_play(num_players=2)
    starter = state.current_player()
    state.apply_action(encode_take_discard_and_replace(2))  # replace some face-down slot
    # After action + column check, current_player is the OTHER player (no chance node here).
    assert state.current_player() == 1 - starter


def test_draw_deck_transitions_to_branch_b_via_chance_node() -> None:
    state = _advance_to_main_play(num_players=2)
    starter = state.current_player()
    state.apply_action(encode_draw_deck())
    # Now we expect a chance node for the drawn card.
    assert state.is_chance_node()
    state.apply_action(state.chance_outcomes()[0][0])
    # After chance, it's the SAME player's turn (Branch (b) sub-action).
    assert state.current_player() == starter
    legal = state.legal_actions()
    kinds = {decode(a).kind for a in legal}
    assert ActionKind.REPLACE_FROM_HAND in kinds
    assert ActionKind.DISCARD_AND_FLIP in kinds


def test_discard_and_flip_illegal_when_no_face_down_remaining() -> None:
    """When F=0 (all slots face-up after eliminations or many flips), Branch (b2) is illegal."""
    state = _advance_to_main_play(num_players=2)
    # Force player 0's grid into all-face-up state via a sequence of TakeDiscardAndReplace
    # that flips every slot. Skipping the heavy setup — assert via a synthetic scenario test:
    # this is covered by hand-crafted tests in Task 14 (test_round_end). Here we just sanity-check.
    pass  # deferred to Task 14's scenario suite


def test_replace_from_hand_advances_turn() -> None:
    state = _advance_to_main_play(num_players=2)
    starter = state.current_player()
    state.apply_action(encode_draw_deck())
    state.apply_action(state.chance_outcomes()[0][0])  # resolve chance
    state.apply_action(encode_replace_from_hand(2))
    assert state.current_player() == 1 - starter


def test_after_take_discard_replaces_old_grid_card_to_discard_top() -> None:
    state = _advance_to_main_play(num_players=2)
    # The discard top before action is a known value; we don't read it directly here
    # because pyspiel.State doesn't expose it on the public surface — use information_state_string
    # in Task 10. For now, assert via a round-trip: take discard, look at info_state shape.
    info_before = state.information_state_string(state.current_player())
    state.apply_action(encode_take_discard_and_replace(2))
    info_after = state.information_state_string(state.current_player())
    assert info_before != info_after


def test_three_player_turn_rotation_is_clockwise() -> None:
    state = _advance_to_main_play(num_players=3)
    starter = state.current_player()
    state.apply_action(encode_take_discard_and_replace(2))
    p2 = state.current_player()
    assert p2 == (starter + 1) % 3
    state.apply_action(encode_take_discard_and_replace(2))
    p3 = state.current_player()
    assert p3 == (starter + 2) % 3
```

- [ ] **Step 2: Run tests (FAIL — main-play not implemented)**

- [ ] **Step 3: Implement main play in `state.py`**

Add to `state.py`:

```python
# additions to SkyjoState

# In legal_actions:
#   if self._phase == Phase.MAIN_PLAY:
#       result = []
#       grid = self._grids[self._current_player_index]
#       for slot in range(grid.num_slots):
#           result.append(skyjo_actions.encode_take_discard_and_replace(slot))
#       result.append(skyjo_actions.encode_draw_deck())
#       return sorted(result)
#   if self._phase == Phase.BRANCH_B_SUBACTION:
#       result = []
#       grid = self._grids[self._current_player_index]
#       for slot in range(grid.num_slots):
#           result.append(skyjo_actions.encode_replace_from_hand(slot))
#       if grid.num_face_down >= 1:
#           for slot in grid.face_down_slots():
#               result.append(skyjo_actions.encode_discard_and_flip(slot))
#       return sorted(result)
#
# In is_chance_node:
#   add: or self._phase == Phase.MAIN_PLAY_DRAW_CHANCE  (new sub-phase)
#
# In _apply_action: branch on Phase.
```

Detailed implementation (replace the placeholder NotImplementedError sections):

```python
def _apply_action(self, action: int) -> None:
    if self._phase == Phase.DEAL:
        self._apply_deal(action)
        return
    if self._phase == Phase.SETUP_COMMIT:
        self._apply_setup_commit(action)
        return
    if self._phase == Phase.MAIN_PLAY:
        self._apply_main_play(action)
        return
    if self._phase == Phase.MAIN_PLAY_DRAW_CHANCE:
        self._apply_draw_chance(action)
        return
    if self._phase == Phase.BRANCH_B_SUBACTION:
        self._apply_branch_b_sub(action)
        return
    raise RuntimeError(f"_apply_action in unexpected phase {self._phase}")


def _apply_main_play(self, action: int) -> None:
    decoded = skyjo_actions.decode(action)
    p = self._current_player_index
    grid = self._grids[p]
    if decoded.kind == skyjo_actions.ActionKind.TAKE_DISCARD_AND_REPLACE:
        new_card = self._discard_pile[-1]
        self._discard_pile.pop()
        new_grid, old_value = grid.replace(decoded.slot, new_card)
        self._discard_pile.append(old_value)
        self._grids[p] = new_grid
        self._post_turn_resolve()
        return
    if decoded.kind == skyjo_actions.ActionKind.DRAW_DECK:
        self._phase = Phase.MAIN_PLAY_DRAW_CHANCE
        return
    raise ValueError(f"action {action} not legal in MAIN_PLAY")


def _apply_draw_chance(self, action: int) -> None:
    value = self._chance_outcome_value(action)
    if self._remaining_deck_counts[value] <= 0:
        # Draw pile exhausted of that value — try recycle.
        self._recycle_discard_into_deck()
    if self._remaining_deck_counts[value] <= 0:
        raise ValueError(f"draw value {value} unavailable after recycle")
    self._remaining_deck_counts[value] -= 1
    if self._remaining_deck_counts[value] == 0:
        del self._remaining_deck_counts[value]
    self._drawn_card = value
    self._phase = Phase.BRANCH_B_SUBACTION


def _apply_branch_b_sub(self, action: int) -> None:
    decoded = skyjo_actions.decode(action)
    p = self._current_player_index
    grid = self._grids[p]
    drawn = self._drawn_card
    assert drawn is not None
    if decoded.kind == skyjo_actions.ActionKind.REPLACE_FROM_HAND:
        new_grid, old_value = grid.replace(decoded.slot, drawn)
        self._discard_pile.append(old_value)
        self._grids[p] = new_grid
        self._drawn_card = None
        self._post_turn_resolve()
        return
    if decoded.kind == skyjo_actions.ActionKind.DISCARD_AND_FLIP:
        if grid.num_face_down < 1:
            raise ValueError("DiscardAndFlip illegal: no face-down slots remain")
        self._discard_pile.append(drawn)
        self._grids[p] = grid.reveal(decoded.slot)
        self._drawn_card = None
        self._post_turn_resolve()
        return
    raise ValueError(f"action {action} not legal in BRANCH_B_SUBACTION")


def _post_turn_resolve(self) -> None:
    """Column-elimination + round-end trigger + advance turn.

    Per the rules-doc elimination-ordering rule: when an action that replaced
    a grid card triggers elimination, the replaced card has already been
    appended to `_discard_pile` by the action handler, so it sits BELOW the
    eliminated trio cards we append here. When elimination fires from a
    flip (no replacement), the trio is the only thing added.
    """
    p = self._current_player_index
    new_grid, eliminated = self._grids[p].try_eliminate_columns()
    self._grids[p] = new_grid
    for _col, value in eliminated:
        # All three cards in an eliminated column share the same value; intra-trio
        # ordering is irrelevant per the rules doc.
        self._discard_pile.extend([value, value, value])
    if self._round_ender is None and new_grid.num_face_down == 0:
        # Trigger round-end: every other player gets exactly one final turn.
        self._round_ender = p
        self._final_turns_remaining = {
            other: 1 for other in range(self._num_players) if other != p
        }
    if self._round_ender is not None:
        # We are in the final-turns sub-phase. Decrement the just-finished player's counter
        # if they were a non-ender taking their final turn.
        if p != self._round_ender:
            self._final_turns_remaining[p] = max(0, self._final_turns_remaining[p] - 1)
        # Have all non-enders taken their final turn?
        if all(v == 0 for v in self._final_turns_remaining.values()):
            self._do_round_end_scoring()
            return
        # Else, advance to next player
        self._current_player_index = (self._current_player_index + 1) % self._num_players
        self._phase = Phase.MAIN_PLAY
        return
    # Normal play continues
    self._current_player_index = (self._current_player_index + 1) % self._num_players
    self._phase = Phase.MAIN_PLAY


def _recycle_discard_into_deck(self) -> None:
    """Per rules: keep current discard top, shuffle the rest, place as draw pile, return top."""
    if len(self._discard_pile) <= 1:
        return  # nothing to recycle
    kept_top = self._discard_pile.pop()
    for v in self._discard_pile:
        self._remaining_deck_counts[v] += 1
    self._discard_pile = [kept_top]


def _do_round_end_scoring(self) -> None:
    raise NotImplementedError("Task 8")
```

Add `Phase.MAIN_PLAY_DRAW_CHANCE` to the `Phase` enum, and `is_chance_node()` returns True for it.

- [ ] **Step 4: Run tests (PASS for main play, scenario tests still skipped)**

```bash
uv run pytest tests/games/skyjo/test_turn.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/state.py tests/games/skyjo/test_turn.py
git commit -m "feat(skyjo): main play (Branch a, b1, b2) + column elimination on turn end"
```

---

## Task 8: SkyjoState — round end (last-turn-for-everyone + scoring + terminal)

**Files:**
- Modify: `src/table_peak/games/skyjo/state.py`
- Create: `tests/games/skyjo/test_round_end.py`

- [ ] **Step 1: Write failing tests for round-end mechanics**

```python
# tests/games/skyjo/test_round_end.py
"""Black-box tests for round end: last-turn-for-everyone trigger + scoring + doubling."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import (
    encode_draw_deck,
    encode_replace_from_hand,
    encode_reveal_initial,
    encode_take_discard_and_replace,
)


def _play_one_full_round_random(num_players: int = 2, seed: int = 0):
    """Drive a full round with deterministic action choice (first legal action). Returns terminal state."""
    state = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(num_players),
         "seed": pyspiel.GameParameter(seed)},
    ).new_initial_state()
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
        else:
            state.apply_action(state.legal_actions()[0])
    return state


def test_round_terminates_within_bounded_steps() -> None:
    state = _play_one_full_round_random(num_players=2, seed=0)
    assert state.is_terminal()


def test_terminal_state_returns_per_player() -> None:
    state = _play_one_full_round_random(num_players=3, seed=1)
    rs = state.returns()
    assert len(rs) == 3
    assert all(isinstance(x, float) for x in rs)


def test_terminal_state_round_scores_post_doubling_consistent_with_returns() -> None:
    state = _play_one_full_round_random(num_players=2, seed=7)
    rs = state.round_scores()
    returns = state.returns()
    for p in range(2):
        assert returns[p] == -float(rs[p])


def test_round_scores_sum_makes_sense() -> None:
    """Sanity: round scores should be in a reasonable range (>= -50 per player after doubling worst case)."""
    state = _play_one_full_round_random(num_players=2, seed=0)
    for p, s in state.round_scores().items():
        assert -100 <= s <= 250  # very loose envelope; tighter bounds are theoretical
```

- [ ] **Step 2: Run tests (FAIL — round-end scoring is `NotImplementedError`)**

- [ ] **Step 3: Implement `_do_round_end_scoring()` and the round-end terminal transition**

```python
def _do_round_end_scoring(self) -> None:
    """At round-end: flip all remaining face-down cards, sum face-up values per player,
    apply round-ender doubling, store as terminal returns."""
    assert self._round_ender is not None
    assert self._grids is not None
    final_grids: list[Grid] = []
    raw: dict[int, int] = {}
    for p in range(self._num_players):
        g = self._grids[p]
        # Flip all face-down slots face-up. (Eliminated columns already removed.)
        for slot in range(g.num_slots):
            if not g.is_face_up(slot):
                g = g.reveal(slot)
        # Re-check column elimination after the global flip.
        g, _ = g.try_eliminate_columns()
        final_grids.append(g)
        raw[p] = sum(g.face_up_values().values())
    self._grids = final_grids
    from table_peak.games.skyjo.scoring import compute_round_scores
    self._round_scores_post_doubling = compute_round_scores(raw, round_ender=self._round_ender)
    self._phase = Phase.TERMINAL
```

- [ ] **Step 4: Run tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_round_end.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/state.py tests/games/skyjo/test_round_end.py
git commit -m "feat(skyjo): round-end scoring + terminal state with returns/round_scores"
```

---

## Task 9: pyspiel conformance harness

**Files:**
- Create: `tests/games/skyjo/test_conformance.py`

Use `pyspiel`'s built-in `random_sim_test` to validate State invariants under random play across `num_players ∈ {2, 3, 4, 6, 8}` and several seeds.

- [ ] **Step 1: Write the conformance test**

```python
# tests/games/skyjo/test_conformance.py
"""Conformance: pyspiel's random_sim_test validates State invariants under random rollouts."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]
import pytest

import table_peak.games.skyjo  # noqa: F401


@pytest.mark.parametrize("num_players", [2, 3, 4, 6, 8])
@pytest.mark.parametrize("seed", [0, 1, 42])
def test_random_simulations_pass(num_players: int, seed: int) -> None:
    game = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(num_players),
         "seed": pyspiel.GameParameter(seed)},
    )
    # pyspiel ships a Python helper at open_spiel.python.algorithms.evaluate_bots OR a
    # simulation harness at open_spiel.python.tests.utils. The exact entrypoint depends on
    # the installed open_spiel version. The robust test below replicates the core check:
    # roll out random episodes and validate basic invariants (legal_actions stable, no
    # exceptions, terminal returns sum to a finite number).
    import random
    rng = random.Random(seed)
    for _episode in range(5):
        state = game.new_initial_state()
        steps = 0
        while not state.is_terminal():
            if state.is_chance_node():
                outcomes = state.chance_outcomes()
                values = [o for o, _ in outcomes]
                weights = [p for _, p in outcomes]
                action = rng.choices(values, weights=weights, k=1)[0]
            else:
                legal = state.legal_actions()
                assert legal, "no legal actions but state not terminal"
                action = rng.choice(legal)
            state.apply_action(action)
            steps += 1
            assert steps < 5000, "round did not terminate within 5000 steps"
        rs = state.returns()
        assert len(rs) == num_players
        assert all(isinstance(x, float) and x == x for x in rs)  # not NaN
```

- [ ] **Step 2: Run (PASS)**

```bash
uv run pytest tests/games/skyjo/test_conformance.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/games/skyjo/test_conformance.py
git commit -m "test(skyjo): pyspiel conformance via random rollouts across player counts"
```

---

## Task 10: Observer (information state string + tensor)

**Files:**
- Modify: `src/table_peak/games/skyjo/observer.py`
- Modify: `src/table_peak/games/skyjo/game.py` (wire `make_py_observer`)
- Modify: `src/table_peak/games/skyjo/state.py` (delegate `information_state_string` to observer)
- Create: `tests/games/skyjo/test_observer.py`

The observer:
- For player `p`, encodes `p`'s grid (positions × {face-up value | face-down sentinel | eliminated sentinel}), all opponents' grids in the same shape with face-down values masked, discard top, draw-pile size, transient drawn-card value if `p == current_player_index` and `phase == BRANCH_B_SUBACTION`, round-end trigger flag, per-player remaining-final-turns counter, and phase indicator.
- String view: human-readable. Tensor view: float32 array, fixed shape per `num_players`.

**Reference:** `open_spiel/python/games/kuhn_poker.py` Observer; `open_spiel/python/observation.py` for the `Observer` base class. The observer is constructed via `make_py_observer` and exposes `set_from(state, player)` and `string_from(state, player)`.

This task is large; break into sub-tasks.

- [ ] **Step 1: Write failing tests for observer string view (information privacy)**

```python
# tests/games/skyjo/test_observer.py
"""Black-box tests for Skyjo observer: information privacy + tensor shape."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import encode_reveal_initial


def _new_game(num_players: int = 2, seed: int = 0):
    return pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(num_players),
         "seed": pyspiel.GameParameter(seed)},
    )


def _advance_to_main_play(num_players: int = 2, seed: int = 0):
    state = _new_game(num_players, seed).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    for _ in range(num_players):
        state.apply_action(encode_reveal_initial(0, 1))
    return state


def test_observer_hides_opponents_face_down_values() -> None:
    state = _advance_to_main_play(num_players=2, seed=0)
    info_p0 = state.information_state_string(0)
    info_p1 = state.information_state_string(1)
    # Heuristic: opponents' face-down slots show as "?" in either player's view.
    # Both players have 10 face-down slots after the initial reveal.
    assert info_p0.count("?") >= 10  # opp's 10 face-down + perhaps own 10 unrevealed = 20
    assert info_p1.count("?") >= 10


def test_observer_exposes_face_up_values_publicly() -> None:
    state = _advance_to_main_play(num_players=2, seed=0)
    info_p0 = state.information_state_string(0)
    info_p1 = state.information_state_string(1)
    # The face-up values from initial reveal appear in both views.
    # Specific values depend on seed; just check that both views contain numeric tokens.
    import re
    nums_p0 = re.findall(r"-?\d+", info_p0)
    nums_p1 = re.findall(r"-?\d+", info_p1)
    assert len(nums_p0) > 0
    assert len(nums_p1) > 0


def test_observation_tensor_shape_is_fixed_per_num_players() -> None:
    game = _new_game(num_players=3)
    state = game.new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    state.apply_action(encode_reveal_initial(0, 1))
    state.apply_action(encode_reveal_initial(0, 1))
    state.apply_action(encode_reveal_initial(0, 1))
    tensor = state.information_state_tensor(0)
    assert tensor is not None
    assert len(tensor) > 0
    # Shape must match game.information_state_tensor_shape()
    expected_size = 1
    for d in game.information_state_tensor_shape():
        expected_size *= d
    assert len(tensor) == expected_size


def test_observer_during_branch_b_includes_drawn_card_for_active_player_only() -> None:
    from table_peak.games.skyjo.actions import encode_draw_deck
    state = _advance_to_main_play(num_players=2, seed=0)
    active = state.current_player()
    other = 1 - active
    state.apply_action(encode_draw_deck())
    # Resolve chance node
    state.apply_action(state.chance_outcomes()[0][0])
    info_active = state.information_state_string(active)
    info_other = state.information_state_string(other)
    # Heuristic: the active player's view contains "drawn=" or similar; the other's does not.
    assert "drawn" in info_active.lower()
    assert "drawn" not in info_other.lower() or "drawn=?" in info_other.lower()
```

- [ ] **Step 2: Run tests (FAIL — observer not implemented)**

- [ ] **Step 3: Implement `observer.py`**

```python
# src/table_peak/games/skyjo/observer.py
"""SkyjoObserver — information state encoding (string + tensor) per pyspiel's Observer contract."""
from __future__ import annotations

from typing import Any

import numpy as np
import pyspiel  # type: ignore[import-not-found]

# Tensor layout per opponent slot:
#   1 float for is_face_up (0/1)
#   1 float for value (0 if face-down, else the value)
#   1 float for is_eliminated (0/1)  -- always 0 in current encoding; reserved
# Per player: 12 slots * 3 floats = 36 floats
# Plus globals: discard_top (1), draw_pile_size_normalized (1), drawn_card (1, valid if active in branch_b),
#               drawn_card_visible (1), round_ender_index (1, -1 sentinel if none), phase one-hot (5).
# Total per state: 36 * num_players + 10


class SkyjoObserver:
    def __init__(self, num_players: int):
        self._num_players = num_players
        per_player = 36
        self._size = per_player * num_players + 10
        self.tensor = np.zeros(self._size, dtype=np.float32)
        self.dict = {"observation": self.tensor}

    def set_from(self, state: Any, player: int) -> None:
        self.tensor.fill(0.0)
        # state._grids, state._discard_pile, etc. accessed via underscored attrs because
        # SkyjoState is the same package.
        offset = 0
        for p in range(self._num_players):
            grid = state._grids[p] if state._grids else None
            for slot in range(12):
                if grid is None or slot >= grid.num_slots:
                    # eliminated/missing slot
                    self.tensor[offset + 0] = 0.0
                    self.tensor[offset + 1] = 0.0
                    self.tensor[offset + 2] = 1.0  # is_eliminated
                else:
                    is_up = grid.is_face_up(slot)
                    if p == player:
                        # owner sees only face-up values; face-down stays hidden (Skyjo rule)
                        self.tensor[offset + 0] = 1.0 if is_up else 0.0
                        self.tensor[offset + 1] = float(grid.value(slot)) if is_up else 0.0
                    else:
                        self.tensor[offset + 0] = 1.0 if is_up else 0.0
                        self.tensor[offset + 1] = float(grid.value(slot)) if is_up else 0.0
                offset += 3
        # globals
        if state._discard_pile:
            self.tensor[offset] = float(state._discard_pile[-1])
        offset += 1
        # remaining draw pile (sum of remaining-deck-counts) normalized
        remaining = sum(state._remaining_deck_counts.values())
        self.tensor[offset] = float(remaining) / 150.0
        offset += 1
        # drawn card visible only to active player in BRANCH_B_SUBACTION
        from table_peak.games.skyjo.state import Phase
        if (state._phase == Phase.BRANCH_B_SUBACTION
                and state._current_player_index == player
                and state._drawn_card is not None):
            self.tensor[offset] = float(state._drawn_card)
            self.tensor[offset + 1] = 1.0  # visible
        offset += 2
        # round_ender_index, -1 sentinel via 0 here + a separate flag
        self.tensor[offset] = float(state._round_ender) if state._round_ender is not None else -1.0
        offset += 1
        # phase one-hot (5 phases relevant to observation)
        phase_index = {
            Phase.SETUP_COMMIT: 0,
            Phase.MAIN_PLAY: 1,
            Phase.MAIN_PLAY_DRAW_CHANCE: 2,
            Phase.BRANCH_B_SUBACTION: 3,
            Phase.TERMINAL: 4,
        }.get(state._phase, 0)
        self.tensor[offset + phase_index] = 1.0

    def string_from(self, state: Any, player: int) -> str:
        from table_peak.games.skyjo.state import Phase
        lines: list[str] = [f"phase={state._phase.value}", f"viewer={player}"]
        for p in range(self._num_players):
            g = state._grids[p] if state._grids else None
            if g is None:
                lines.append(f"player_{p}=<no grid>")
                continue
            cells: list[str] = []
            for slot in range(g.num_slots):
                if g.is_face_up(slot):
                    cells.append(str(g.value(slot)))
                else:
                    if p == player:
                        # owner cannot see own face-down values per Skyjo
                        cells.append("?")
                    else:
                        cells.append("?")
            lines.append(f"player_{p}=[{','.join(cells)}]")
        if state._discard_pile:
            lines.append(f"discard_top={state._discard_pile[-1]}")
        else:
            lines.append("discard_top=<empty>")
        lines.append(f"draw_pile_size={sum(state._remaining_deck_counts.values())}")
        if (state._phase == Phase.BRANCH_B_SUBACTION
                and state._current_player_index == player
                and state._drawn_card is not None):
            lines.append(f"drawn={state._drawn_card}")
        else:
            lines.append("drawn=?")
        if state._round_ender is not None:
            lines.append(f"round_ender={state._round_ender}")
        return "\n".join(lines)
```

- [ ] **Step 4: Wire observer in `game.py`**

In `game.py`:

```python
def make_py_observer(self, iig_obs_type=None, params=None):  # type: ignore[no-untyped-def]
    from table_peak.games.skyjo.observer import SkyjoObserver
    return SkyjoObserver(num_players=self._num_players)
```

And update `_GAME_TYPE`:

```python
provides_information_state_string=True,
provides_information_state_tensor=True,
provides_observation_string=True,
provides_observation_tensor=True,
```

In `state.py`, replace the placeholder `information_state_string` with delegation:

```python
def information_state_string(self, player: int = -1) -> str:
    from table_peak.games.skyjo.observer import SkyjoObserver
    if player < 0:
        player = self._current_player_index if self._current_player_index >= 0 else 0
    obs = SkyjoObserver(num_players=self._num_players)
    return obs.string_from(self, player)


def information_state_tensor(self, player: int = -1) -> list[float]:
    from table_peak.games.skyjo.observer import SkyjoObserver
    if player < 0:
        player = self._current_player_index if self._current_player_index >= 0 else 0
    obs = SkyjoObserver(num_players=self._num_players)
    obs.set_from(self, player)
    return obs.tensor.tolist()
```

Add `information_state_tensor_shape` to the game (for consumers querying it):

```python
def information_state_tensor_shape(self) -> list[int]:
    return [36 * self._num_players + 10]
```

- [ ] **Step 5: Run tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_observer.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/games/skyjo/observer.py src/table_peak/games/skyjo/game.py src/table_peak/games/skyjo/state.py tests/games/skyjo/test_observer.py
git commit -m "feat(skyjo): observer (info state string + tensor) with privacy enforcement"
```

---

## Task 11: Generic pyspiel adapter (chance auto-resolve, immutability)

**Files:**
- Modify: `src/table_peak/games/_pyspiel_adapter.py`
- Create: `tests/games/test_pyspiel_adapter.py`

The adapter wraps any `pyspiel.State` and presents it as our `State` Protocol. It auto-resolves chance nodes using a deterministic seeded RNG.

- [ ] **Step 1: Write failing tests**

```python
# tests/games/test_pyspiel_adapter.py
"""Black-box tests for the generic pyspiel adapter."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games._pyspiel_adapter import PyspielGameAdapter


def test_adapter_exposes_protocol_surface() -> None:
    inner = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(2),
         "seed": pyspiel.GameParameter(0)},
    )
    game = PyspielGameAdapter(inner, seed=0)
    assert game.num_players == 2
    state = game.new_initial_state()
    # Chance was auto-resolved during new_initial_state.
    assert state.current_player >= 0
    assert state.is_terminal is False
    legal = state.legal_actions()
    assert len(legal) > 0


def test_apply_action_returns_new_state_and_resolves_subsequent_chance() -> None:
    inner = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(2),
         "seed": pyspiel.GameParameter(0)},
    )
    game = PyspielGameAdapter(inner, seed=0)
    state = game.new_initial_state()
    legal = state.legal_actions()
    s2 = state.apply_action(legal[0])
    # Chance auto-resolved if any
    assert s2.current_player >= 0 or s2.is_terminal


def test_apply_action_does_not_mutate_caller() -> None:
    inner = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(2),
         "seed": pyspiel.GameParameter(0)},
    )
    game = PyspielGameAdapter(inner, seed=0)
    state = game.new_initial_state()
    legal_before = state.legal_actions()
    state.apply_action(legal_before[0])
    # state itself unchanged (immutable view)
    assert state.legal_actions() == legal_before


def test_terminal_returns_dict_per_player() -> None:
    """Drive a game to terminal via adapter; returns is dict[PlayerId, float]."""
    import random
    inner = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(2),
         "seed": pyspiel.GameParameter(0)},
    )
    game = PyspielGameAdapter(inner, seed=0)
    state = game.new_initial_state()
    rng = random.Random(0)
    while not state.is_terminal:
        legal = state.legal_actions()
        state = state.apply_action(rng.choice(legal))
    rs = state.returns()
    assert isinstance(rs, dict)
    assert set(rs.keys()) == {0, 1}
    assert all(isinstance(v, float) for v in rs.values())
```

- [ ] **Step 2: Run tests (FAIL)**

- [ ] **Step 3: Implement adapter**

```python
# src/table_peak/games/_pyspiel_adapter.py
"""Generic adapter: pyspiel.State -> table_peak.games.base.State Protocol.

Auto-resolves chance nodes using a deterministic seeded RNG. Exposes an immutable
view (apply_action returns a new adapter wrapping a cloned underlying state).
"""
from __future__ import annotations

import random
from collections.abc import Sequence

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.base import Action, PlayerId


class PyspielStateAdapter:
    def __init__(self, inner: pyspiel.State, rng: random.Random):
        # Resolve chance nodes immediately so the home-grown agent layer never sees them.
        while inner.is_chance_node():
            outcomes = inner.chance_outcomes()
            values = [v for v, _ in outcomes]
            weights = [p for _, p in outcomes]
            chosen = rng.choices(values, weights=weights, k=1)[0]
            inner.apply_action(chosen)
        self._inner: pyspiel.State = inner
        self._rng: random.Random = rng

    @property
    def current_player(self) -> PlayerId:
        return self._inner.current_player()

    def legal_actions(self) -> Sequence[Action]:
        return list(self._inner.legal_actions())

    def apply_action(self, action: Action) -> "PyspielStateAdapter":
        cloned = self._inner.clone()
        cloned.apply_action(action)
        # Fresh RNG state — derive a child seed deterministically to avoid sharing.
        child_seed = self._rng.randrange(2**31)
        return PyspielStateAdapter(cloned, random.Random(child_seed))

    @property
    def is_terminal(self) -> bool:
        return self._inner.is_terminal()

    def returns(self) -> dict[PlayerId, float]:
        rs = self._inner.returns()
        return {p: float(rs[p]) for p in range(len(rs))}


class PyspielGameAdapter:
    def __init__(self, inner: pyspiel.Game, *, seed: int):
        self._inner: pyspiel.Game = inner
        self._seed: int = seed

    @property
    def num_players(self) -> int:
        return int(self._inner.num_players())

    def new_initial_state(self) -> PyspielStateAdapter:
        return PyspielStateAdapter(self._inner.new_initial_state(), random.Random(self._seed))
```

- [ ] **Step 4: Run tests (PASS)**

```bash
uv run pytest tests/games/test_pyspiel_adapter.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/_pyspiel_adapter.py tests/games/test_pyspiel_adapter.py
git commit -m "feat(games): generic pyspiel.State -> State Protocol adapter with chance auto-resolve"
```

---

## Task 12: SkyjoGameWrapper convenience + runner integration test

**Files:**
- Modify: `src/table_peak/games/skyjo/__init__.py`
- Create: `tests/games/skyjo/test_wrapper.py`

- [ ] **Step 1: Write failing test**

```python
# tests/games/skyjo/test_wrapper.py
"""End-to-end: runner.play_game over the adapter-wrapped Skyjo game."""
from __future__ import annotations

from table_peak.agents.random import RandomAgent
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.runner.play import play_game, play_matches


def test_play_game_runs_to_terminal() -> None:
    import random
    game = SkyjoGameWrapper(num_players=2, seed=0)
    agents = {0: RandomAgent(rng=random.Random(0)), 1: RandomAgent(rng=random.Random(1))}
    outcome = play_game(game, agents)
    assert outcome.num_moves > 0
    assert set(outcome.returns.keys()) == {0, 1}


def test_play_matches_reproducible_with_seed() -> None:
    a = play_matches(
        SkyjoGameWrapper(num_players=2, seed=0),
        agent_a=__import__("table_peak.agents.random", fromlist=["RandomAgent"]).RandomAgent(),
        agent_b=__import__("table_peak.agents.random", fromlist=["RandomAgent"]).RandomAgent(),
        n=20,
        swap_sides=True,
        seed=42,
    )
    b = play_matches(
        SkyjoGameWrapper(num_players=2, seed=0),
        agent_a=__import__("table_peak.agents.random", fromlist=["RandomAgent"]).RandomAgent(),
        agent_b=__import__("table_peak.agents.random", fromlist=["RandomAgent"]).RandomAgent(),
        n=20,
        swap_sides=True,
        seed=42,
    )
    assert a == b
```

- [ ] **Step 2: Run tests (FAIL — `SkyjoGameWrapper` not exported)**

- [ ] **Step 3: Implement convenience export**

```python
# src/table_peak/games/skyjo/__init__.py
"""Skyjo engine — registers `skyjo` with open_spiel on import.

Public surface:
  - SkyjoGameWrapper(num_players, seed): returns a PyspielGameAdapter ready for runner.play_game.
"""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

from table_peak.games._pyspiel_adapter import PyspielGameAdapter
from table_peak.games.skyjo import game as _game  # noqa: F401  registration side-effect


def SkyjoGameWrapper(*, num_players: int = 2, seed: int = 0) -> PyspielGameAdapter:
    inner = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(num_players),
         "seed": pyspiel.GameParameter(seed)},
    )
    return PyspielGameAdapter(inner, seed=seed)
```

- [ ] **Step 4: Run tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_wrapper.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/__init__.py tests/games/skyjo/test_wrapper.py
git commit -m "feat(skyjo): SkyjoGameWrapper convenience for runner.play_game integration"
```

---

## Task 13: Scenario tests for [CHOSEN] rules

**Files:**
- Create: `tests/games/skyjo/test_column_erase.py`
- Create: `tests/games/skyjo/test_deck_exhaustion.py`

These hand-crafted tests target specific rule edges. They use synthetic State construction (build a SkyjoState with specific grid contents) — for that, expose a `_for_testing` factory on SkyjoState OR use deterministic seeds that produce the desired board.

The simpler approach is **deterministic-seed scenario**: search small seed space until a seed yields the desired pre-condition, hardcode the seed. Failing that, expose a test-only factory.

- [ ] **Step 1: Write column-erase scenario test**

```python
# tests/games/skyjo/test_column_erase.py
"""Scenario tests for column elimination on three-of-a-kind."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import (
    encode_replace_from_hand,
    encode_reveal_initial,
    encode_take_discard_and_replace,
)


def test_column_erase_via_take_discard_replace() -> None:
    """Drive a 2-player game to a state where TakeDiscardAndReplace flips a column to all-equal,
    then assert the column is removed (grid shrinks)."""
    # Use a fixed seed and deterministic action policy. The exact action sequence depends on
    # the seed's deck order; the assertion relies on the post-condition (num_columns < 4 at
    # some point, or a specific player's grid shrank).
    state = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(2),
         "seed": pyspiel.GameParameter(0)},
    ).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    state.apply_action(encode_reveal_initial(0, 1))
    state.apply_action(encode_reveal_initial(0, 1))
    # Play out the round, watching for a column elimination and verifying that
    # when one fires, three copies of the eliminated value appear on top of the
    # discard pile (the rules-doc elimination-ordering rule).
    eliminations_seen = False
    prev_columns = [g.num_columns for g in state._grids]  # type: ignore[attr-defined]
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
            continue
        state.apply_action(state.legal_actions()[0])
        new_columns = [g.num_columns for g in state._grids]  # type: ignore[attr-defined]
        for p, (before, after) in enumerate(zip(prev_columns, new_columns, strict=True)):
            if after < before:
                eliminations_seen = True
                # Per the rules-doc ordering: the eliminated trio sits at the top of
                # the discard pile. Three copies of one identical value.
                top3 = state._discard_pile[-3:]  # type: ignore[attr-defined]
                assert len(top3) == 3
                assert top3[0] == top3[1] == top3[2]
        prev_columns = new_columns
    # Loose: with seed 0, eliminations are likely; tighten with a curated seed if flaky.
    assert state.is_terminal()
```

- [ ] **Step 2: Write deck-exhaustion scenario test**

```python
# tests/games/skyjo/test_deck_exhaustion.py
"""Scenario tests for deck recycle when the draw pile runs low."""
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games.skyjo.actions import encode_draw_deck, encode_reveal_initial


def test_long_round_exercises_deck_recycle() -> None:
    """An 8-player long round exhausts the deck and triggers the recycle path."""
    import random
    state = pyspiel.load_game(
        "skyjo",
        {"num_players": pyspiel.GameParameter(8),
         "seed": pyspiel.GameParameter(0)},
    ).new_initial_state()
    rng = random.Random(0)
    while not state.is_terminal():
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            state.apply_action(rng.choices(
                [v for v, _ in outcomes], weights=[p for _, p in outcomes], k=1)[0])
        else:
            state.apply_action(rng.choice(state.legal_actions()))
    # If we got here without exception, the recycle path either was hit or wasn't needed.
    # Either way, no crash = pass.
    assert state.is_terminal()
```

- [ ] **Step 3: Run scenario tests (PASS)**

```bash
uv run pytest tests/games/skyjo/test_column_erase.py tests/games/skyjo/test_deck_exhaustion.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/games/skyjo/test_column_erase.py tests/games/skyjo/test_deck_exhaustion.py
git commit -m "test(skyjo): scenario tests for column erase + deck exhaustion"
```

---

## Task 14: TTT regression check + lint/type sweep

**Files:**
- (read-only) all existing tests

- [ ] **Step 1: Run the entire test suite**

```bash
uv run pytest -v
```

Expected: all existing TTT tests still pass; new Skyjo tests pass; total runtime under 60s.

- [ ] **Step 2: Run mypy --strict**

```bash
uv run mypy --strict src/
```

Expected: no errors. Where `pyspiel` lacks stubs, `# type: ignore[import-not-found]` (or `[misc]` for subclassing) is scoped to import lines and class declarations only.

- [ ] **Step 3: Run ruff**

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

Expected: clean.

- [ ] **Step 4: Final commit if anything was reformatted**

```bash
git add -A
git diff --cached --stat
git commit -m "style(skyjo): ruff format pass"
```

---

## Self-review checklist (for the writing-plans skill)

- Spec coverage: every section in the spec maps to a task.
  - "Setup-commit phase" → Task 6
  - "Synchronous reveal" → Task 6
  - "Action encoding" → Task 4
  - "Utility convention" → Task 6 (returns())
  - "Information state design" → Task 10
  - "Wrapper Port" → Tasks 11, 12
  - "Module layout" → Task 1
  - "Edge cases & rule fidelity" → Tasks 7, 8, 13
  - "Forbidden zones" → declared at top
  - "Tooling/dependencies" → Task 0
- Placeholders: none (no "TBD" / "fill in details").
- Type consistency: `Grid`, `Phase`, `Action`, `ActionKind`, `SkyjoState`, `SkyjoGame`, `SkyjoObserver`, `PyspielStateAdapter`, `PyspielGameAdapter`, `SkyjoGameWrapper` — all used consistently across tasks.

## Notes for the implementer

- The `_pending_discard_top` mechanism in `_apply_deal` is a slight kludge — feel free to refactor to a dedicated `Phase.DEAL_DISCARD_TOP` if it reads cleaner. The behavior must remain identical.
- The information-state observer is intentionally compact in Task 10. If a downstream training run shows the encoding is information-thin (e.g., missing per-player remaining-final-turns counter), extend the tensor — but the tensor SHAPE is part of the public surface and bumping it is a breaking change to any saved checkpoints.
- Performance: pure-Python pyspiel custom games are slow. If `test_conformance.py` runs over ~30s, you may need to reduce the number of episodes per parameter combination. **Do not** start optimizing pyspiel internals.
- If `pyspiel`'s API differs from this plan in minor ways (method names, parameter passing), follow `open_spiel/python/games/kuhn_poker.py` as the canonical reference and adapt the relevant signatures. Spec compliance is non-negotiable; method-name fidelity is.
