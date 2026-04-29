# Table Peak — v1 Design

**Date:** 2026-04-29
**Status:** Draft, awaiting user review

## Goal

Build the foundation of a multi-game RL framework, starting with tic-tac-toe as a smoke test (no learning). The v1 deliverable proves the framework runs games end-to-end and plugs in agents cleanly. Future iterations add learning agents, then partial-information card games (Skyjo, Skull King, 6 nimmt!, Coinche), with a long-term ambition of superhuman performance and strategy exploration on at least one of those games.

## Non-goals (v1)

- No learning of any kind (no Q-learning, no neural networks, no self-play training).
- No external framework integration (no `open_spiel`, `pgx`, `gymnasium`, `PettingZoo`, `RLlib`).
- No CLI, no UI, no metrics dashboards.
- No partial-information mechanics, no chance nodes, no simultaneous moves.
- No CI.

These are deferred deliberately — see [Deferred](#deferred-explicit-yagni) for the full list.

## Architecture

**Style:** functional core / imperative shell. Game rules and agent policies are pure transformations; the runner is a thin imperative driver.

```
src/table_peak/
├── games/      # core: rules. pure. no I/O, no torch.
├── agents/     # core: policies. pure (state → action). no I/O.
└── runner/     # shell: orchestration. drives the game loop.
```

**Why not full hexagonal architecture for v1?** Hexagonal earns its keep when there's a real adapter zoo (DB, REST API, message queue, external services). v1 has none. Honor the principle (pure core, infrastructure at the edges); skip the ports/adapters folders. Re-evaluate when training adds real adapter boundaries (checkpoints, configs, logging).

**Conceptual shape borrowed from `open_spiel`** (`current_player`, `legal_actions`, `apply_action`, `is_terminal`, `returns`, `information_state`). Swapping `open_spiel` in later — or wrapping it — is mechanical.

## Components

```
src/table_peak/
├── __init__.py
├── games/
│   ├── __init__.py
│   ├── base.py           # Game, State Protocols
│   └── tic_tac_toe.py    # TTT implementation
├── agents/
│   ├── __init__.py
│   ├── base.py           # Agent Protocol
│   ├── random.py         # RandomAgent
│   └── minimax.py        # MinimaxAgent (TTT-shaped for v1)
└── runner/
    ├── __init__.py
    └── play.py           # play_game, play_matches, Outcome, MatchStats

tests/
├── games/
│   └── test_tic_tac_toe.py
├── agents/
│   ├── test_random.py
│   └── test_minimax.py
└── runner/
    └── test_play.py
```

## Interfaces

All as `typing.Protocol` (PEP 544) — duck-typed, no inheritance ceremony.

### `State`

Immutable. `apply_action` returns a new state.

```python
class State(Protocol):
    @property
    def current_player(self) -> PlayerId: ...
    def legal_actions(self) -> Sequence[Action]: ...
    def apply_action(self, action: Action) -> "State": ...
    @property
    def is_terminal(self) -> bool: ...
    def returns(self) -> dict[PlayerId, float]: ...
```

### `Game`

A `State` factory plus meta-information.

```python
class Game(Protocol):
    @property
    def num_players(self) -> int: ...
    def new_initial_state(self) -> State: ...
```

### `Agent`

A pure policy.

```python
class Agent(Protocol):
    def act(self, state: State) -> Action: ...
```

### Type aliases

```python
PlayerId = int
Action = int  # promotes to TypeVar when actions get richer (cards, bids)
```

### Decisions and tradeoffs

- **Immutable `State`** vs. open_spiel's `clone()`-based mutation. For v1, immutability is cheap, removes a class of bugs, and makes tree search natural (no defensive cloning). When perf matters (Coinche + MCTS at scale), revisit — add a mutable variant or wrap `open_spiel.State`. Choice, not constraint.
- **`returns()` is `dict[PlayerId, float]`** — not `float`, not `tuple`. TTT returns `{0: 1.0, 1: -1.0}` for a P0 win; same shape scales to 4-player Coinche team rewards.
- **What's *not* on the Protocol yet** — `is_chance_node()`, `chance_outcomes()`, `information_state(player)`, `acting_players` (set, for simultaneous moves). TTT needs none. Stubbing them now is ceremony. Add when the first game needs them (Skyjo for `information_state`, 6 nimmt! for simultaneous moves).
- **`Agent.act` is pure** — no learning state mutation in v1. When training arrives, learning lives in a separate `train_step(agent, batch)` function, keeping the policy interface stable across frozen and training agents.

## Data flow

### Game loop

```python
def play_game(game: Game, agents: dict[PlayerId, Agent]) -> Outcome:
    state = game.new_initial_state()
    history: list[tuple[State, Action]] = []
    while not state.is_terminal:
        player = state.current_player
        action = agents[player].act(state)
        history.append((state, action))
        state = state.apply_action(action)
    return Outcome(state.returns(), history, len(history))
```

The runner doesn't know about TTT, doesn't know about random/minimax — it just orchestrates.

### `Outcome`

```python
@dataclass(frozen=True)
class Outcome:
    returns: dict[PlayerId, float]
    trajectory: list[tuple[State, Action]]
    num_moves: int
```

Trajectory included even though v1 doesn't train. Free (`list.append`), gives debug-replays immediately, stable interface for future training.

### Match runner

```python
def play_matches(
    game: Game,
    agent_a: Agent,
    agent_b: Agent,
    n: int,
    swap_sides: bool = True,
    seed: int | None = None,
) -> MatchStats: ...

@dataclass(frozen=True)
class MatchStats:
    n_games: int
    wins: dict[PlayerId, int]
    draws: int
    mean_returns: dict[PlayerId, float]
```

`swap_sides=True` runs half with A as P0, half as P1, then aggregates — removes first-mover bias (TTT P0 wins ~58% under random play; comparing agents without side-swap produces misleading numbers).

### Randomness

- Stochastic agents (e.g., `RandomAgent`) take a `random.Random` instance via `__init__`. No global `random` module use.
- Match runner takes optional `seed: int | None`, threads a single `Random` through.
- TTT itself is fully deterministic in v1 (no chance node).

### Error handling

Light. `apply_action` raises `ValueError` on illegal actions. `play_game` raises if the `agents` keys mismatch `game.num_players`. No custom exception hierarchy until something motivates it.

## Testing

Aligned with project test guidelines: macro, black-box, fast.

**Macro tests (sociable, real implementations):**

- TTT rules through public API: hand-crafted sequences (P0 diagonal win, draw, illegal action raises).
- Runner end-to-end: `play_game` returns a well-formed `Outcome`; trajectory length matches `num_moves`.
- Match statistics with fixed seed: `play_matches(..., n=1000, seed=42)` produces exact reproducible counts.
- Minimax behavior:
  - Vs. random over 200 seeded games: minimax never loses.
  - Vs. itself over 50 seeded games: every game draws.
  - Hand-crafted "win in one" / "must block" positions.

**What we don't test:** internal pattern checks, recursion bookkeeping — those are exercised through macro behavior.

**Static layer:**

- `mypy --strict`
- `ruff check` (lint) and `ruff format`

**No coverage gate.** Coverage is a metric, not a goal.

**Hypothesis (property-based):** deferred until a real bug motivates it.

**Test layout** mirrors `src/`. `pytest` runs in <1s for v1.

## Tooling

| Concern | Choice | Why |
|---|---|---|
| Python | **3.12** | Wide library compat, modern type features, mature. |
| Package / venv / runner | **`uv`** (Astral) | Single tool, fast, current standard. |
| Lint + format | **`ruff`** | Replaces black + isort + flake8. |
| Type checker | **`mypy --strict`** | Mature, Protocol-aware. |
| Tests | **`pytest`** | De facto standard. |
| Pre-commit | **`pre-commit`** with `ruff` + `mypy` hooks | Same as `exposition_rag` setup. |
| Project metadata | **`pyproject.toml`** with `hatchling` backend | uv's default, PEP 621. |

## Deferred (explicit YAGNI)

These are deliberately out of v1 scope. They re-enter the design when concrete need shows up.

- **Learning of any kind** — Q-learning (tabular or neural), MCTS, AlphaZero, CFR, NFSP.
- **External frameworks** — `open_spiel`, `pgx`, `gymnasium`, `PettingZoo`, `RLlib`. Re-evaluate at first partial-info game.
- **Configuration system** — Hydra, OmegaConf, plain YAML.
- **Logging / metrics** — `print()` is enough. W&B, TensorBoard, MLflow later.
- **Hexagonal ports/adapters folders** — re-evaluate when training adds real adapter boundaries.
- **CLI / UI** — `python -m` invocations and direct API use suffice for v1.
- **CI** — local pre-commit + manual `uv run pytest` suffice for solo work.
- **Property-based testing** — re-evaluate if game-state invariants get tricky.
- **Makefile / taskfile** — `uv run …` commands are short enough for v1.
- **`.editorconfig`** — nice-to-have, not load-bearing for solo work.

## Future games — design implications (informational)

The long-term targets (Skyjo, Skull King, 6 nimmt!, Coinche) bring concrete extensions. Not implemented in v1, but the v1 interface is shaped to accept them without an interface rewrite.

| Aspect | TTT | Future games |
|---|---|---|
| Players | 2 | 2–10, variable |
| Information | Perfect | Hidden hands |
| Randomness | None | Card deals (chance nodes) |
| Move structure | Sequential | Sometimes simultaneous (6 nimmt!) |
| Phases | Single | Bidding then play (Skull King, Coinche) |
| Teams | None | Yes (Coinche) |

Concretely:

- `dict[PlayerId, ...]` for rewards, agents, wins — already scales to N players.
- `Action = int` will need promotion to a generic when actions become cards/bids.
- `is_chance_node()`, `chance_outcomes()`, `information_state(player)` get added on the Protocol.
- `acting_players` (set) replaces or complements `current_player` (singleton) for simultaneous-move games.
- Hexagonal-flavored adapter boundaries appear when checkpoints / configs / logging arrive.

## Open questions / risks

- **None blocking v1.** TTT smoke test is small enough that the design choices above carry it.
- **Mid-term risk:** when partial-info games arrive, the choice between adopting `open_spiel` and rolling our own CFR engine is consequential. Out of scope for the v1 plan; revisit before starting Skyjo.
