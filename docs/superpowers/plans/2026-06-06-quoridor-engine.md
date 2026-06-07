# Quoridor Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 2-player Quoridor engine as a registered OpenSpiel game, wrapped through `PyspielGameAdapter`, with conformance-focused tests and no UI or neural-training work.

**Architecture:** Build a new `src/table_peak/games/quoridor/` package with a thin `pyspiel.Game` / `pyspiel.State` shell over focused helpers for board geometry, action encoding, wall legality, and pawn-move generation. Keep the public integration surface small: `pyspiel.load_game("quoridor", {"seed": ...})` and `QuoridorGameWrapper(seed=...)` should be enough for the rest of the repo to use the engine through the existing `Game` / `State` protocol.

**Tech Stack:** Python 3.12, open_spiel / `pyspiel`, pytest, ruff, mypy --strict, existing `PyspielGameAdapter`, existing runner / random agents.

---

## File Structure

**New files:**
- `src/table_peak/games/quoridor/__init__.py` — import-time registration side effect + `QuoridorGameWrapper(seed=0)`.
- `src/table_peak/games/quoridor/actions.py` — stable int action encoding / decoding and `NUM_DISTINCT_ACTIONS`.
- `src/table_peak/games/quoridor/geometry.py` — `Cell`, `WallAnchor`, `Orientation`, board constants, and coordinate helpers.
- `src/table_peak/games/quoridor/walls.py` — wall-edge blocking, wall legality checks, and BFS path-condition helpers.
- `src/table_peak/games/quoridor/moves.py` — legal pawn-destination generation, including straight and lateral jumps.
- `src/table_peak/games/quoridor/state.py` — `QuoridorState`, turn flow, legal action enumeration, apply-action logic, terminal detection, returns.
- `src/table_peak/games/quoridor/game.py` — `QuoridorGame`, `GameType`, `GameInfo`, and registration.
- `tests/games/quoridor/test_actions.py` — codec / constants tests.
- `tests/games/quoridor/test_walls.py` — wall blocking, overlap / crossing, and path-condition tests.
- `tests/games/quoridor/test_moves.py` — pawn-move and jump-rule tests.
- `tests/games/quoridor/test_state.py` — registered-game initial-state, illegal-action, and terminal-return tests.
- `tests/games/quoridor/test_wrapper.py` — wrapper / runner / seeded random playout tests.

**Shared files intentionally left untouched unless unavoidable:**
- `src/table_peak/games/_pyspiel_adapter.py` — reused as-is.
- `src/table_peak/games/__init__.py` — currently empty; do not modify unless some import surface truly needs it.

---

## Task 1: Define Quoridor coordinates and action encoding

**Files:**
- Create: `src/table_peak/games/quoridor/geometry.py`
- Create: `src/table_peak/games/quoridor/actions.py`
- Test: `tests/games/quoridor/test_actions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/games/quoridor/test_actions.py`:

```python
from __future__ import annotations

from table_peak.games.quoridor.actions import (
    NUM_DISTINCT_ACTIONS,
    decode,
    encode_move,
    encode_wall,
)
from table_peak.games.quoridor.geometry import BOARD_SIZE, Cell, Orientation, WallAnchor


def test_move_actions_round_trip_through_codec() -> None:
    action = encode_move(Cell(col=4, row=1))
    decoded = decode(action)
    assert decoded.kind == "move"
    assert decoded.destination == Cell(col=4, row=1)
    assert decoded.anchor is None
    assert decoded.orientation is None


def test_wall_actions_round_trip_through_codec() -> None:
    action = encode_wall(WallAnchor(col=3, row=4), Orientation.VERTICAL)
    decoded = decode(action)
    assert decoded.kind == "wall"
    assert decoded.destination is None
    assert decoded.anchor == WallAnchor(col=3, row=4)
    assert decoded.orientation is Orientation.VERTICAL


def test_num_distinct_actions_covers_all_cells_and_wall_anchors() -> None:
    assert BOARD_SIZE == 9
    assert NUM_DISTINCT_ACTIONS == 81 + 64 + 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/games/quoridor/test_actions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'table_peak.games.quoridor'`.

- [ ] **Step 3: Write the minimal geometry and codec modules**

