# Skyjo Web Play — Design

**Date:** 2026-06-05
**Status:** Draft, awaiting user review
**Slug:** `skyjo-web-play`

## Goal

Let a human play a full round of Skyjo in the browser against Random bots, reusing
the existing FastAPI web stack that today plays Tic-Tac-Toe. This is the first
human-facing front-end for the Skyjo engine: it doubles as an end-to-end test of
the engine's main loop and as the seat scaffold a trained agent will later drop into.

## Scope decisions (arbitrations made during brainstorming)

- **Front-end: the existing web UI.** Not a CLI. It is where the "play against AI later"
  story lives and reuses the TTT play machinery (`advance_bots`, session store, partial
  re-render on each move).
- **Seats: one human + N Random bots, total 2–8.** The human is player 0; players 1..N−1
  are Random bots. The new-game form picks the player count. No hotseat / multi-human —
  a single viewing perspective sidesteps Skyjo's hidden-information "pass the device"
  problem entirely.
- **One round only.** Matches the engine, which is single-round (the game-to-100 driver
  stays deferred). "Play Skyjo" = play one round to its scored conclusion.
- **Drop in after a randomized setup; no fast-forward.** On new game, the deal and the
  initial flip-2 setup phase are auto-resolved with *random* reveals for every seat,
  including the human. The human is then handed their first main-play turn and plays the
  whole main phase to round-end. The only thing the human does not control is which two
  cards start face-up.
  - *Why randomized setup, not a setup UI:* the setup move is "choose an unordered pair
    of 2 of 12 slots" — 66 distinct actions, awkward to render and low strategic payoff
    for a play/test tool.
  - *Why no fast-forward:* advancing N random main turns is cheap, but the engine's
    `random_sim` conformance tests already cover varied mid-game states, so the
    stress-test value is redundant; a clean post-setup start is a more natural play
    experience and still exercises the complete main loop (turns, column elimination,
    round-end trigger, scoring) end-to-end.
- **Board layout: opponents tiled across the top, the human anchored at the bottom**
  (classic online-card-game framing; scales as bots are added).

## Non-goals (explicit YAGNI)

- No setup-phase UI (auto-randomized, see above).
- No multi-round / game-to-100 driver or cumulative scoreboard.
- No hotseat / multi-human, and therefore no pass-and-play hidden-info flow.
- No bespoke Skyjo agents. Random bots only; the seat mechanism is identical for a future
  trained agent (a one-line registry change).
- No fast-forward / scripted starting positions.
- No persistence beyond the existing in-memory session store; single Uvicorn worker.
- No universal/data-driven "render any game" abstraction (premature with two games).
- No restyle of the existing TTT board beyond the mechanical `cell`→`action` rename.

## Architecture decisions

### A. Generalize the web core the minimal amount; add a per-game renderer

The current web stack is hardwired to TTT. The minimal generalization to host a second
game:

- **`GameSession.state` is typed to the `State` Protocol**, not `TicTacToeState`.
  `advance_bots` already calls only Protocol methods (`current_player`, `is_terminal`,
  `legal_actions` indirectly via the agent, `apply_action`) and needs no change.
- **Renderer registry.** Rendering dispatches per game: a small map from a game key to a
  render function. TTT keeps its existing `render`; Skyjo gets a new one. `game.html`
  includes the per-game board partial.
- **Moves post a raw action integer.** `submit_move` takes `action: int` (was `cell`),
  validated against `state.legal_actions()` exactly as today. TTT's `cell` already *was*
  the action integer, so this is a rename plus generalization; the TTT template posts
  `action` instead of `cell`.
- **New-game form** gains a game choice and, for Skyjo, a player-count (2–8). `create_game`
  branches on the chosen game to build the right initial state and the seat→agent map
  (seat 0 = Human/`None`, the rest = Random).

Rejected: a parallel Skyjo-only stack (duplicates the session store + `advance_bots`,
two diverging stacks, fights the multi-game-framework premise) and a universal view-model
(premature abstraction on a sample size of two very different games).

### B. The renderer reads a viewer-aware `public_view` from the engine

The board needs, per viewer: every player's grid (face-up values, face-down markers, and
the current column count so eliminated columns shrink correctly), the discard top, the
draw-pile size, the phase, the viewer's own drawn card (only mid-draw), and — at
round-end — the fully revealed grids and final scores. The engine exposes none of this in
structured public form today (only private fields, a god's-eye `__str__`, and the
agent-oriented `information_state_string`).

