# Quoridor Web Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent table_peak-4rl`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.

**Goal:** Let a human play Quoridor in the browser through the existing FastAPI web UI, reusing the already-shipped Quoridor engine untouched, for hands-on exploratory testing of pawn moves, jumps, wall-blocking, walls-remaining, and win detection.

**Architecture:** A per-game renderer (`web/renderers/quoridor.py`) projects the engine adapter's state into a frozen `QuoridorBoardView`; a Jinja partial (`_quoridor_board.html`) renders a 17-track CSS grid (9 cells + 8 gutters per axis) flipped so the human plays from the bottom. Pawn moves are 1 click (htmx form, like TTT); walls are 2 clicks resolved entirely client-side to a single legal `(anchor, orientation)` action, then POSTed as one action — keeping the server contract identical to TTT (one POST = one legal action). Quoridor reuses the existing TTT request path (`game_page` fast-forwards bots, `submit_move` re-renders the partial); only `create_game` gets a new branch.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, htmx (already vendored in templates), pyspiel-backed engine via `PyspielGameAdapter`. Tests: pytest + FastAPI `TestClient`.

---

## Background the engineer needs

**The engine adapter surface.** A Quoridor game is `QuoridorGameWrapper(seed).new_initial_state()`, returning a `PyspielStateAdapter`. The web layer drives it through the same `State` protocol as TTT/Skyjo:
- `state.current_player` (property) → `int` seat (0 or 1).
- `state.legal_actions()` → `list[int]` of encoded action ids.
- `state.apply_action(a)` → a new adapter (immutable).
- `state.is_terminal` (property) → `bool`.
- `state.returns()` → `dict[PlayerId, float]`, e.g. `{0: 1.0, 1: -1.0}` for a P0 win.
- `state.inner` (property) → the wrapped `QuoridorState`, used by the renderer to read board structure.

**Reading board structure (no engine changes).** Quoridor is perfect-information, so unlike Skyjo (which has a `view.py` to mask hidden cards) there is nothing to project or hide. The renderer reads the inner `QuoridorState` attributes directly:
- `inner._pawn_positions` → `dict[int, Cell]` (seat → `Cell(col,row)`).
- `inner._walls_remaining` → `dict[int, int]` (seat → walls left, starts 10/10).
- `inner._horizontal_walls` → `frozenset[WallAnchor]` placed horizontal walls.
- `inner._vertical_walls` → `frozenset[WallAnchor]` placed vertical walls.

> **Decision (flag at review):** the renderer reads single-underscore attributes of the inner engine state. This honors the spec's hard "no engine changes / web-only files" constraint and is safe because the game is perfect-information (no masking needed). The alternative — adding a read-only `games/quoridor/view.py` mirroring Skyjo — was rejected to keep this task to web files only. Isolated in one helper, `_read_board`.

**Action encoding** (`table_peak.games.quoridor.actions`, import as `q`):
- `q.encode_move(Cell(col,row)) -> int`.
- `q.encode_wall(WallAnchor(col,row), Orientation.HORIZONTAL|VERTICAL) -> int`.
- `q.decode(action) -> DecodedAction` with `.kind` (`"move"`/`"wall"`), `.destination` (`Cell|None`), `.anchor` (`WallAnchor|None`), `.orientation` (`Orientation|None`).

**Geometry** (`table_peak.games.quoridor.geometry`): `BOARD_SIZE = 9`, `Cell(col,row)`, `WallAnchor(col,row)` (col/row in 0..7), `Orientation` (StrEnum: `HORIZONTAL="h"`, `VERTICAL="v"`). `START_CELLS = {0: (4,0), 1: (4,8)}`, `GOAL_ROWS = {0: 8, 1: 0}`.