Create `src/table_peak/games/quoridor/geometry.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

BOARD_SIZE = 9
WALL_GRID_SIZE = 8


@dataclass(frozen=True, slots=True)
class Cell:
    col: int
    row: int


@dataclass(frozen=True, slots=True)
class WallAnchor:
    col: int
    row: int


class Orientation(str, Enum):
    HORIZONTAL = "h"
    VERTICAL = "v"


START_CELLS = {0: Cell(col=4, row=0), 1: Cell(col=4, row=8)}
GOAL_ROWS = {0: 8, 1: 0}


def cell_on_board(cell: Cell) -> bool:
    return 0 <= cell.col < BOARD_SIZE and 0 <= cell.row < BOARD_SIZE


def anchor_on_board(anchor: WallAnchor) -> bool:
    return 0 <= anchor.col < WALL_GRID_SIZE and 0 <= anchor.row < WALL_GRID_SIZE
```

Create `src/table_peak/games/quoridor/actions.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from table_peak.games.quoridor.geometry import BOARD_SIZE, Orientation, WallAnchor, Cell

MOVE_OFFSET = 0
HORIZONTAL_WALL_OFFSET = BOARD_SIZE * BOARD_SIZE
VERTICAL_WALL_OFFSET = HORIZONTAL_WALL_OFFSET + 64
NUM_DISTINCT_ACTIONS = VERTICAL_WALL_OFFSET + 64


@dataclass(frozen=True, slots=True)
class DecodedAction:
    kind: Literal["move", "wall"]
    destination: Cell | None = None
    anchor: WallAnchor | None = None
    orientation: Orientation | None = None


def encode_move(cell: Cell) -> int:
    return MOVE_OFFSET + cell.row * BOARD_SIZE + cell.col


def encode_wall(anchor: WallAnchor, orientation: Orientation) -> int:
    index = anchor.row * 8 + anchor.col
    if orientation is Orientation.HORIZONTAL:
        return HORIZONTAL_WALL_OFFSET + index
    return VERTICAL_WALL_OFFSET + index


def decode(action: int) -> DecodedAction:
    if 0 <= action < HORIZONTAL_WALL_OFFSET:
        col = action % BOARD_SIZE
        row = action // BOARD_SIZE
        return DecodedAction(kind="move", destination=Cell(col=col, row=row))
    if HORIZONTAL_WALL_OFFSET <= action < VERTICAL_WALL_OFFSET:
        index = action - HORIZONTAL_WALL_OFFSET
        return DecodedAction(
            kind="wall",
            anchor=WallAnchor(col=index % 8, row=index // 8),
            orientation=Orientation.HORIZONTAL,
        )
    if VERTICAL_WALL_OFFSET <= action < NUM_DISTINCT_ACTIONS:
        index = action - VERTICAL_WALL_OFFSET
        return DecodedAction(
            kind="wall",
            anchor=WallAnchor(col=index % 8, row=index // 8),
            orientation=Orientation.VERTICAL,
        )
    raise ValueError(f"Unknown Quoridor action id: {action}")
```

Create `src/table_peak/games/quoridor/__init__.py` with just:

```python
"""Quoridor package."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/games/quoridor/test_actions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/quoridor/__init__.py \
        src/table_peak/games/quoridor/geometry.py \
        src/table_peak/games/quoridor/actions.py \
        tests/games/quoridor/test_actions.py
git commit -m "feat(quoridor): add action and coordinate primitives"
```

---

## Task 2: Implement wall blocking and path-condition helpers

**Files:**
- Create: `src/table_peak/games/quoridor/walls.py`
- Test: `tests/games/quoridor/test_walls.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/games/quoridor/test_walls.py`:

```python
from __future__ import annotations

from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor
from table_peak.games.quoridor.walls import edge_blocked, is_wall_legal, path_exists


def test_horizontal_wall_blocks_vertical_step() -> None:
    horizontal = frozenset({WallAnchor(col=3, row=0)})
    assert edge_blocked(
        Cell(col=4, row=0),
        Cell(col=4, row=1),
        horizontal_walls=horizontal,
        vertical_walls=frozenset(),
    )


def test_crossing_wall_is_illegal() -> None:
    assert not is_wall_legal(
        anchor=WallAnchor(col=2, row=2),
        orientation=Orientation.HORIZONTAL,
        walls_remaining=10,
        pawns=(Cell(col=4, row=0), Cell(col=4, row=8)),
        horizontal_walls=frozenset(),
        vertical_walls=frozenset({WallAnchor(col=2, row=2)}),
    )


def test_path_exists_detects_fully_trapped_start_in_artificial_wall_layout() -> None:
    horizontal = frozenset({WallAnchor(col=3, row=0)})
    vertical = frozenset({WallAnchor(col=3, row=0), WallAnchor(col=4, row=0)})
    assert not path_exists(
        start=Cell(col=4, row=0),
        goal_row=8,
        horizontal_walls=horizontal,
        vertical_walls=vertical,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/games/quoridor/test_walls.py -v`