Decision: **add a small read-only `public_view(viewer)` method to `SkyjoState`** returning
a plain dataclass with the hiding rules applied — face-down values omitted (for the owner
too, per Skyjo's rule), deck order hidden, and the drawn card present only when `viewer`
is the player currently mid-draw. The hiding logic thus lives in the engine alongside the
existing observer, not smeared into the web renderer. **The adapter exposes its wrapped
state via a read-only `.inner`** so the web layer can reach the `SkyjoState`. The Skyjo
engine is already merged with no parallel work in flight, so these additions are safe.

Rejected: reading engine privates from the web layer (fragile coupling) and parsing
`information_state_string` / `__str__` (stringly-typed, format meant for agents/debugging).

### C. Setup is auto-resolved at game creation, detected via the action range

On `create_game`, after the adapter is built (the deal is auto-resolved as chance by the
adapter), the state sits in the setup-commit phase where every legal action is a
`RevealInitial` pair (the engine's reveal-initial action IDs occupy the low range below
all other action families). A small helper applies a random legal action while *all* legal
actions fall in that reveal-initial range — i.e. while still in setup — for every seat
including the human. Once the engine transitions to main play (legal actions now include
draw / take-discard IDs outside that range), the loop exits. This detection uses only the
`State` Protocol (`legal_actions`), so it needs no extra engine surface. Then the normal
`advance_bots` runs any bots that act before the human's first turn.

### D. Per-render states the UI must handle

Because `advance_bots` runs synchronously before each render, the human only ever lands on
their own decision point or the end. The render cases are:

1. **Your main turn — root:** choose *Take discard* (replace a slot with the visible
   discard top) or *Draw from deck*.
2. **Your main turn — after drawing:** the drawn card is shown to you; choose a **mode**,
   *Keep it → replace any slot* or *Discard it → flip a face-down slot*, then click the
   slot. The explicit mode toggle is required because a face-down slot is a legal target
   for both actions; the toggle is resolved client-side (no extra round trip) and posts
   the corresponding action ID. *Take discard* needs no toggle (only "replace a slot").
3. **Round over:** all grids revealed, per-player final scores shown, no controls.

(The setup case is never rendered — it is auto-resolved at creation.)

### E. Action wiring

Each clickable element (a slot, a button) carries the engine action integer it would post.
The Skyjo renderer computes those IDs from the engine's encoders for the current phase and
attaches them, so `submit_move` stays game-agnostic: validate `action ∈ legal_actions()`,
apply, `advance_bots`, re-render the board partial. Identical control flow to TTT.

## Information hiding

Single human perspective (player 0). The rendered view for any seat shows only public
information plus that seat's own legal private knowledge (its drawn card mid-turn). Bots'
face-down cards, the deck order, and bots' transient drawn cards are never serialized into
the human's view. A test asserts the rendered human view exposes no face-down card values.

## Success criteria (binary, machine-checkable)

1. **Start.** From `/`, choosing Skyjo with a player count 2–8 creates a game and renders
   the human's first main turn — setup already resolved, the human's grid showing exactly
   two face-up cards (a player only ever modifies its own grid, so any bot turns that
   precede the human's first turn leave the human's two-face-up grid untouched).
2. **Full round.** A scripted client (TestClient) can play a complete round of Skyjo to
   terminal by posting legal actions, and the round-end page shows per-player final scores
   equal to the engine's `round_scores()` / `-returns()`.
3. **TTT regression.** Existing TTT web tests pass unchanged after the `cell`→`action`
   generalization (the TTT template and route updated together).
4. **No info leak.** The human's rendered view contains no face-down card value for any
   player and no drawn-card value for any bot. Asserted by test.
5. **Illegal-move handling.** Posting an action not in `legal_actions()` is rejected
   (HTTP 4xx), as in the TTT route.
6. **Static layer.** `mypy --strict` and `ruff check` pass on new/changed code.

## Testing strategy

Macro, black-box, fast — aligned with the project's test guidelines and the existing web
tests (FastAPI `TestClient`, `dependency_overrides` for the store).

- **Setup auto-resolve.** After `create_game` for Skyjo, the state is in main play and the
  human's grid has two face-up cards (black-box on the rendered view / public_view).
- **Full-round playthrough.** Drive a 2-player Skyjo game via `TestClient`, always posting
  a legal action for the human, until the round-over page; assert displayed scores match
  the engine. A seeded run is reproducible.
- **Info-hiding.** Assert the rendered human view never contains a face-down value.
- **`public_view` unit-ish.** A hand-built terminal and mid-draw state expose the right
  public fields and hide the right private ones.
- **TTT regression.** Existing suite, unchanged behavior.
- **Static.** `mypy --strict`, `ruff`.

Not tested: pixel-level HTML, bot decision quality, multi-worker session behavior.

## Forbidden zones (parallel-feature-development)

Globs this feature owns and exclusively writes:

- `src/table_peak/web/renderers/skyjo.py` (new)
- `src/table_peak/web/templates/_skyjo_board.html` and any Skyjo-specific partials (new)
- `tests/web/test_skyjo_play.py` (new) and Skyjo web test modules

Shared files this feature modifies (a concurrent sibling must coordinate):

- `src/table_peak/web/app.py` — game picker route branch, `cell`→`action` rename
- `src/table_peak/web/sessions.py` — `GameSession.state` typed to `State` Protocol; setup
  auto-resolve helper
- `src/table_peak/web/agents.py` — Random factory available for Skyjo seats
- `src/table_peak/web/renderers/__init__.py` — renderer registry
- `src/table_peak/web/templates/new_game.html`, `game.html`, `_board.html` — game picker,
  dispatch, `action` field
- `src/table_peak/games/skyjo/state.py` — add `public_view(viewer)` (read-only)
- `src/table_peak/games/skyjo/__init__.py` — export the public-view dataclass if it lives
  there
- `src/table_peak/games/_pyspiel_adapter.py` — add read-only `.inner`

Reads but does not modify: `src/table_peak/games/base.py`, `src/table_peak/agents/**`,
`docs/games/skyjo-rules.md`.

## Open questions / risks

- **TTT `cell`→`action` rename blast radius.** Small and mechanical (one route field, one
  template field, the TTT tests). The regression test is the binding check.
- **Branch-b client-side mode toggle.** The keep-vs-discard-&-flip toggle is the only
  client-side interaction beyond a plain POST; kept minimal (toggles which action ID the
  slot click posts). If it proves fiddly, fallback is a two-step server round trip
  (choose mode → re-render with the right targets); no engine change either way.
- **Column elimination shrinks the grid mid-round.** The renderer must read the current
  column count from `public_view`, not assume 4 columns. Covered by deriving geometry from
  the view.

## Deferred (explicit YAGNI for this spec)

- Multi-round driver and cumulative scoreboard.
- Human-controlled setup (choosing your own opening flip).
- Trained/heuristic Skyjo agents.
- Hotseat / multi-human and pass-and-play.
- Persistent sessions / multi-worker.
- Universal cross-game renderer.
