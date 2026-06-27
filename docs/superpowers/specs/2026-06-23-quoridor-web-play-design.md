# Quoridor Web Play — Design

**Date:** 2026-06-23
**Status:** Draft, awaiting user review
**Slug:** `quoridor-web-play`

## Goal

Let a human play Quoridor in the browser, reusing the existing FastAPI web stack that
today plays Tic-Tac-Toe and Skyjo. The point is hands-on, exploratory testing of the
already-shipped Quoridor engine: clicking through real positions to confirm pawn moves,
jumps, wall-blocking, walls-remaining, and win detection *look and feel* right. This is
the first human-facing front-end for the engine and the seat scaffold a trained agent
will later drop into.

## Scope decisions (arbitrations made during brainstorming)

- **Engine is reused untouched.** `QuoridorGameWrapper(seed)` already returns a
  `PyspielGameAdapter` conforming to the same `State` protocol the web UI drives
  (`current_player`, `legal_actions`, `apply_action`, `is_terminal`, `returns`). Skyjo —
  also pyspiel-backed — already plays through this exact path. **This task is pure
  web-UI plumbing: no engine changes.**
- **Front-end: the existing web UI.** A renderer + template + registry/`create_game`
  wiring + a `new_game.html` block, mirroring the TTT/Skyjo pattern. Not a CLI.
- **Seats: two per-seat dropdowns (`Human` / `Random`), reusing the TTT form pattern.**
  This gives Human-vs-Human hotseat *or* Human-vs-Random from one mechanism. Hotseat is
  acceptable here because Quoridor is perfect-information — no hidden-info "pass the
  device" problem (unlike Skyjo) — and it lets the tester drive both pawns to construct
  arbitrary positions.
- **Bots fast-forward (TTT-style), not step-by-step (Skyjo-style "Next").** A Quoridor
  turn is a single action, so there is nothing multi-step to watch; after a human move,
  bot moves resolve until the next mover is human or the game ends. The board re-renders
  showing the bot's pawn move or new wall.
- **The engine is the single source of truth for legality.** Every clickable element is
  derived from `legal_actions()`. The UI can never offer or submit an illegal action;
  illegal POSTs are rejected exactly as today.

### Input model (refined "option A": the element you click determines intent — no mode toggle)

- **Pawn move = 1 click.** Legal destination cells (from `legal_actions()` decoded as
  moves — this already includes jumps) get a **slight green tint**; clicking one submits
  that action immediately.
- **Wall = 2 clicks.** Walls live in the gutters *between* cells and span two segments,
  so a single segment is genuinely ambiguous (it belongs to two possible walls, and H/V
  compete at each intersection). The two clicks resolve it:
  1. Click a gutter segment → it lands immediately in the **final wall color** (reads as
     a real placed segment), and the legal collinear continuations highlight in the
     segment **hover/preview color**.
  2. Click a highlighted continuation → the full wall is laid: first edge + the gap
     between + second edge fill solid. Hovering a continuation previews the gap filling.
  3. The pair `(segment, continuation)` maps to exactly one legal `(anchor, orientation)`
     action. Clicking a pawn cell or any non-candidate element cancels the pending wall.
  - Only continuations that complete a *legal* wall are offered, so the engine stays the
    arbiter.

### Visual decisions (validated against an interactive mockup during brainstorming)

- **The human plays from the bottom**, advancing upward toward their goal row. This is a
  pure *rendering* flip (`scaleY(-1)` on the board); the engine's coordinates
  (P0 start col4/row0, goal row 8) are untouched.
- **Pawn-destination hint is light** — a slight green cell tint, not a heavy ring/marker.
- **Wall reserves sit on the side of the board**, as **horizontal racks** of vertical-wall
  tokens: opponent's row directly above the human's so the two reserves compare at a
  glance. Tokens are **true 1:1 board scale** (one gutter wide × two-cells-plus-gutter
  tall), spaced one wall-width apart, and **only remaining walls are shown** (the rack
  shrinks as walls are spent — no empty slots).