Expected: FAIL with `ModuleNotFoundError` for `table_peak.games.quoridor.walls`.

- [ ] **Step 3: Write `walls.py`**

Create `src/table_peak/games/quoridor/walls.py`:

```python
from __future__ import annotations

from collections import deque

from table_peak.games.quoridor.geometry import (
    BOARD_SIZE,
    Cell,
    GOAL_ROWS,
    Orientation,
    WallAnchor,
    anchor_on_board,
    cell_on_board,
)


def edge_blocked(
    a: Cell,
    b: Cell,
    *,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> bool:
    if a.col == b.col:
        lower_row = min(a.row, b.row)
        return (
            WallAnchor(col=a.col, row=lower_row) in horizontal_walls
            or WallAnchor(col=a.col - 1, row=lower_row) in horizontal_walls
        )
    left_col = min(a.col, b.col)
    return (
        WallAnchor(col=left_col, row=a.row) in vertical_walls
        or WallAnchor(col=left_col, row=a.row - 1) in vertical_walls
    )


def orthogonal_neighbors(
    cell: Cell,
    *,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> tuple[Cell, ...]:
    result: list[Cell] = []
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nxt = Cell(col=cell.col + dc, row=cell.row + dr)
        if cell_on_board(nxt) and not edge_blocked(
            cell,
            nxt,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            result.append(nxt)
    return tuple(result)


def path_exists(
    *,
    start: Cell,
    goal_row: int,
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> bool:
    queue: deque[Cell] = deque([start])
    seen = {start}
    while queue:
        cell = queue.popleft()
        if cell.row == goal_row:
            return True
        for nxt in orthogonal_neighbors(
            cell,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def is_wall_legal(
    *,
    anchor: WallAnchor,
    orientation: Orientation,
    walls_remaining: int,
    pawns: tuple[Cell, Cell],
    horizontal_walls: frozenset[WallAnchor],
    vertical_walls: frozenset[WallAnchor],
) -> bool:
    if walls_remaining <= 0 or not anchor_on_board(anchor):
        return False
    if orientation is Orientation.HORIZONTAL:
        if anchor in horizontal_walls or anchor in vertical_walls:
            return False
        trial_horizontal = horizontal_walls | {anchor}
        trial_vertical = vertical_walls
    else:
        if anchor in vertical_walls or anchor in horizontal_walls:
            return False
        trial_horizontal = horizontal_walls
        trial_vertical = vertical_walls | {anchor}
    return all(
        path_exists(
            start=pawns[player],
            goal_row=GOAL_ROWS[player],
            horizontal_walls=trial_horizontal,
            vertical_walls=trial_vertical,
        )
        for player in (0, 1)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/games/quoridor/test_walls.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/quoridor/walls.py \
        tests/games/quoridor/test_walls.py
git commit -m "feat(quoridor): add wall legality helpers"
```

---

## Task 3: Implement pawn move generation, including jump rules

**Files:**
- Create: `src/table_peak/games/quoridor/moves.py`
- Test: `tests/games/quoridor/test_moves.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/games/quoridor/test_moves.py`:

