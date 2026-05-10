# Skyjo Engine — Design

**Date:** 2026-05-10
**Status:** Draft, awaiting user review
**Slug:** `skyjo-engine`

## Goal

Ship a Skyjo game engine in `src/table_peak/games/skyjo/` that:

- Implements the full ruleset documented in `docs/games/skyjo-rules.md` — single round, parameterized 2–8 players.
- Lives as a `pyspiel.Game` + `pyspiel.State` + `Observer` (open_spiel custom-game pattern, pure Python — no compiled extensions).
- Exposes a wrapper Port that adapts `pyspiel.State` to our existing `games/base.py` `State` / `Game` Protocols, so `runner/play.py`, `agents/`, and (later) `web/` can drive Skyjo without importing `pyspiel`.

## Non-goals (explicit YAGNI)

- No human-play UI / web renderer for Skyjo (next feature).
- No bespoke Skyjo agents (random / heuristic / NN / CFR). open_spiel's built-in `RandomAgent` is sufficient for smoke tests.
- No multi-round / game-to-100 driver. Single round only — design preserves the 1→3 evolution path: the State exposes `round_scores()` for a future driver, and no first-round-only assumptions live inside the engine.
- No training. CFR / NFSP / PSRO via open_spiel comes after the engine ships.
- No retrofit of TTT into open_spiel. TTT stays home-grown.
- No simultaneous-dynamics flag. Initial-reveal is sequential blind commit + deterministic synchronized reveal (see "Initial reveal").
- No multi-process / async play. Single-process is fine for the engine.

## Success criteria (binary, machine-checkable)

1. **pyspiel conformance.** Built-in `random_sim_test` and `playthrough_test` pass for `num_players ∈ {2, 3, 4, 6, 8}` over many seeded runs. Required because these test the State invariants that CFR / NFSP rely on.
2. **Hand-crafted scenario tests pass.** Column-erase on a freshly-flipped triple; last-turn-for-everyone trigger; round-ender doubling — including tie-at-lowest-triggers-doubling per the rules doc; deck exhaustion mid-round.
3. **TTT regression.** Existing TTT tests pass unchanged. `runner/`, `agents/random.py`, `agents/minimax.py`, `agents/neural.py`, `web/`, `training/` are not modified.
4. **Wrapper Port.** `runner.play_game(SkyjoGameWrapper(num_players=2), {0: RandomAgent(...), 1: RandomAgent(...)})` (using the existing `agents/random.py`) returns a well-formed `Outcome` whose per-player `returns` matches the underlying `pyspiel.State.returns()`. `play_matches(..., n=200, seed=42)` is reproducible across runs (same seed ⇒ same `MatchStats`).
5. **Static layer.** `mypy --strict` and `ruff check` pass on the new code.

## Architectural decisions

### Why open_spiel here, not home-grown

Logged in `~/.claude/projects/.../memory/project_open_spiel_adoption.md`. The TTT-v2 trajectory called for home-grown training; the user chose to adopt open_spiel for partial-info games starting here, against this assistant's recommendation. The decisive argument is that CFR / NFSP / PSRO / MCCFR are already implemented inside open_spiel and expect `pyspiel.State` directly. Writing Skyjo as a `pyspiel.Game` makes those algorithms available to us at training time without retrofitting.

### Engine = single round, with hooks for future multi-round

Rationale: matches what published Skyjo RL work models; smaller State; easier to test exhaustively; CFR-friendly tree depth. Two design hooks preserve the 1→3 evolution path:

- The terminal `pyspiel.State` subclass exposes a `round_scores() -> dict[int, int]` method returning the **raw integer round score** per player (post-doubling). The wrapper adapter forwards it. The future multi-round driver sums these across rounds.
- `pyspiel.State.returns()` is the **utility** view (lower raw score = higher utility — see "Utility convention"). The driver uses `round_scores()`, not `returns()`, for cumulative bookkeeping.
- No "this is the only round" assumption inside the engine: setup logic is parameterized so a future driver can hand it a fresh shuffle seed per round.

### Players: parameterized 2–8

