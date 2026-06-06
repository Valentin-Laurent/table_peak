# Quoridor Engine — Design

**Date:** 2026-06-06
**Status:** Draft, awaiting user review
**Slug:** `quoridor-engine`

## Goal

Add a training-ready **2-player Quoridor engine** to `table_peak`, implemented as a
registered OpenSpiel / `pyspiel` game and exposed through the existing
`PyspielGameAdapter` wrapper. The deliverable is engine-only: no web UI, no
Quoridor-specific neural training stack, and no 4-player support in v1.

## Scope decisions (arbitrations made during brainstorming)

- **Game scope: 2-player Quoridor only.** The existing technical rules doc already
  targets the 2-player game, so v1 stays strict to that spec rather than
  half-designing 4-player support.
- **Architecture: layered OpenSpiel engine.** Use a `pyspiel.Game` /
  `pyspiel.State` shell, but keep core rules in focused helpers instead of one
  monolithic state class.
- **Integration target: existing `Game` / `State` protocol via wrapper.** The rest
  of `table_peak` should consume Quoridor through `PyspielGameAdapter`, as it does
  for Skyjo.
- **Testing target: engine + wrapper + conformance tests.** The feature stops at a
  correct, stable engine boundary; RL-specific encoders or experiments stay out of
  scope.

## Non-goals (explicit YAGNI)

- No 4-player Quoridor.
- No web or CLI play surface.
- No Quoridor-specific training encoder, policy net, or benchmark report.
- No generalized board-game framework refactor outside what Quoridor directly needs.
- No speculative abstractions for future games beyond the helper boundaries inside
  `src/table_peak/games/quoridor/`.

## Architecture decisions

### A. Mirror Skyjo's registration pattern, but keep the rules split into small units

Quoridor should live in a new `src/table_peak/games/quoridor/` package with:

- `game.py` — `QuoridorGame`, `GameType`, `GameInfo`, and registration
- `state.py` — `QuoridorState`, the OpenSpiel-facing state shell
- `geometry.py` — board coordinates, neighboring cells, wall-anchor addressing
- `actions.py` — stable int action encoding / decoding
- `moves.py` — pawn move generation, including straight and lateral jumps
- `walls.py` — wall occupancy, overlap / crossing checks, and path-condition search
- `__init__.py` — `QuoridorGameWrapper(seed=0)` returning `PyspielGameAdapter`

This matches the repo's OpenSpiel-compatible path while keeping logic testable in
isolation. `QuoridorState` owns turn flow and OpenSpiel API compliance, but helper
modules own the actual rules logic.

Rejected: a monolithic `QuoridorState` with all logic inline (faster initially, but
harder to reason about and test) and a native non-OpenSpiel engine first (cleaner
internals, but misaligned with the chosen integration target).

### B. Keep helper modules pure; keep the OpenSpiel state orchestration-thin

The design should preserve a clean boundary:

- helper functions are deterministic and side-effect free
- they accept explicit board / wall / pawn data
- they return concrete legal destinations, legal wall placements, or validation
  outcomes
- `QuoridorState` calls them to implement `legal_actions()`, `apply_action()`,
  terminal detection, and return values

That boundary keeps the core rules readable and enables black-box tests at both
helper and wrapped-game layers.

## State model and data flow

The state payload should stay intentionally small:

- active player
- pawn position for each player
- walls remaining for each player
- placed horizontal walls
- placed vertical walls

Terminal status is derived from pawn positions, not stored redundantly. A pawn move
onto the opponent's starting row ends the game immediately; wall placement never
wins.

### Action model

Use a **stable global integer action space** rather than state-local renumbering:

1. one contiguous range for `MovePawn(destination_cell)` over all 81 cells
2. one contiguous range for horizontal wall placements over the 8x8 legal anchors
3. one contiguous range for vertical wall placements over the 8x8 legal anchors

Most encoded actions are illegal in most states, which is acceptable: the benefit is
stable semantics across states, simpler tests, and a cleaner future RL integration
surface.

### Turn flow

`legal_actions()` builds the legal set in two passes:

1. enumerate legal pawn destinations from the current board graph, including:
   - orthogonal one-step moves
   - straight jumps over an adjacent opponent
   - lateral jumps when the straight jump is blocked by a wall or board edge
2. if the active player still has walls, enumerate legal wall placements by checking:
   - supply
   - on-board anchor
   - no overlap
   - no crossing
   - path condition for **both** players

`apply_action()` decodes the integer, validates that it is legal in the current
state, and returns the next state. Illegal actions raise `ValueError`.

## Error handling

Error handling should be strict and explicit:

- illegal actions raise `ValueError` with contextual detail
- malformed coordinates or impossible decoded actions fail loudly
- helper-layer invariants are enforced close to the source, not silently coerced

The wall path-condition check should use graph search over wall-unblocked orthogonal
movement so walls are rejected for the real rules reason rather than via brittle
special cases.

## Success criteria (binary, machine-checkable)

1. `pyspiel.load_game("quoridor", {"seed": ...})` works and produces a playable
   2-player game.
2. `QuoridorGameWrapper(seed=...)` returns a `PyspielGameAdapter` compatible with
   the existing `Game` / `State` protocol.
3. The engine enforces the repository's 2-player technical rules doc, including:
   - orthogonal movement with walls
   - straight jumps
   - lateral jumps triggered by wall or board-edge blockage
   - wall overlap / crossing rejection
   - all-players path-condition enforcement
4. Illegal actions are rejected deterministically.
5. Seeded random playouts do not hit impossible states or dead turns.
6. The feature lands without requiring any web/UI or neural-training changes.

## Testing strategy

Favor black-box, macro-leaning tests under `tests/games/quoridor/`:

- **Setup / initial state:** starting positions, wall counts, and first-player turn
- **Pawn movement:** orthogonal movement, wall blocking, straight jump, lateral jump
- **Wall legality:** overlap rejection, crossing rejection, off-board rejection, path
  condition rejection
- **Terminal / returns:** goal-row win detection and payoff shape
- **Wrapper compatibility:** `QuoridorGameWrapper` works through `PyspielGameAdapter`
- **Random conformance:** seeded random playouts keep producing legal states and stop
  at terminal outcomes

Not in scope for this spec:

- Quoridor neural training
- UI rendering
- performance tuning beyond ordinary correctness-driven implementation choices

## Forbidden zones (parallel-feature-development)

Globs this feature owns and exclusively writes:

- `src/table_peak/games/quoridor/**`
- `tests/games/quoridor/**`

Shared files this feature may touch if needed:

- `src/table_peak/games/__init__.py`
- `docs/superpowers/in-flight.md`

Reads but does not modify:

- `docs/games/quoridor-rules.md`
- `src/table_peak/games/_pyspiel_adapter.py`
- existing training and runner modules

## Open questions / risks

- **Action encoding vs helper ergonomics.** Stable integer ranges are the right public
  surface, but the implementation should still use typed internal helpers so the state
  code does not become number-heavy.
- **Path-condition cost.** Re-checking connectivity on every candidate wall can be
  expensive; correctness comes first, but the implementation should keep the search
  straightforward and local rather than prematurely optimizing.
- **Jump edge cases.** Lateral-jump rules are the most ambiguity-prone part of
  Quoridor; tests should mirror the rules doc examples closely.

## Deferred

- 4-player Quoridor
- Quoridor observation / encoder work for neural training
- Human-play surfaces
- Cross-game abstraction beyond what this package naturally needs