```python
from __future__ import annotations

from table_peak.games.quoridor.geometry import Cell, WallAnchor
from table_peak.games.quoridor.moves import legal_pawn_destinations


def test_start_position_has_three_pawn_moves() -> None:
    assert set(
        legal_pawn_destinations(
            player=Cell(col=4, row=0),
            opponent=Cell(col=4, row=8),
            horizontal_walls=frozenset(),
            vertical_walls=frozenset(),
        )
    ) == {Cell(col=3, row=0), Cell(col=5, row=0), Cell(col=4, row=1)}


def test_adjacent_opponent_allows_straight_jump() -> None:
    legal = set(
        legal_pawn_destinations(
            player=Cell(col=4, row=0),
            opponent=Cell(col=4, row=1),
            horizontal_walls=frozenset(),
            vertical_walls=frozenset(),
        )
    )
    assert Cell(col=4, row=2) in legal


def test_blocked_straight_jump_turns_into_lateral_jumps() -> None:
    legal = set(
        legal_pawn_destinations(
            player=Cell(col=4, row=0),
            opponent=Cell(col=4, row=1),
            horizontal_walls=frozenset({WallAnchor(col=3, row=1)}),
            vertical_walls=frozenset(),
        )
    )
    assert Cell(col=4, row=2) not in legal
    assert Cell(col=3, row=1) in legal
    assert Cell(col=5, row=1) in legal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/games/quoridor/test_moves.py -v`
Expected: FAIL with `ModuleNotFoundError` for `table_peak.games.quoridor.moves`.

- [ ] **Step 3: Write `moves.py`**

Create `src/table_peak/games/quoridor/moves.py`:

```python
from __future__ import annotations

from table_peak.games.quoridor.geometry import Cell, cell_on_board
from table_peak.games.quoridor.walls import edge_blocked


def legal_pawn_destinations(
    *,
    player: Cell,
    opponent: Cell,
    horizontal_walls: frozenset,
    vertical_walls: frozenset,
) -> tuple[Cell, ...]:
    result: set[Cell] = set()
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        adjacent = Cell(col=player.col + dc, row=player.row + dr)
        if not cell_on_board(adjacent):
            continue
        if edge_blocked(
            player,
            adjacent,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            continue
        if adjacent != opponent:
            result.add(adjacent)
            continue

        straight = Cell(col=opponent.col + dc, row=opponent.row + dr)
        if cell_on_board(straight) and not edge_blocked(
            opponent,
            straight,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
        ):
            result.add(straight)
            continue

        for ldc, ldr in ((dr, dc), (-dr, -dc)):
            lateral = Cell(col=opponent.col + ldc, row=opponent.row + ldr)
            if cell_on_board(lateral) and not edge_blocked(
                opponent,
                lateral,
                horizontal_walls=horizontal_walls,
                vertical_walls=vertical_walls,
            ):
                result.add(lateral)
    return tuple(sorted(result, key=lambda cell: (cell.row, cell.col)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/games/quoridor/test_moves.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/quoridor/moves.py \
        tests/games/quoridor/test_moves.py
git commit -m "feat(quoridor): add pawn move generation"
```

---

## Task 4: Register the game and implement `QuoridorState`

**Files:**
- Create: `src/table_peak/games/quoridor/game.py`
- Create: `src/table_peak/games/quoridor/state.py`
- Modify: `src/table_peak/games/quoridor/__init__.py`
- Test: `tests/games/quoridor/test_state.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/games/quoridor/test_state.py`:

```python
from __future__ import annotations

import pytest
import pyspiel  # type: ignore[import-not-found]

import table_peak.games.quoridor  # noqa: F401
from table_peak.games.quoridor.actions import encode_move
from table_peak.games.quoridor.geometry import Cell


def test_registered_game_starts_with_player_zero_and_forward_move() -> None:
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    legal = set(state.legal_actions())
    assert state.current_player() == 0
    assert not state.is_terminal()
    assert encode_move(Cell(col=4, row=1)) in legal


def test_illegal_action_raises_value_error() -> None:
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    with pytest.raises(ValueError, match="Illegal action"):
        state.apply_action(encode_move(Cell(col=4, row=8)))


def test_straight_race_to_goal_row_returns_win_for_player_zero() -> None:
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    sequence = [
        Cell(col=4, row=1), Cell(col=3, row=8),
        Cell(col=4, row=2), Cell(col=4, row=8),
        Cell(col=4, row=3), Cell(col=3, row=8),
        Cell(col=4, row=4), Cell(col=4, row=8),
        Cell(col=4, row=5), Cell(col=3, row=8),
        Cell(col=4, row=6), Cell(col=4, row=8),
        Cell(col=4, row=7), Cell(col=3, row=8),
        Cell(col=4, row=8),
    ]
    for cell in sequence:
        state.apply_action(encode_move(cell))
    assert state.is_terminal()
    assert state.returns() == [1.0, -1.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/games/quoridor/test_state.py -v`
Expected: FAIL because `pyspiel.load_game("quoridor", ...)` is not registered yet.