`num_players` is a `pyspiel.Game` parameter (open_spiel's `GameType.parameter_specification`). Validated to `[2, 8]` at game construction. Action space, observer tensor shape, and initial-deal logic all derive from `num_players`. Tests cover at least 2, 4, and 8.

### Initial reveal: sequential blind commit + synchronous reveal

The rules say "simultaneously," but `GameType.dynamics = SEQUENTIAL` is the clean fit for open_spiel's main algorithm code paths. Modeling that preserves the strategic content of true simultaneity:

1. **Deal phase** — chance nodes deal 12·num_players cards from the shuffled 150-card deck into per-player 4×3 grids (face-down for everyone).
2. **Setup-commit phase** — sequential decision nodes in fixed convention order (player 0, 1, …, num_players−1). Each player picks an unordered position pair `(i, j)` with `i ≠ j` from their 12 face-down slots. **The committed pair enters that player's own information state but does NOT enter other players' information states.**
3. **Synchronous reveal** — after the last player commits, a deterministic state transition exposes all 2·num_players chosen card values to public knowledge in one step (no per-card chance node, since the values were already determined by the deal).
4. **Starting player determination** — highest sum-of-two among revealed pairs; ties broken by a fixed-RNG draw among the tied players (deterministic given the game seed). This matches the rules-doc `[CHOSEN]` policy.

This is extensive-form imperfect-information done right. CFR is built for it. There is no `SIMULTANEOUS` GameType to opt into.

### Action encoding (single integer namespace)

`pyspiel` actions are integers. Skyjo's distinct actions are bounded:

- `RevealInitial(i, j)`: unordered pairs over 12 slots → `C(12, 2) = 66` actions.
- `TakeDiscardAndReplace(i)`: up to 12 slots → up to 12 actions (legal subset depends on current grid size after eliminations).
- `DrawDeck`: 1 action.
- `ReplaceFromHand(i)`: up to 12 actions.
- `DiscardAndFlip(i)`: up to 12 actions (legal only on face-down slots).

**Encoding strategy:** disjoint integer ranges, one per action family. The encoding is a closed-form function of `(family, args)` with a matching decoder. `num_distinct_actions` is the static union size (~103). Legal-action computation lives on the State per current phase / branch.

This keeps the action namespace stable across player counts (a 2-player game and an 8-player game share the same action IDs — the action is per-player, not per-table).

### Utility convention

Skyjo is "lowest score wins." open_spiel's `returns()` convention is "higher is better." Two reasonable mappings:

- **Raw negation** — `returns(p) = -round_score(p)`. Bounded by `±max_grid_score` plus the doubling factor. Simple. Multi-round driver inverts.
- **Rank-based** — `returns(p) ∈ {-1, 0, +1}` for last/tie/first place per round. Matches a standard "win/lose" framing; loses information about score margin.

Decision: **raw negation**. CFR/NFSP work better with informative reward; rank-collapse loses signal that the game itself rewards (winning by a wide margin is genuinely better in Skyjo's multi-round meta-game). `min_utility` and `max_utility` are computed as theoretical bounds parameterized by `num_players`.

### Information state design

Per-player information state encodes:

- **My grid**: 12 slots × `(face-up | face-down | eliminated)`, with the value for face-up slots and a sentinel for face-down / eliminated. Eliminated columns shrink the grid below 12.
- **Opponents' grids**: identical structure, but face-down slots show only the sentinel — values are hidden.
- **Discard pile top** (value, public).
- **Draw pile size** (count only — order is hidden).
- **Transient drawn-card value** — when I'm the active player in Branch (b) between `DrawDeck` and the sub-action, this value is in MY info state but no one else's.
- **Round-end trigger flag** — and per-player remaining-final-turns counter, both public.
- **Cumulative scores from prior rounds** — zero in single-round mode; field is present so the multi-round driver doesn't need a State surgery later.
- **Phase / branch indicator** — `setup_commit | main_play_root | branch_b_subaction` so a policy network knows which legal-action family is active.

Both string (`information_state_string`) and tensor (`information_state_tensor`) views are implemented. The string view is human-readable for tests and debugging; the tensor view is the float32 array CFR/NFSP consume.

### Wrapper Port — pyspiel.State adapted to our State Protocol

Lives in `src/table_peak/games/_pyspiel_adapter.py` (game-agnostic, anticipating future open_spiel-backed games — Skull King, 6 nimmt!, Coinche). Provides:

- `PyspielStateAdapter` — wraps a `pyspiel.State`, implements our `State` Protocol surface (`current_player`, `legal_actions`, `apply_action`, `is_terminal`, `returns`).
- `PyspielGameAdapter` — wraps a `pyspiel.Game`, implements our `Game` Protocol surface (`num_players`, `new_initial_state`).
- `SkyjoGameWrapper` — convenience constructor in `src/table_peak/games/skyjo/__init__.py` that loads the registered Skyjo game and returns a `PyspielGameAdapter`.

**Two semantic translations the adapter is responsible for:**

1. **Chance nodes are auto-resolved before returning control.** Our `State` Protocol has no `is_chance_node` concept (and the user has not asked to introduce one). The adapter, on each `new_initial_state` and after every `apply_action`, internally drives chance nodes to completion using the open_spiel game's RNG (seeded). This preserves the home-grown agent contract: agents never see chance nodes. They observe, they act, the world advances — including any chance — to the next decision point.
2. **Mutable underlying state, immutable adapter view.** `pyspiel.State` is mutable (`apply_action` mutates in place + `clone()` is the copy escape hatch). Our `State` Protocol is immutable (`apply_action` returns a new state). The adapter's `apply_action` clones the underlying `pyspiel.State`, applies on the clone, and returns a new `PyspielStateAdapter` wrapping the clone.

The seeding for the auto-resolution chance loop is a constructor-time parameter on `PyspielGameAdapter`. When called from `runner.play_matches(..., seed=42)`, the runner threads its own `random.Random` through, deriving per-game seeds for the adapter — same pattern as v1.

### Module layout

```
src/table_peak/
├── games/
│   ├── base.py                    # unchanged (existing State/Game Protocols)
│   ├── tic_tac_toe.py             # unchanged
│   ├── _pyspiel_adapter.py        # NEW — generic pyspiel.State→Protocol adapter
│   └── skyjo/                     # NEW — Skyjo engine
│       ├── __init__.py            # exposes SkyjoGameWrapper convenience
│       ├── game.py                # pyspiel.Game subclass + GameType + GameInfo
│       ├── state.py               # pyspiel.State subclass — turn logic, phases
│       ├── observer.py            # pyspiel Observer — info_state_string/tensor
│       ├── actions.py             # action encoding/decoding, legal-action helpers
│       ├── deck.py                # 150-card composition, shuffle helpers
│       ├── grid.py                # 4x3 grid + elimination + face-up/down accounting
│       └── scoring.py             # round score + doubling + tiebreak rules
└── …  (agents/, runner/, web/, training/ untouched)

tests/
├── games/
│   ├── test_tic_tac_toe.py        # unchanged
│   └── skyjo/                     # NEW
│       ├── test_conformance.py    # pyspiel random_sim_test + playthrough_test
│       ├── test_setup.py          # initial reveal + starting-player rules
│       ├── test_turn.py           # Branch (a), Branch (b1), Branch (b2)
│       ├── test_column_erase.py   # three-of-a-kind elimination
│       ├── test_round_end.py      # last-turn-for-everyone + scoring + doubling
│       ├── test_deck_exhaustion.py
│       ├── test_observer.py       # info_state hides what it must hide
│       └── test_wrapper.py        # adapter end-to-end with runner.play_game
```

**Why a package rather than a single `skyjo.py` file:** Skyjo state has at least four orthogonal concerns (deck, grid, scoring, action encoding) and three lifecycle phases (setup, main play, scoring). Single-file would cross 800 lines and bury the concerns. The package layout is one-thing-per-file: each file under ~200 lines, each test module mirrors one concern.

### Tooling / dependencies

| Concern | Choice | Why |
|---|---|---|
| Game framework | `open_spiel` (Python wheels) | Strategic decision (see top). |
| Type checker | `mypy --strict` | Same as v1/v2. Where `open_spiel` lacks stubs, scope `# type: ignore[attr-defined]` to the import line, not the call sites. |
| Lint / format | `ruff` | Same as v1/v2. |
| Tests | `pytest` | Same as v1/v2. |
| Reproducibility | Seeded `random.Random` threaded by runner; `pyspiel.Game` accepts a seed parameter via the adapter | Matches v1 randomness story. |

`open_spiel` is added as a runtime dep in `pyproject.toml`. No build-time toolchain change beyond `uv sync`.

### Edge cases & rule fidelity

The implementation follows `docs/games/skyjo-rules.md` literally, including every `[CHOSEN]` policy:

- Column elimination shrinks the grid; eliminated columns count as "not face-down" for the round-end trigger.
- Round-ender doubling triggers on tie at lowest (strict literal reading per the rules doc).
- Doubling applies to negative round-ender scores too (makes them more negative).
- Deck exhaustion: keep current discard top aside, shuffle the rest, place face-down as new draw pile, return kept top to discard.
- Branch (b2) `DiscardAndFlip` is illegal when the player has zero face-down slots remaining.
- Replacing a face-up card with a same-value card is legal; column elimination is re-checked after.
- Face-down own cards are hidden from the owner. Skyjo's defining symmetric ignorance.

Each of these has at least one targeted test in the scenario suite.

### Error handling

- **Illegal action passed to `_apply_action`** — raise via `_legal_actions` mismatch; `apply_action`'s pyspiel layer surfaces it as a Python exception. Tests assert this for hand-crafted illegal cases.
- **Adapter receives a `pyspiel.State` from a game it doesn't recognize** — type-check at adapter construction, raise `TypeError` early.
- **Multi-process / fork safety** — out of scope. Single-process engine. Document in README only if the user later asks.

### Forbidden zones (parallel-feature-development)

Globs this feature owns and exclusively writes to. Sibling features must not touch:

- `src/table_peak/games/skyjo/**`
- `src/table_peak/games/_pyspiel_adapter.py`
- `tests/games/skyjo/**`

Globs this feature **reads but does not modify**:

- `src/table_peak/games/base.py` (existing State/Game Protocols — used unchanged)
- `src/table_peak/runner/**` (regression target only)
- `docs/games/skyjo-rules.md` (rule source of truth)

Shared files this feature modifies (sibling features must coordinate):

- `pyproject.toml` — add `open_spiel` runtime dep
- `uv.lock` — regenerated by `uv lock` after the dep is added

## Testing strategy

Aligned with project test guidelines: macro, black-box, fast.

**Layered:**

1. **Conformance layer (pyspiel built-ins).** `random_sim_test` runs the game forward with random actions for many seeded episodes per `num_players`, validating internal invariants (legal-action consistency, terminal coherence, returns shape, info-state stability). `playthrough_test` produces a deterministic playthrough text and diffs it against a checked-in golden — catches accidental rule changes.

2. **Scenario layer (hand-crafted).** Each rule with a `[CHOSEN]` policy gets its own test. Each branch of the turn structure gets at least one test. Edge cases enumerated in the rules doc each get a test.

3. **Wrapper layer.** End-to-end via `runner.play_game(SkyjoGameWrapper(num_players=2), {0: …, 1: …})`. Reproducibility: `play_matches(..., n=200, seed=42)` produces identical `MatchStats` across runs.

4. **Static layer.** `mypy --strict` and `ruff check`.

**What we don't test:** observer tensor numerical values beyond shape and a small hand-crafted check (the tensor format is open_spiel's serialization concern, not ours); pyspiel internal cloning; chance-node probability distributions beyond "outcomes sum to ~1" (the framework owns that).

**Property-based testing:** deferred until a real bug motivates it. The conformance harness is doing the same job with random inputs.

## Open questions / risks

- **open_spiel Python custom-game API compatibility on Apple Silicon + Python 3.12.** Validated at the spike level; the `random_sim_test` running over a few seeds in CI is the binding check. Risk is small given mature wheels in 2026, but worth a smoke-install before plan-writing kicks off.
- **Performance.** Pure-Python pyspiel custom games are noticeably slower than C++ built-ins. For Skyjo's tree size + rollout-style RandomAgent play this is fine; for actual CFR training on 8-player games it may matter. **Out of scope for this engine spec.** If it bites later, the route is rewriting hot paths in Cython or in C++ following open_spiel's contribution guide — both are post-engine work.
- **Multi-round driver.** Path documented; not implemented. Adding it later may surface API friction (e.g., the multi-round driver wanting to short-circuit `pyspiel.State` cloning for performance). **Out of scope for this spec.**
- **TTT cohabitation under one runner.** `runner.play_game` must work with both `TicTacToe` (home-grown `Game` Protocol) and `SkyjoGameWrapper` (adapter over `pyspiel.Game`). The Protocol is duck-typed, so the runner doesn't care — but a regression test for both side by side is part of the wrapper-layer test suite.

## Deferred (explicit YAGNI for this spec)

- Multi-round / game-to-100 driver.
- Skyjo agents (random / heuristic / NN / CFR / NFSP).
- CFR/NFSP/PSRO training runs.
- Web-UI rendering of Skyjo grids (next feature).
- Performance optimization beyond "doesn't time out CI."
- TTT migration into open_spiel.
- Generic `pyspiel`-game registration system beyond what Skyjo needs (we register one game; deferred until the second open_spiel-backed game arrives).
- Cython / C++ acceleration of the Skyjo State.

## Future work — design implications (informational)

Once this engine ships, the next features in roughly increasing order:

1. **Web UI for Skyjo human-play** — adds `src/table_peak/web/renderers/skyjo.py` and a Skyjo entry in the new-game form. The wrapper Port shipped here means the web layer never imports `pyspiel`.
2. **Multi-round driver** — `src/table_peak/games/skyjo/multi_round.py` (~50–100 lines) wrapping the engine; cumulative-score loop until any player ≥ 100.
3. **Random / heuristic Skyjo agents** — over the wrapper Port; reusable in the web UI directly.
4. **CFR / NFSP training** — direct on `pyspiel.State`, bypassing the wrapper. Algorithms come from open_spiel.
