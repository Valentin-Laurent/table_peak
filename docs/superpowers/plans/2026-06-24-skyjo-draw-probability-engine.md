# Skyjo Draw-Probability Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent <epic-id>`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.

**Goal:** Add a pure engine function that returns the probability distribution over the value of the next card drawn from the Skyjo deck, computed only from public information.

**Architecture:** One new module `src/table_peak/games/skyjo/odds.py` with a `DrawOdds` frozen value object (wraps the pmf, exposes pure-of-pmf query methods) and a `draw_odds(state)` function that derives the unseen-pool distribution from a `SkyjoState`. Odds are common knowledge, so there is no `viewer` parameter. Derived stats are methods on `DrawOdds` and never touch `state`.

**Tech Stack:** Python 3, `collections.Counter`, frozen dataclasses, pyspiel `SkyjoState`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-24-skyjo-draw-probability-engine-design.md`

---

## Background the engineer needs

- **Deck:** `src/table_peak/games/skyjo/deck.py` exposes `DECK_COMPOSITION: Mapping[int, int]` — card value → copies, summing to 150: `{-2: 5, -1: 10, 0: 15, 1..12: 10 each}`.
- **Grid** (`src/table_peak/games/skyjo/grid.py`): `grid.num_slots`, `grid.is_face_up(slot)`, `grid.value(slot)` (raises if face-down — never use on face-down), `grid.num_face_down`, and crucially `grid.face_up_values() -> dict[int, int]` returning `{slot_index: value}` for **only** the face-up slots. Use `.values()` of that to collect a player's visible cards without ever touching a hidden value.
- **State** (`src/table_peak/games/skyjo/state.py`):
  - `state._grids: list[Grid] | None` — `None` before dealing completes; a `Grid` per player otherwise.
  - `state._discard_pile: list[int]` — full discard pile, oldest first, top is `[-1]`. This is the perfect-recall discard history.
  - `state._remaining_deck_counts: Counter[int]` — the god's-eye draw-pile composition. **Do NOT read individual counts** (that leaks hidden draw-pile contents). Only `sum(state._remaining_deck_counts.values())` is allowed — that is the public draw-pile *size*.
  - `state._phase: Phase` — `Phase.MAIN_PLAY` is the normal pre-draw decision point.
- **Existing module style:** see `scoring.py` and `view.py` for frozen-dataclass + pure-function conventions. `view.py` already stores a `dict` field on a frozen dataclass (`scores: dict[int, int] | None`), so a `dict` pmf field on a frozen dataclass matches precedent.
- **Privacy invariant the tests must defend:** `draw_odds` reads only face-up grid values, the discard pile, and the draw-pile *size*. It must never call `grid.value()` on a face-down slot or read per-value entries of `_remaining_deck_counts`.

## File Structure

- **Create:** `src/table_peak/games/skyjo/odds.py` — `DrawOdds` value object + `draw_odds(state)`. Single responsibility: next-draw distribution.
- **Create:** `tests/games/skyjo/test_odds.py` — black-box tests.

## Test helper note

Tests need real `SkyjoState` instances. Build them via the registered game, mirroring existing Skyjo tests. Check `tests/games/skyjo/test_view.py` or `test_observer.py` for the exact construction helper already used in this suite (e.g. a `load_game`/`new_initial_state` + `apply_action` driver), and reuse that helper rather than inventing a new one. Where a test needs a precise pool, drive the state to a known point or assert against quantities derived from the state itself (face-up values + discard + draw-pile size), not hard-coded deal orders.

---

### Task 1: `DrawOdds` value object

**Files:**
- Create: `src/table_peak/games/skyjo/odds.py`
- Test: `tests/games/skyjo/test_odds.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/games/skyjo/test_odds.py
"""Black-box tests for the Skyjo draw-probability engine."""

from __future__ import annotations

import pytest

from table_peak.games.skyjo.odds import DrawOdds


def test_pmf_is_exposed_as_given():
    odds = DrawOdds(pmf={-2: 0.5, 5: 0.5})
    assert odds.pmf == {-2: 0.5, 5: 0.5}


def test_expected_value_is_probability_weighted_mean():
    odds = DrawOdds(pmf={-2: 0.25, 0: 0.5, 4: 0.25})
    # 0.25*-2 + 0.5*0 + 0.25*4 = 0.5
    assert odds.expected_value() == pytest.approx(0.5)


def test_prob_at_most_sums_probabilities_up_to_threshold_inclusive():
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    assert odds.prob_at_most(0) == pytest.approx(0.5)   # -2 and 0
    assert odds.prob_at_most(-2) == pytest.approx(0.2)  # only -2
    assert odds.prob_at_most(12) == pytest.approx(1.0)  # everything
    assert odds.prob_at_most(-3) == pytest.approx(0.0)  # nothing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/games/skyjo/test_odds.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'table_peak.games.skyjo.odds'` / cannot import `DrawOdds`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/table_peak/games/skyjo/odds.py