**Wall geometry (confirmed against `walls.edge_blocked`).** Walls span two cells:
- A **horizontal** wall at anchor `(col,row)` sits in the horizontal gutter between board rows `row` and `row+1`, spanning columns `col` and `col+1`. It occupies the two unit "segments" `h-{col}-{row}` and `h-{col+1}-{row}`, where segment `h-{c}-{r}` is the horizontal gutter piece under cell-column `c`, between rows `r` and `r+1`.
- A **vertical** wall at anchor `(col,row)` sits in the vertical gutter between board cols `col` and `col+1`, spanning rows `row` and `row+1`. It occupies segments `v-{col}-{row}` and `v-{col}-{row+1}`, where segment `v-{c}-{r}` is the vertical gutter piece right of cell-column `c`, at row `r`.
- The **intersection gap** filled solid when a wall is laid: `g-{col}-{row}` (the crossing point at the wall's anchor).

This `(segment, continuation) -> unique legal (anchor, orientation)` mapping is exactly what makes the 2-click input unambiguous, and it is precomputed in the renderer from `legal_actions()`.

**The 17-track CSS grid.** The board renders as a 17×17 grid: cell tracks (48px) interleaved with gutter tracks (12px). CSS grid lines are 1-based. An element at board column `c` uses grid-line `2c+1`; the gutter after column `c` uses line `2c+2` (same for rows). Concretely:
- Cell `(col,row)`: `grid-column: 2*col+1; grid-row: 2*row+1`.
- H-segment `h-{c}-{r}` (c∈0..8, r∈0..7): `grid-column: 2*c+1; grid-row: 2*r+2`.
- V-segment `v-{c}-{r}` (c∈0..7, r∈0..8): `grid-column: 2*c+2; grid-row: 2*r+1`.
- Gap `g-{c}-{r}` (c∈0..7, r∈0..7): `grid-column: 2*c+2; grid-row: 2*r+2`.

The board container gets `transform: scaleY(-1)` so P0 (start row 0) appears at the bottom — a pure rendering flip; engine coordinates are untouched. Pawns are plain colored disks (no text), so the flip does not mirror any glyphs. Wall reserves render **outside** the flipped board (so they read upright), opponent's rack above the human's.

---

## File Structure

- **Create** `src/table_peak/web/renderers/quoridor.py` — `render(state, agents, game_id) -> QuoridorBoardView`. Owns all geometry↔action-id mapping; reads inner engine state via one `_read_board` helper.
- **Modify** `src/table_peak/web/renderers/__init__.py` — register `"quoridor"` in `RENDERERS`.
- **Create** `src/table_peak/web/templates/_quoridor_board.html` — the board partial (CSS grid, pawn-move htmx forms, gutter segments, racks, wall 2-click JS).
- **Modify** `src/table_peak/web/templates/new_game.html` — add a Quoridor `<fieldset>`.
- **Modify** `src/table_peak/web/app.py` — add a `quoridor` branch to `create_game`.
- **Create** `tests/web/test_quoridor_renderer.py` — renderer micro tests.
- **Modify** `tests/web/test_app.py` — add Quoridor macro tests (TestClient).

The existing `game_page`, `submit_move`, `advance_bots`, and `_render` need **no changes**: Quoridor is `!= "skyjo"`, so it already fast-forwards bots and re-renders `view.partial`, and `_render` already falls through to `RENDERERS.get(session.game)`.

---

### Task 1: Renderer core — view, board read, cells, pawns, status, walls-remaining

Builds the renderer skeleton and everything except wall decomposition (Task 2): the frozen view, reading inner engine state, the 81 cells with pawn occupancy and legal-move targets, walls-remaining counts, status/terminal text, and registry wiring.

**Files:**
- Create: `src/table_peak/web/renderers/quoridor.py`
- Modify: `src/table_peak/web/renderers/__init__.py`
- Test: `tests/web/test_quoridor_renderer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_quoridor_renderer.py`:

```python
"""Tests for the Quoridor board renderer (state -> QuoridorBoardView)."""

from __future__ import annotations

import json
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.quoridor import QuoridorGameWrapper
from table_peak.games.quoridor import actions as q
from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor
from table_peak.web.renderers.quoridor import QuoridorBoardView, render


def _initial() -> Any:
    return QuoridorGameWrapper(seed=0).new_initial_state()


def _human_vs_human() -> dict[PlayerId, Agent | None]:
    return {0: None, 1: None}


def _human_vs_bot() -> dict[PlayerId, Agent | None]:
    return {0: None, 1: RandomAgent()}


def _cell(view: QuoridorBoardView, col: int, row: int) -> Any:
    return next(c for c in view.cells if c.col == col and c.row == row)


def test_initial_view_metadata_and_pawns() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    assert view.partial == "_quoridor_board.html"
    assert view.title == "Quoridor"
    assert view.game_id == "g1"
    assert view.is_terminal is False
    assert len(view.cells) == 81
    # P0 starts at (4,0), P1 at (4,8).
    assert _cell(view, 4, 0).pawn == 0
    assert _cell(view, 4, 8).pawn == 1
    # No other cell is occupied.
    assert sum(1 for c in view.cells if c.pawn is not None) == 2
    # Both players start with 10 walls.
    assert view.walls_p0 == 10
    assert view.walls_p1 == 10


def test_initial_view_status_and_clickable_when_human_to_move() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    # advance_bots guarantees the rendered current player is human; P0 moves first.
    assert view.cells_clickable is True
    assert "Player 1" in view.status


def test_not_clickable_when_current_seat_is_a_bot() -> None:
    # P0 is a bot: render() is pure and must reflect that cells aren't clickable.
    agents: dict[PlayerId, Agent | None] = {0: RandomAgent(), 1: None}
    view = render(_initial(), agents, "g1")
    assert view.cells_clickable is False


def test_terminal_status_reports_winner() -> None:
    # Drive P0 straight up the board to its goal row (8) for a deterministic win.
    state = _initial()
    for row in range(1, 9):
        state = state.apply_action(q.encode_move(Cell(col=4, row=row)))
    view = render(state, _human_vs_human(), "g1")
    assert view.is_terminal is True
    assert "Player 1" in view.status and "won" in view.status
    assert view.cells_clickable is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -q`
Expected: FAIL — `ImportError: cannot import name 'QuoridorBoardView' from 'table_peak.web.renderers.quoridor'` (module does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `src/table_peak/web/renderers/quoridor.py`:

```python
"""Render a Quoridor state (PyspielStateAdapter) into a template-friendly view.

Quoridor is perfect-information, so unlike Skyjo there is nothing to mask: the
renderer reads the inner engine state directly (see _read_board). The human plays
from the bottom via a CSS scaleY(-1) flip in the template; engine coordinates are
untouched.

Interaction model:
  - Pawn move = 1 click on a green-tinted legal destination cell -> POST encode_move.
  - Wall = 2 clicks on gutter segments, resolved client-side to one legal
    (anchor, orientation) action -> POST encode_wall (see Task 2 / legal_walls_json).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from table_peak.agents.base import Agent
from table_peak.games._pyspiel_adapter import PyspielStateAdapter
from table_peak.games.base import PlayerId
from table_peak.games.quoridor import actions as q
from table_peak.games.quoridor.geometry import BOARD_SIZE, Cell, WallAnchor

PARTIAL = "_quoridor_board.html"
TITLE = "Quoridor"


@dataclass(frozen=True, slots=True)
class QuoridorCell:
    col: int
    row: int
    pawn: int | None  # seat occupying this cell, or None
    is_move_target: bool  # legal pawn destination -> green tint + clickable
    move_action: int  # encode_move id when is_move_target, else -1


@dataclass(frozen=True, slots=True)
class BoardData:
    """Plain projection of the inner engine state (no hidden info to mask)."""

    pawns: dict[int, Cell]
    walls_remaining: dict[int, int]
    horizontal_walls: frozenset[WallAnchor]
    vertical_walls: frozenset[WallAnchor]


@dataclass(frozen=True, slots=True)
class QuoridorBoardView:
    partial: str
    title: str
    game_id: str
    status: str
    is_terminal: bool
    cells: tuple[QuoridorCell, ...]  # row-major, 81 cells
    cells_clickable: bool
    walls_p0: int
    walls_p1: int
    # Wall fields are populated in Task 2; default to empty so Task 1 stays self-contained.
    placed_segs: frozenset[str] = frozenset()
    placed_gaps: frozenset[str] = frozenset()
    candidate_segs: frozenset[str] = frozenset()
    legal_walls_json: str = "[]"


def _read_board(inner: Any) -> BoardData:
    """Read board structure off the inner QuoridorState.

    Reaches single-underscore attributes by design: Quoridor is perfect-info, so
    the renderer needs no masking and the engine exposes no public accessor. This
    is the only place that couples to engine internals.
    """
    return BoardData(
        pawns=dict(inner._pawn_positions),
        walls_remaining=dict(inner._walls_remaining),
        horizontal_walls=inner._horizontal_walls,
        vertical_walls=inner._vertical_walls,
    )


def _human_seat(agents: dict[PlayerId, Agent | None]) -> int:
    for seat, agent in agents.items():
        if agent is None:
            return seat
    return 0


def _status(state: Any, board: BoardData, seat: int, clickable: bool) -> str:
    if state.is_terminal:
        returns = state.returns()
        winner = next((pid for pid, r in returns.items() if r > 0), None)
        if winner is None:
            return "Game over — draw"
        return f"Game over — Player {winner + 1} won"
    walls = board.walls_remaining[seat]
    return f"Your turn — Player {seat + 1} ({walls} walls left)"


def render(
    state: Any,
    agents: dict[PlayerId, Agent | None],
    game_id: str,
) -> QuoridorBoardView:
    assert isinstance(state, PyspielStateAdapter)
    board = _read_board(state.inner)

    pawn_at: dict[tuple[int, int], int] = {
        (c.col, c.row): seat for seat, c in board.pawns.items()
    }

    seat = state.current_player
    clickable = (not state.is_terminal) and agents[seat] is None

    move_targets: dict[tuple[int, int], int] = {}
    if clickable:
        for action in state.legal_actions():
            decoded = q.decode(action)
            if decoded.kind == "move":
                assert decoded.destination is not None
                move_targets[(decoded.destination.col, decoded.destination.row)] = action

    cells: list[QuoridorCell] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            is_target = (col, row) in move_targets
            cells.append(
                QuoridorCell(
                    col=col,
                    row=row,
                    pawn=pawn_at.get((col, row)),
                    is_move_target=is_target,
                    move_action=move_targets.get((col, row), -1),
                )
            )

    return QuoridorBoardView(
        partial=PARTIAL,
        title=TITLE,
        game_id=game_id,
        status=_status(state, board, seat, clickable),
        is_terminal=state.is_terminal,
        cells=tuple(cells),
        cells_clickable=clickable,
        walls_p0=board.walls_remaining[0],
        walls_p1=board.walls_remaining[1],
    )
```

Register it in `src/table_peak/web/renderers/__init__.py` — add the import and registry entry:

```python
from table_peak.web.renderers import quoridor, skyjo, tic_tac_toe

RenderFn = Callable[[Any, dict[PlayerId, Agent | None], str], Any]

RENDERERS: dict[str, RenderFn] = {
    "tic_tac_toe": tic_tac_toe.render,
    "skyjo": skyjo.render,
    "quoridor": quoridor.render,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/web/renderers/quoridor.py src/table_peak/web/renderers/__init__.py tests/web/test_quoridor_renderer.py
git commit -m "feat(web): Quoridor renderer core — cells, pawns, status, walls-remaining"
```

---

### Task 2: Renderer wall decomposition — candidate segments, placed walls, legal-wall payload

Adds the 2-click wall data to the renderer: which gutter segments are placed (solid), which are clickable candidates, and a JSON payload mapping each legal wall to its two segments so the client JS can resolve a `(segment, continuation)` pair to one action id.

**Files:**
- Modify: `src/table_peak/web/renderers/quoridor.py`
- Test: `tests/web/test_quoridor_renderer.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_quoridor_renderer.py`:

```python
def _legal_walls(view: QuoridorBoardView) -> list[dict[str, Any]]:
    return json.loads(view.legal_walls_json)


def test_initial_legal_walls_payload_decomposes_into_segments() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    walls = _legal_walls(view)
    # A horizontal wall at anchor (0,0) is legal on an empty board.
    h00 = q.encode_wall(WallAnchor(col=0, row=0), Orientation.HORIZONTAL)
    entry = next(w for w in walls if w["action"] == h00)
    assert entry["orientation"] == "h"
    assert {entry["seg_a"], entry["seg_b"]} == {"h-0-0", "h-1-0"}
    # A vertical wall at anchor (0,0) decomposes into stacked v-segments.
    v00 = q.encode_wall(WallAnchor(col=0, row=0), Orientation.VERTICAL)
    ventry = next(w for w in walls if w["action"] == v00)
    assert ventry["orientation"] == "v"
    assert {ventry["seg_a"], ventry["seg_b"]} == {"v-0-0", "v-0-1"}


def test_candidate_segs_are_the_union_of_legal_wall_segments() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    walls = _legal_walls(view)
    expected = {w["seg_a"] for w in walls} | {w["seg_b"] for w in walls}
    assert view.candidate_segs == expected
    assert "h-0-0" in view.candidate_segs


def test_placed_wall_marks_its_segments_and_gap() -> None:
    # P0 places a horizontal wall at anchor (2,3), then read the view.
    state = _initial()
    action = q.encode_wall(WallAnchor(col=2, row=3), Orientation.HORIZONTAL)
    assert action in state.legal_actions()
    state = state.apply_action(action)
    view = render(state, _human_vs_human(), "g1")
    assert {"h-2-3", "h-3-3"} <= view.placed_segs
    assert "g-2-3" in view.placed_gaps


def test_no_candidate_walls_when_not_human_turn() -> None:
    agents: dict[PlayerId, Agent | None] = {0: RandomAgent(), 1: None}
    view = render(_initial(), agents, "g1")
    assert view.candidate_segs == frozenset()
    assert _legal_walls(view) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -q`
Expected: FAIL — the new tests fail because `legal_walls_json` is `"[]"`, `candidate_segs`/`placed_segs`/`placed_gaps` are empty (Task 1 defaults).

- [ ] **Step 3: Write minimal implementation**

In `src/table_peak/web/renderers/quoridor.py`, add `json` and `Orientation` imports at the top:

```python
import json
```

and extend the geometry import line to include `Orientation`:

```python
from table_peak.games.quoridor.geometry import BOARD_SIZE, Cell, Orientation, WallAnchor
```

Add these helpers above `render`:

```python
def _wall_segments(anchor: WallAnchor, orientation: Orientation) -> tuple[str, str]:
    """The two unit gutter segments a wall occupies (see module/plan geometry)."""
    if orientation is Orientation.HORIZONTAL:
        return f"h-{anchor.col}-{anchor.row}", f"h-{anchor.col + 1}-{anchor.row}"
    return f"v-{anchor.col}-{anchor.row}", f"v-{anchor.col}-{anchor.row + 1}"


def _placed(board: BoardData) -> tuple[frozenset[str], frozenset[str]]:
    """Segment ids and intersection-gap ids for every already-placed wall."""
    segs: set[str] = set()
    gaps: set[str] = set()
    for anchor in board.horizontal_walls:
        segs.update(_wall_segments(anchor, Orientation.HORIZONTAL))
        gaps.add(f"g-{anchor.col}-{anchor.row}")
    for anchor in board.vertical_walls:
        segs.update(_wall_segments(anchor, Orientation.VERTICAL))
        gaps.add(f"g-{anchor.col}-{anchor.row}")
    return frozenset(segs), frozenset(gaps)


def _legal_walls(state: Any) -> tuple[list[dict[str, Any]], frozenset[str]]:
    """Legal-wall payload (for client JS) and the union of candidate segment ids."""
    walls: list[dict[str, Any]] = []
    candidates: set[str] = set()
    for action in state.legal_actions():
        decoded = q.decode(action)
        if decoded.kind != "wall":
            continue
        assert decoded.anchor is not None and decoded.orientation is not None
        seg_a, seg_b = _wall_segments(decoded.anchor, decoded.orientation)
        walls.append(
            {
                "action": action,
                "orientation": decoded.orientation.value,
                "seg_a": seg_a,
                "seg_b": seg_b,
            }
        )
        candidates.update((seg_a, seg_b))
    return walls, frozenset(candidates)
```

In `render`, after computing `clickable` and before building `cells`, compute the wall data (candidate walls only when it's the human's turn):

```python
    placed_segs, placed_gaps = _placed(board)
    if clickable:
        legal_walls, candidate_segs = _legal_walls(state)
    else:
        legal_walls, candidate_segs = [], frozenset()
```

Then pass the new fields into the `QuoridorBoardView(...)` return:

```python
        placed_segs=placed_segs,
        placed_gaps=placed_gaps,
        candidate_segs=candidate_segs,
        legal_walls_json=json.dumps(legal_walls),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/web/renderers/quoridor.py tests/web/test_quoridor_renderer.py
git commit -m "feat(web): Quoridor renderer wall decomposition — segments, placed, legal-wall payload"
```

---

### Task 3: Board template — grid, pawns, placed walls, racks, pawn-move forms

Creates `_quoridor_board.html`: the flipped 17-track CSS grid with cells, pawn disks, placed walls solid, gutter segments, the two wall-reserve racks, and 1-click pawn-move htmx forms. Wall-click JS is added in Task 4. Verified by a render smoke test through `game_page` in Task 5; here we add a focused template-render test using Jinja directly.

**Files:**
- Create: `src/table_peak/web/templates/_quoridor_board.html`
- Test: `tests/web/test_quoridor_renderer.py` (one template-render test)

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_quoridor_renderer.py`:

```python
def _render_partial(view: QuoridorBoardView) -> str:
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    templates_dir = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "table_peak"
        / "web"
        / "templates"
    )
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    return env.get_template("_quoridor_board.html").render(view=view)


def test_template_renders_board_pawns_and_status() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    html = _render_partial(view)
    assert 'id="board"' in html
    assert "Player 1" in html  # status text
    # Pawn disks for both seats appear.
    assert "pawn p0" in html
    assert "pawn p1" in html
    # A legal pawn-move target posts its action via an htmx form. P0 can step to (4,1).
    target = next(c for c in view.cells if c.col == 4 and c.row == 1)
    assert target.is_move_target is True
    assert f'value="{target.move_action}"' in html


def test_template_renders_placed_wall_segments() -> None:
    state = _initial()
    state = state.apply_action(
        q.encode_wall(WallAnchor(col=2, row=3), Orientation.HORIZONTAL)
    )
    view = render(state, _human_vs_human(), "g1")
    html = _render_partial(view)
    # Placed segments carry the "placed" class.
    assert "placed" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -k template -q`
Expected: FAIL — `jinja2.exceptions.TemplateNotFound: _quoridor_board.html`.

- [ ] **Step 3: Write minimal implementation**

Create `src/table_peak/web/templates/_quoridor_board.html`:

```html
<div id="board">
    <style>
        .qwrap { margin: 1rem 0; }
        .qrack { display: flex; gap: 6px; height: 24px; margin: 6px 0; align-items: center; }
        .qrack .tok { width: 12px; height: 24px; background: #6b4f2a; border-radius: 2px; }
        .qrack .lbl { font-size: 0.9rem; color: #555; margin-right: 8px; min-width: 5.5rem; }
        .qgrid {
            display: grid;
            grid-template-columns: repeat(8, 48px 12px) 48px;
            grid-template-rows: repeat(8, 48px 12px) 48px;
            background: #d9b98a;
            padding: 8px;
            width: max-content;
            transform: scaleY(-1);
        }
        .qcell { background: #f2dcb3; display: flex; align-items: center; justify-content: center; }
        .qcell.target { background: #bfe6bf; cursor: pointer; }
        .qcell form { width: 100%; height: 100%; margin: 0; }
        .qcell button { width: 100%; height: 100%; background: transparent; border: 0; cursor: pointer; }
        .pawn { width: 32px; height: 32px; border-radius: 50%; }
        .pawn.p0 { background: #2b6cb0; }
        .pawn.p1 { background: #c53030; }
        .seg { background: transparent; }
        .seg.candidate { cursor: pointer; }
        .seg.candidate:hover { background: #9ec7f0; }
        .seg.placed, .gap.placed { background: #6b4f2a; }
        .seg.pending { background: #6b4f2a; }
        .seg.preview { background: #c9a36a; }
        .gap { background: transparent; }
        .status { font-size: 1.25rem; }
    </style>

    <div class="qwrap">
        <p class="status">{{ view.status }}</p>

        <div class="qrack">
            <span class="lbl">Player 2</span>
            {% for _ in range(view.walls_p1) %}<span class="tok"></span>{% endfor %}
        </div>

        <div class="qgrid">
            {# Cells: pawn disks and 1-click move targets. #}
            {% for cell in view.cells %}
                {% set gc = 2 * cell.col + 1 %}
                {% set gr = 2 * cell.row + 1 %}
                {% if cell.is_move_target %}
                    <form class="qcell target" style="grid-column: {{ gc }}; grid-row: {{ gr }};"
                          hx-post="/games/{{ view.game_id }}/move" hx-target="#board" hx-swap="outerHTML">
                        <button type="submit" name="action" value="{{ cell.move_action }}"></button>
                    </form>
                {% else %}
                    <div class="qcell" style="grid-column: {{ gc }}; grid-row: {{ gr }};">
                        {% if cell.pawn is not none %}<span class="pawn p{{ cell.pawn }}"></span>{% endif %}
                    </div>
                {% endif %}
            {% endfor %}

            {# Horizontal gutter segments: c in 0..8, r in 0..7. #}
            {% for r in range(8) %}{% for c in range(9) %}
                {% set sid = "h-" ~ c ~ "-" ~ r %}
                <div class="seg{% if sid in view.placed_segs %} placed{% elif sid in view.candidate_segs %} candidate{% endif %}"
                     {% if sid in view.candidate_segs %}data-segid="{{ sid }}"{% endif %}
                     style="grid-column: {{ 2 * c + 1 }}; grid-row: {{ 2 * r + 2 }};"></div>
            {% endfor %}{% endfor %}

            {# Vertical gutter segments: c in 0..7, r in 0..8. #}
            {% for r in range(9) %}{% for c in range(8) %}
                {% set sid = "v-" ~ c ~ "-" ~ r %}
                <div class="seg{% if sid in view.placed_segs %} placed{% elif sid in view.candidate_segs %} candidate{% endif %}"
                     {% if sid in view.candidate_segs %}data-segid="{{ sid }}"{% endif %}
                     style="grid-column: {{ 2 * c + 2 }}; grid-row: {{ 2 * r + 1 }};"></div>
            {% endfor %}{% endfor %}

            {# Intersection gaps: c in 0..7, r in 0..7. #}
            {% for r in range(8) %}{% for c in range(8) %}
                {% set gid = "g-" ~ c ~ "-" ~ r %}
                <div class="gap{% if gid in view.placed_gaps %} placed{% endif %}"
                     style="grid-column: {{ 2 * c + 2 }}; grid-row: {{ 2 * r + 2 }};"></div>
            {% endfor %}{% endfor %}
        </div>

        <div class="qrack">
            <span class="lbl">Player 1 (you)</span>
            {% for _ in range(view.walls_p0) %}<span class="tok"></span>{% endfor %}
        </div>
    </div>
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -k template -q`
Expected: PASS (2 passed). Run the whole file too: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -q` → 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/web/templates/_quoridor_board.html tests/web/test_quoridor_renderer.py
git commit -m "feat(web): Quoridor board template — grid, pawns, placed walls, racks, move forms"
```

---

### Task 4: Wall 2-click client JS

Adds the client-side 2-click wall mechanism to the partial: first click arms a segment (final color) and previews legal continuations (preview color); second click on a continuation resolves the unique `(segment, continuation)` pair to its action id and POSTs it via htmx; clicking elsewhere cancels. The script lives **inside** `#board` so every htmx swap re-initializes it (same approach as Skyjo's armed mechanism). No automated browser test (out of scope per spec); verified manually + by the macro test in Task 5 that POSTs a resolved wall action directly.

**Files:**
- Modify: `src/table_peak/web/templates/_quoridor_board.html`

- [ ] **Step 1: Add the script block**

Insert this `<script>` just before the final closing `</div>` of `#board` (after the `.qwrap` div), so it is re-run on every swap:

```html
    <script>
    (function () {
        var board = document.getElementById('board');
        var gameId = "{{ view.game_id }}";
        var walls = {{ view.legal_walls_json | safe }};
        // segId -> [{action, other}]
        var map = {};
        walls.forEach(function (w) {
            (map[w.seg_a] = map[w.seg_a] || []).push({ action: w.action, other: w.seg_b });
            (map[w.seg_b] = map[w.seg_b] || []).push({ action: w.action, other: w.seg_a });
        });
        var pending = null;

        function clearMarks() {
            board.querySelectorAll('.pending, .preview').forEach(function (el) {
                el.classList.remove('pending', 'preview');
            });
        }
        function seg(id) { return board.querySelector('[data-segid="' + id + '"]'); }
        function arm(id) {
            clearMarks();
            pending = id;
            var el = seg(id);
            if (el) el.classList.add('pending');
            (map[id] || []).forEach(function (c) {
                var o = seg(c.other);
                if (o) o.classList.add('preview');
            });
        }
        function complete(id) {
            var entry = (map[pending] || []).find(function (c) { return c.other === id; });
            pending = null;
            if (!entry) { clearMarks(); return; }
            htmx.ajax('POST', '/games/' + gameId + '/move', {
                target: '#board', swap: 'outerHTML', values: { action: entry.action }
            });
        }
        board.addEventListener('click', function (ev) {
            var el = ev.target.closest('[data-segid]');
            if (!el) { if (pending) { clearMarks(); pending = null; } return; }
            var id = el.dataset.segid;
            if (!(id in map)) return;
            if (pending && (map[pending] || []).some(function (c) { return c.other === id; })) {
                complete(id);
            } else {
                arm(id);
            }
        });
    })();
    </script>
```

- [ ] **Step 2: Verify the partial still renders (regression)**

Run: `.venv/bin/pytest tests/web/test_quoridor_renderer.py -q`
Expected: PASS (10 passed) — the `| safe` JSON and script block must not break Jinja rendering.

- [ ] **Step 3: Manual smoke check (documented, not automated)**

Run the app and confirm wall placement by eye:

Run: `.venv/bin/uvicorn table_peak.web.app:app --port 8000` (then open http://localhost:8000, start a Quoridor game, click a gutter segment → it darkens and continuations highlight; click a continuation → the full wall lays and the turn advances). Stop the server with Ctrl-C.
Expected: a wall spanning two cells appears; an illegal continuation is never offered; clicking a pawn target still moves the pawn.

- [ ] **Step 4: Commit**

```bash
git add src/table_peak/web/templates/_quoridor_board.html
git commit -m "feat(web): Quoridor 2-click wall placement (client-side resolve + htmx POST)"
```

---

### Task 5: Wire create_game + new-game form, and macro tests

Adds the `quoridor` branch to `create_game` and a Quoridor `<fieldset>` to the new-game form (two `Human`/`Random` seat dropdowns, reusing the existing `x_agent`/`o_agent` form fields and `_build_agent`). Then end-to-end macro tests through the FastAPI `TestClient`.

**Files:**
- Modify: `src/table_peak/web/app.py`
- Modify: `src/table_peak/web/templates/new_game.html`
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_app.py`:

```python
from table_peak.games.quoridor import QuoridorGameWrapper
from table_peak.games.quoridor import actions as q
from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor


def _create_quoridor(client: TestClient, x_agent: str, o_agent: str) -> str:
    r = client.post(
        "/games",
        data={"game": "quoridor", "x_agent": x_agent, "o_agent": o_agent},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return str(r.headers["location"]).rsplit("/", 1)[-1]


def test_new_game_page_offers_quoridor(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'value="quoridor"' in r.text


def test_quoridor_game_page_renders_board(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    r = client.get(f"/games/{game_id}")
    assert r.status_code == 200
    assert 'id="board"' in r.text
    assert "Player 1" in r.text
    assert "pawn p0" in r.text


def test_quoridor_human_pawn_move_applies(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    # P0 steps forward from (4,0) to (4,1).
    action = q.encode_move(Cell(col=4, row=1))
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 200
    assert 'id="board"' in r.text  # response is the board fragment


def test_quoridor_human_wall_move_applies(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    # A resolved wall action (what the 2-click JS ultimately POSTs).
    action = q.encode_wall(WallAnchor(col=2, row=3), Orientation.HORIZONTAL)
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 200
    assert "placed" in r.text  # the wall now renders solid


def test_quoridor_illegal_action_rejected(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Human")
    # Teleporting P0 across the board is not a legal action.
    action = q.encode_move(Cell(col=0, row=8))
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 400


def test_quoridor_human_vs_random_bot_replies(client: TestClient) -> None:
    game_id = _create_quoridor(client, "Human", "Random")
    # GET fast-forwards nothing (P0/human is first); human moves, bot replies.
    action = q.encode_move(Cell(col=4, row=1))
    r = client.post(f"/games/{game_id}/move", data={"action": str(action)})
    assert r.status_code == 200
    # After the human move + bot reply it is the human's turn again, or game over.
    assert "Player 1" in r.text or "Game over" in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_app.py -k quoridor -q`
Expected: FAIL — `create_game` raises `400 Unknown game: quoridor` (no branch yet), so the create helper's `assert r.status_code == 303` fails.

- [ ] **Step 3: Write minimal implementation**

In `src/table_peak/web/app.py`, add the import near the other game imports:

```python
from table_peak.games.quoridor import QuoridorGameWrapper
```

Add a `quoridor` branch in `create_game`, between the `tic_tac_toe` branch and the final `else`:

```python
    elif game == "quoridor":
        agents = {
            0: _build_agent(x_agent),
            1: _build_agent(o_agent),
        }
        session = GameSession(
            game="quoridor",
            state=QuoridorGameWrapper(seed=secrets.randbelow(2**31)).new_initial_state(),
            agents=agents,
        )
```

> Note: the existing `tic_tac_toe` branch already declares `agents: dict[PlayerId, Agent | None]`. Reuse that annotated variable — do not redeclare the type — so the two branches share one `agents` binding and mypy stays happy.

In `src/table_peak/web/templates/new_game.html`, add a Quoridor form before the closing `</body>`:

```html
    <form action="/games" method="post">
        <fieldset>
            <legend>Quoridor</legend>
            <input type="hidden" name="game" value="quoridor">
            <label>
                Player 1 (you, bottom):
                <select name="x_agent">
                    <option value="Human" selected>Human</option>
                    <option value="Random">Random</option>
                </select>
            </label>
            <label>
                Player 2 (top):
                <select name="o_agent">
                    <option value="Human">Human</option>
                    <option value="Random" selected>Random</option>
                </select>
            </label>
            <button type="submit">Start Quoridor</button>
        </fieldset>
    </form>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/test_app.py -k quoridor -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Run the full web suite + static checks**

Run: `.venv/bin/pytest tests/web -q`
Expected: PASS (all web tests, including the pre-existing TTT/Skyjo ones, green).

Run: `.venv/bin/mypy src/table_peak/web/renderers/quoridor.py src/table_peak/web/app.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/web/app.py src/table_peak/web/templates/new_game.html tests/web/test_app.py
git commit -m "feat(web): wire Quoridor into create_game + new-game form, add macro tests"
```

---

## Verification before completion

After Task 5, run the full project gate and confirm the new tests actually ran (not "collected 0"):

```bash
.venv/bin/pytest tests/web -q          # expect the Quoridor renderer (10) + app (7) tests green
.venv/bin/mypy src/table_peak/web      # no errors
```

Then a one-time manual look (the spec's whole point is "look and feel"): start the app, play a few pawn moves and place a wall as described in Task 4 Step 3.

## Spec coverage map

- Engine reused untouched → no `games/quoridor/*` edits; renderer reads via `_read_board` only. ✓
- Per-game renderer + `.partial`/`.title` + registry → Task 1. ✓
- Clickable sets precomputed in the renderer from `legal_actions()` → Tasks 1 (moves) & 2 (walls). ✓
- 1-click pawn move (green tint) → Task 3 (`.target` + form). ✓
- 2-click wall, client-side, one POST = one action → Tasks 2 (data) + 4 (JS). ✓
- Human plays from bottom (`scaleY(-1)`) → Task 3. ✓
- Wall racks, opponent above human, only remaining shown → Task 3. ✓
- Two `Human`/`Random` seat dropdowns; Human-vs-Human hotseat + Human-vs-Random → Task 5. ✓
- Bots fast-forward (TTT path), illegal POST rejected → reuses existing `game_page`/`submit_move`; asserted in Task 5. ✓
- Renderer micro test + macro TestClient test → Tasks 1–3 + 5. ✓
- Non-goals (no engine changes, no new AI, no step-by-step, no persistence, no universal abstraction, no auto engine-correctness harness) → respected throughout. ✓