- [ ] **Step 3: Write the game shell, state, and wrapper export**

Create `src/table_peak/games/quoridor/game.py`:

```python
from __future__ import annotations

from typing import Any

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.quoridor.actions import NUM_DISTINCT_ACTIONS
from table_peak.games.quoridor.state import QuoridorState

_GAME_TYPE = pyspiel.GameType(
    short_name="quoridor",
    long_name="Quoridor (Gigamic, 1997)",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=2,
    min_num_players=2,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=False,
    provides_observation_tensor=False,
    parameter_specification={"seed": 0},
)


class QuoridorGame(pyspiel.Game):  # type: ignore[misc]
    def __init__(self, params: dict[str, Any] | None = None):
        params = dict(params or {})
        seed = int(params.get("seed", 0))
        info = pyspiel.GameInfo(
            num_distinct_actions=NUM_DISTINCT_ACTIONS,
            max_chance_outcomes=0,
            num_players=2,
            min_utility=-1.0,
            max_utility=1.0,
            max_game_length=200,
        )
        super().__init__(_GAME_TYPE, info, params)
        self._seed = seed

    def new_initial_state(self) -> QuoridorState:
        return QuoridorState(self, seed=self._seed)


pyspiel.register_game(_GAME_TYPE, QuoridorGame)
```

Create `src/table_peak/games/quoridor/state.py`:

```python
from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.quoridor.actions import decode, encode_move, encode_wall
from table_peak.games.quoridor.geometry import GOAL_ROWS, START_CELLS, Cell, Orientation, WallAnchor
from table_peak.games.quoridor.moves import legal_pawn_destinations
from table_peak.games.quoridor.walls import is_wall_legal


class QuoridorState(pyspiel.State):  # type: ignore[misc]
    def __init__(self, game: pyspiel.Game, seed: int):
        super().__init__(game)
        self._seed = seed
        self._current_player_index = 0
        self._pawn_positions = {0: START_CELLS[0], 1: START_CELLS[1]}
        self._walls_remaining = {0: 10, 1: 10}
        self._horizontal_walls: frozenset[WallAnchor] = frozenset()
        self._vertical_walls: frozenset[WallAnchor] = frozenset()
        self._winner: int | None = None

    def current_player(self) -> int:
        if self._winner is not None:
            return int(pyspiel.PlayerId.TERMINAL)
        return self._current_player_index

    def is_terminal(self) -> bool:
        return self._winner is not None

    def _legal_actions(self, player: int = -1) -> list[int]:
        if self.is_terminal():
            return []
        me = self._current_player_index
        other = 1 - me
        moves = [
            encode_move(cell)
            for cell in legal_pawn_destinations(
                player=self._pawn_positions[me],
                opponent=self._pawn_positions[other],
                horizontal_walls=self._horizontal_walls,
                vertical_walls=self._vertical_walls,
            )
        ]
        walls: list[int] = []
        for row in range(8):
            for col in range(8):
                anchor = WallAnchor(col=col, row=row)
                for orientation in (Orientation.HORIZONTAL, Orientation.VERTICAL):
                    if is_wall_legal(
                        anchor=anchor,
                        orientation=orientation,
                        walls_remaining=self._walls_remaining[me],
                        pawns=(self._pawn_positions[0], self._pawn_positions[1]),
                        horizontal_walls=self._horizontal_walls,
                        vertical_walls=self._vertical_walls,
                    ):
                        walls.append(encode_wall(anchor, orientation))
        return sorted(moves + walls)

    def _apply_action(self, action: int) -> None:
        legal = set(self._legal_actions())
        if action not in legal:
            raise ValueError(f"Illegal action {action} for player {self._current_player_index}")
        decoded = decode(action)
        if decoded.kind == "move":
            assert decoded.destination is not None
            self._pawn_positions[self._current_player_index] = decoded.destination
            if decoded.destination.row == GOAL_ROWS[self._current_player_index]:
                self._winner = self._current_player_index
            else:
                self._current_player_index = 1 - self._current_player_index
            return
        assert decoded.anchor is not None
        assert decoded.orientation is not None
        if decoded.orientation is Orientation.HORIZONTAL:
            self._horizontal_walls = self._horizontal_walls | {decoded.anchor}
        else:
            self._vertical_walls = self._vertical_walls | {decoded.anchor}
        self._walls_remaining[self._current_player_index] -= 1
        self._current_player_index = 1 - self._current_player_index

    def _action_to_string(self, player: int, action: int) -> str:
        decoded = decode(action)
        if decoded.kind == "move":
            assert decoded.destination is not None
            return f"MovePawn({decoded.destination.col},{decoded.destination.row})"
        assert decoded.anchor is not None
        assert decoded.orientation is not None
        return f"PlaceWall({decoded.anchor.col},{decoded.anchor.row},{decoded.orientation.value})"

    def returns(self) -> list[float]:
        if self._winner is None:
            return [0.0, 0.0]
        return [1.0, -1.0] if self._winner == 0 else [-1.0, 1.0]
```