"""Skyjo draw-probability engine: the distribution over the next deck draw.

Odds are common knowledge — no player (owner included) sees any face-down value —
so this module takes the state only and exposes no per-player / viewer variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class DrawOdds:
    """Distribution over the value of the next card drawn from the deck.

    `pmf` maps each possible card value (a subset of -2..12) to its probability;
    keys with zero probability are omitted. All query methods are pure functions
    of `pmf` and never touch game state, so they cannot drift from the distribution.
    """

    pmf: Mapping[int, float]

    def expected_value(self) -> float:
        """Probability-weighted mean of the drawn card value."""
        return sum(value * prob for value, prob in self.pmf.items())

    def prob_at_most(self, threshold: int) -> float:
        """Probability the drawn value is <= threshold (inclusive).

        'Beats a discard top of value t' means drawing strictly less than t, i.e.
        callers use prob_at_most(t - 1).
        """
        return sum(prob for value, prob in self.pmf.items() if value <= threshold)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/games/skyjo/test_odds.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
git commit --no-verify -- src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
```

(Use `--no-verify` and explicit paths: pre-commit's stash step is not sandbox-writable in this environment; run `make check` / ruff+mypy manually instead — see Task 4.)

---

### Task 2: `draw_odds(state)` — normal-case pool model

**Files:**
- Modify: `src/table_peak/games/skyjo/odds.py`
- Test: `tests/games/skyjo/test_odds.py`

The pool is `DECK_COMPOSITION` minus every face-up grid card minus the entire discard pile. The next draw is uniform over this whole unseen pool (draw pile + face-down grid cells) by exchangeability. Invariant: `sum(pool) == draw_pile_size + total_face_down_cells`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/games/skyjo/test_odds.py
from collections import Counter

from table_peak.games.skyjo.deck import DECK_COMPOSITION
from table_peak.games.skyjo.odds import draw_odds

# Reuse the Skyjo state-construction helper already used in this test suite
# (see tests/games/skyjo/test_view.py / test_observer.py) to build `state`
# driven into Phase.MAIN_PLAY. Bind it here as `make_main_play_state()`.


def _expected_pool(state) -> Counter[int]:
    pool: Counter[int] = Counter(DECK_COMPOSITION)
    for grid in state._grids:
        for value in grid.face_up_values().values():
            pool[value] -= 1
    for value in state._discard_pile:
        pool[value] -= 1
    return +pool  # drop any zero/negative entries


def test_pmf_matches_unseen_pool_normalized():
    state = make_main_play_state()
    pool = _expected_pool(state)
    total = sum(pool.values())

    odds = draw_odds(state)

    assert odds.pmf.keys() == {v for v, n in pool.items() if n > 0}
    for value, count in pool.items():
        if count > 0:
            assert odds.pmf[value] == pytest.approx(count / total)


def test_pmf_sums_to_one():
    odds = draw_odds(make_main_play_state())
    assert sum(odds.pmf.values()) == pytest.approx(1.0)


def test_pool_size_invariant_holds():
    state = make_main_play_state()
    draw_pile_size = sum(state._remaining_deck_counts.values())
    face_down = sum(g.num_face_down for g in state._grids)

    pool = _expected_pool(state)

    assert sum(pool.values()) == draw_pile_size + face_down
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/games/skyjo/test_odds.py -k "pool or sums_to_one" -v`
Expected: FAIL — `cannot import name 'draw_odds'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/table_peak/games/skyjo/odds.py`:

```python
from collections import Counter
from typing import TYPE_CHECKING

from table_peak.games.skyjo.deck import DECK_COMPOSITION

if TYPE_CHECKING:
    from table_peak.games.skyjo.state import SkyjoState


def _unseen_pool(state: SkyjoState) -> Counter[int]:
    """Multiset of cards the player has not seen: full deck minus every face-up
    grid card minus the entire discard pile. Equals draw pile + face-down grid
    cells. Reads only public information (never a face-down value, never per-value
    draw-pile counts)."""
    pool: Counter[int] = Counter(DECK_COMPOSITION)
    assert state._grids is not None, "draw_odds requires a dealt state"
    for grid in state._grids:
        for value in grid.face_up_values().values():
            pool[value] -= 1
    for value in state._discard_pile:
        pool[value] -= 1
    return pool


def draw_odds(state: SkyjoState) -> DrawOdds:
    """Distribution over the value of the next card drawn from the deck.

    Odds are common knowledge, so no viewer is needed. The next draw is uniform
    over the unseen pool (draw pile + face-down grid cells): a player cannot
    distinguish a draw-pile card from a face-down grid card, so by exchangeability
    the marginal next-draw ranges over the whole pool.
    """
    pool = _unseen_pool(state)
    total = sum(pool.values())
    pmf = {value: count / total for value, count in pool.items() if count > 0}
    return DrawOdds(pmf=pmf)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/games/skyjo/test_odds.py -v`
Expected: PASS (all tasks 1 + 2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
git commit --no-verify -- src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
```

---

### Task 3: Recycle-boundary handling (`draw_pile_size == 0`)

**Files:**
- Modify: `src/table_peak/games/skyjo/odds.py`
- Test: `tests/games/skyjo/test_odds.py`

When the draw pile is empty, the next draw recycles the discard (everything except the top card) into the draw pile and draws from it. The support is then exactly the known multiset `discard[:-1]`, uniform. This must override the general pool formula, which would otherwise normalize over face-down grid cells that are never drawn.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/games/skyjo/test_odds.py

def test_empty_draw_pile_uses_recycled_discard_minus_top():
    # Drive or construct a MAIN_PLAY state with an empty draw pile and a known
    # discard pile of >= 2 cards using the suite's state helper. Then:
    state = make_state_with_empty_draw_pile()  # discard pile e.g. [3, 3, 7, 1] (1 is top)
    assert sum(state._remaining_deck_counts.values()) == 0

    recycled = Counter(state._discard_pile[:-1])  # everything but the top
    total = sum(recycled.values())

    odds = draw_odds(state)

    assert odds.pmf.keys() == set(recycled.keys())
    for value, count in recycled.items():
        assert odds.pmf[value] == pytest.approx(count / total)
    assert sum(odds.pmf.values()) == pytest.approx(1.0)
```

If constructing an empty-draw-pile state through legal play is impractical in a
unit test, build the state via the suite helper and then set
`state._remaining_deck_counts = Counter()` with a chosen `state._discard_pile`
directly in the test (Arrange step only) — the function under test still reads
only public-size + discard, so this stays black-box at the API boundary.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/games/skyjo/test_odds.py -k recycled -v`
Expected: FAIL — current `draw_odds` normalizes over the full unseen pool (includes face-down grid cells), so the pmf keys/values won't match the discard-minus-top distribution.

- [ ] **Step 3: Write minimal implementation**

Update `draw_odds` in `src/table_peak/games/skyjo/odds.py`:

```python
def draw_odds(state: SkyjoState) -> DrawOdds:
    """Distribution over the value of the next card drawn from the deck.

    Odds are common knowledge, so no viewer is needed. The next draw is uniform
    over the unseen pool (draw pile + face-down grid cells): a player cannot
    distinguish a draw-pile card from a face-down grid card, so by exchangeability
    the marginal next-draw ranges over the whole pool.

    Recycle boundary: when the draw pile is empty, the next draw instead recycles
    the discard (all but the top card) and draws from it, so the support is the
    known multiset discard[:-1], uniform.
    """
    draw_pile_size = sum(state._remaining_deck_counts.values())
    if draw_pile_size == 0:
        recycled = Counter(state._discard_pile[:-1])
        total = sum(recycled.values())
        if total == 0:
            raise ValueError("no drawable cards: empty draw pile and no recyclable discard")
        pmf = {value: count / total for value, count in recycled.items()}
        return DrawOdds(pmf=pmf)

    pool = _unseen_pool(state)
    total = sum(pool.values())
    pmf = {value: count / total for value, count in pool.items() if count > 0}
    return DrawOdds(pmf=pmf)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/games/skyjo/test_odds.py -v`
Expected: PASS (all tests across tasks 1–3).

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
git commit --no-verify -- src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
```

---

### Task 4: Static checks + full suite

**Files:** none (verification only).

- [ ] **Step 1: Run the project gates manually**

Run: `make check` (or, if unavailable, `ruff check src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py && mypy src/table_peak/games/skyjo/odds.py`).
Expected: clean. **Watch for the known repo gotcha:** ruff selects `UP`; if any `class X(str, Enum)` pattern is introduced it triggers `UP042` (use `enum.StrEnum`) — not applicable here (no new enum), but apply `--fix` for import sorting (`I001`) if flagged.

- [ ] **Step 2: Run the full Skyjo test module**

Run: `pytest tests/games/skyjo/test_odds.py -v`
Expected: PASS, and confirm a non-zero collected count (a 0-collected run also exits 0 — verify the count).

- [ ] **Step 3: Run the broader Skyjo suite for regressions**

Run: `pytest tests/games/skyjo -q`
Expected: PASS — this task adds a module and touches nothing existing, so the rest of the suite must stay green.

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
git commit --no-verify -- src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
```

(Skip if Step 1 produced no changes.)

---

## Spec coverage check

- Common-knowledge / no viewer → Task 2 (`draw_odds(state)`, no viewer param).
- Whole-unseen-pool support + pool formula → Task 2 (`_unseen_pool`, `test_pmf_matches_unseen_pool_normalized`).
- Reads only public fields (no cheating) → Task 2 implementation + background privacy invariant; `face_up_values()` + discard + draw-pile size only.
- Pool-size invariant → Task 2 (`test_pool_size_invariant_holds`).
- Takes `SkyjoState` not the view → Task 2 signature.
- `DrawOdds` value object with `.pmf`, `.expected_value()`, `.prob_at_most()` → Task 1.
- `prob_at_most(t-1)` convention for "beats discard top" → documented in Task 1 docstring + tested in Task 1.
- Recycle boundary → Task 3.
- Module placement `games/skyjo/odds.py` → Tasks 1–3.
- Fresh post-deal pool test (150 − 2·num_players − 1) → covered by `test_pool_size_invariant_holds` on a post-deal MAIN_PLAY state; if a dedicated literal-count assertion is wanted, add it as an extra case in Task 2 Step 1.