## Non-goals (explicit YAGNI)

- No engine changes of any kind.
- No AI beyond the existing `RandomAgent`; the seat mechanism is identical for a future
  trained agent (a registry entry).
- No step-by-step bot stepping, animations, sound, or mobile/touch polish.
- No persistence beyond the existing in-memory session store; single Uvicorn worker.
- No universal/data-driven "render any game" abstraction (premature with three games).
- No automated engine-correctness harness (e.g. pyspiel game-tester); that is a separate,
  arguably better-targeted task and is out of scope here. The engine already has unit
  tests (commit `966b0e9`).

## Architecture decisions

### A. Per-game renderer, following the established pattern

- **`web/renderers/quoridor.py`** turns the adapter's state into a frozen
  `QuoridorBoardView`: the 9×9 cells with both pawns, placed horizontal/vertical walls in
  the gutters, each player's walls-remaining count, current-player/status text, and
  terminal/winner status. It exposes `.partial` (`_quoridor_board.html`) and `.title`,
  like `BoardView` (TTT) and the Skyjo view.
- **Clickable sets are precomputed in the renderer** from `legal_actions()`: the set of
  legal destination cells, and the set of legal wall placements decomposed into
  (first-segment → legal-continuation) pairs the template/JS can consume. The renderer,
  not the template, owns the mapping between grid geometry and engine action ids
  (`actions.encode_move` / `encode_wall` / `decode`).
- **Register** `quoridor` in `web/renderers/__init__.py:RENDERERS`.

### B. Minimal `create_game` + form wiring

- Add a `quoridor` branch to `create_game` in `app.py`: build the two seats from the
  `Human`/`Random` dropdowns (reusing `_build_agent`), construct the state via
  `QuoridorGameWrapper(seed=...).new_initial_state()`, wrap in a `GameSession`, store,
  redirect — exactly the TTT shape.
- Add a Quoridor `<fieldset>` to `new_game.html` with two per-seat dropdowns.
- Quoridor goes through the **same** `game_page` / `submit_move` path as TTT (it is
  `!= "skyjo"`, so `advance_bots` fast-forwards and `submit_move` re-renders the partial).

### C. The 2-click wall is a UI-only first step (no server round-trip needed mid-draw)

- The first click sets no game state. The board fragment can highlight the pending edge
  and legal continuations client-side from data the renderer already emitted, mirroring
  the existing `/board` fragment "armed/first-pick" mechanism Skyjo uses for
  `reveal_first`. Only the completing (second) click POSTs a single wall action to
  `/move`. This keeps the server contract identical to TTT: one POST = one legal action.

## Testing

Black-box, following the repo's macro/micro split:

- **Renderer micro test** — given a constructed `QuoridorState` (a known position with a
  pawn move available, a placed wall, and some walls spent), assert the `QuoridorBoardView`
  reflects it: pawn cells, wall gutters, walls-remaining counts, the legal
  destination/clickable sets, and terminal/winner status.
- **Macro test through the FastAPI `TestClient`** — create a Quoridor game, GET the board,
  POST a pawn move and a (resolved) wall action, assert the board reflects each and that an
  illegal action id is rejected (409/400, as today). This is the wiring test; the engine's
  own correctness is already covered.

## Files touched

- `src/table_peak/web/renderers/quoridor.py` (new)
- `src/table_peak/web/renderers/__init__.py` (register)
- `src/table_peak/web/templates/_quoridor_board.html` (new)
- `src/table_peak/web/templates/new_game.html` (Quoridor fieldset)
- `src/table_peak/web/app.py` (`create_game` branch)
- `tests/web/` (renderer + TestClient tests)

## Open question for review

- The interactive mockup lives at `.superpowers/brainstorm/quoridor-mockup-v5.html`
  (gitignored). It is the visual reference for the renderer/template; not shipped.