Replace `src/table_peak/games/quoridor/__init__.py` with:

```python
"""Quoridor engine package."""

from __future__ import annotations

from table_peak.games.quoridor import game as _game  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/games/quoridor/test_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/quoridor/game.py \
        src/table_peak/games/quoridor/state.py \
        src/table_peak/games/quoridor/__init__.py \
        tests/games/quoridor/test_state.py
git commit -m "feat(quoridor): add registered game and state shell"
```

---

## Task 5: Prove wrapper compatibility and random-play conformance

**Files:**
- Modify: `src/table_peak/games/quoridor/__init__.py`
- Create: `tests/games/quoridor/test_wrapper.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/games/quoridor/test_wrapper.py`:

```python
from __future__ import annotations

import random

from table_peak.agents.random import RandomAgent
from table_peak.games.quoridor import QuoridorGameWrapper
from table_peak.runner.play import play_game, play_matches


def test_play_game_runs_to_terminal() -> None:
    game = QuoridorGameWrapper(seed=0)
    agents = {0: RandomAgent(rng=random.Random(0)), 1: RandomAgent(rng=random.Random(1))}
    outcome = play_game(game, agents)
    assert outcome.num_moves > 0
    assert set(outcome.returns.keys()) == {0, 1}


def test_play_matches_is_reproducible_with_seeded_agents() -> None:
    def run() -> object:
        return play_matches(
            QuoridorGameWrapper(seed=0),
            agent_a=RandomAgent(rng=random.Random(10)),
            agent_b=RandomAgent(rng=random.Random(20)),
            n=10,
            swap_sides=True,
            seed=99,
        )

    assert run() == run()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/games/quoridor/test_wrapper.py -v`
Expected: FAIL with `ImportError: cannot import name 'QuoridorGameWrapper'`.

- [ ] **Step 3: Export the wrapper, then run the whole Quoridor slice**

Replace `src/table_peak/games/quoridor/__init__.py` with:

```python
"""Quoridor engine -- registers `quoridor` with open_spiel on import."""

from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

from table_peak.games._pyspiel_adapter import PyspielGameAdapter
from table_peak.games.quoridor import game as _game  # noqa: F401


def QuoridorGameWrapper(seed: int = 0) -> PyspielGameAdapter:
    inner = pyspiel.load_game("quoridor", {"seed": seed})
    return PyspielGameAdapter(inner, seed=seed)
```

Use these commands:

```bash
.venv/bin/pytest tests/games/quoridor -v
.venv/bin/ruff check src/table_peak/games/quoridor tests/games/quoridor
.venv/bin/mypy src/table_peak/games/quoridor tests/games/quoridor
```

Expected: all Quoridor tests PASS; `ruff` and `mypy` exit 0.

- [ ] **Step 4: Run the repo-wide verification target**

Run:

```bash
make check
```

Expected: `lint`, `format-check`, `typecheck`, and `test` all pass.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/quoridor/__init__.py \
        tests/games/quoridor/test_wrapper.py
git commit -m "test(quoridor): add wrapper and conformance coverage"
```

---

## Self-review checklist

- **Spec coverage:** this plan covers codec/constants, wall legality/path condition, pawn movement/jumps, registered-game/state wiring, wrapper compatibility, and repo-level verification.
- **Placeholder scan:** no `TBD`, `TODO`, or “similar to Task N” references remain.
- **Type consistency:** `Cell`, `WallAnchor`, `Orientation`, `encode_move`, `encode_wall`, `decode`, `legal_pawn_destinations`, `is_wall_legal`, `QuoridorState`, and `QuoridorGameWrapper` are used consistently across tasks.
