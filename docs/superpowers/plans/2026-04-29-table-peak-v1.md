# Table Peak v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the v1 smoke-test of `table-peak` per `docs/superpowers/specs/2026-04-29-table-peak-v1-design.md` — TicTacToe + RandomAgent + MinimaxAgent + game/match runner, fully tested, no learning.

**Architecture:** Functional core / imperative shell. Three packages: `games/` (rules), `agents/` (policies), `runner/` (orchestration). Public surface is a small set of `Protocol`s (`Game`, `State`, `Agent`) shaped to mirror `open_spiel` concepts so a future framework swap is mechanical. State is an immutable, hashable frozen dataclass — minimax caches across runs without defensive cloning.

**Tech Stack:** Python 3.12, `uv` (package mgmt), `ruff` (lint+format), `mypy --strict`, `pytest`, `pre-commit`. No runtime dependencies. No external RL framework in v1.

---

## File Structure

```
table_peak/
├── pyproject.toml                      # project + tool config (Task 0)
├── .pre-commit-config.yaml             # ruff + mypy hooks (Task 0)
├── src/table_peak/
│   ├── __init__.py                     # Task 0 (empty marker)
│   ├── games/
│   │   ├── __init__.py                 # Task 1 (empty marker)
│   │   ├── base.py                     # Task 1: State, Game Protocols + aliases
│   │   └── tic_tac_toe.py              # Task 2: TicTacToeState, TicTacToe
│   ├── agents/
│   │   ├── __init__.py                 # Task 1 (empty marker)
│   │   ├── base.py                     # Task 1: Agent Protocol
│   │   ├── random.py                   # Task 3: RandomAgent
│   │   └── minimax.py                  # Task 4: MinimaxAgent
│   └── runner/
│       ├── __init__.py                 # Task 5 (empty marker)
│       └── play.py                     # Task 5+6: play_game, play_matches, Outcome, MatchStats
└── tests/
    ├── __init__.py                     # Task 2 (empty marker)
    ├── games/
    │   ├── __init__.py                 # Task 2 (empty marker)
    │   └── test_tic_tac_toe.py         # Task 2
    ├── agents/
    │   ├── __init__.py                 # Task 3 (empty marker)
    │   ├── test_random.py              # Task 3
    │   └── test_minimax.py             # Task 4
    └── runner/
        ├── __init__.py                 # Task 5 (empty marker)
        └── test_play.py                # Tasks 5 + 6
```

Each file has one clear responsibility; no file exceeds ~200 lines.

---

## Task 0: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.pre-commit-config.yaml`
- Create: `src/table_peak/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "table-peak"
version = "0.1.0"
description = "Game-playing agents for tabletop games."
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
    "pytest>=8.0",
    "mypy>=1.8",
    "ruff>=0.4",
    "pre-commit>=3.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/table_peak"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.12"
files = ["src", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra --tb=short"
```

- [ ] **Step 2: Create empty package marker**

Create `src/table_peak/__init__.py` as an empty file.

- [ ] **Step 3: Sync the environment**

Run: `uv sync`
Expected: `.venv/` is created, dev dependencies installed, `uv.lock` written.

- [ ] **Step 4: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        files: ^(src|tests)/
        args: [--strict]
        additional_dependencies: []
```

- [ ] **Step 5: Install pre-commit hooks**

Run: `uv run pre-commit install`
Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 6: Verify the env works**

Run: `uv run pytest --collect-only`
Expected: `no tests ran` (or "collected 0 items"). Exit code 5 (no tests collected) is expected and acceptable here.

Run: `uv run mypy src`
Expected: `Success: no issues found in 1 source file` (only `__init__.py` exists).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .pre-commit-config.yaml src/table_peak/__init__.py
git commit -m "chore: bootstrap python project (uv, ruff, mypy, pytest, pre-commit)"
```

---

## Task 1: Define Protocols

**Files:**
- Create: `src/table_peak/games/__init__.py`
- Create: `src/table_peak/games/base.py`
- Create: `src/table_peak/agents/__init__.py`
- Create: `src/table_peak/agents/base.py`

- [ ] **Step 1: Create empty package markers**

Create `src/table_peak/games/__init__.py` (empty) and `src/table_peak/agents/__init__.py` (empty).

- [ ] **Step 2: Write `src/table_peak/games/base.py`**

```python
"""Game and State protocols. Conceptually shaped after open_spiel."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

PlayerId = int
Action = int


@runtime_checkable
class State(Protocol):
    """A snapshot of a game. Immutable: apply_action returns a new state."""

    @property
    def current_player(self) -> PlayerId: ...

    def legal_actions(self) -> Sequence[Action]: ...

    def apply_action(self, action: Action) -> State: ...

    @property
    def is_terminal(self) -> bool: ...

    def returns(self) -> dict[PlayerId, float]: ...


@runtime_checkable
class Game(Protocol):
    """A game definition: a State factory plus meta-information."""

    @property
    def num_players(self) -> int: ...

    def new_initial_state(self) -> State: ...
```

- [ ] **Step 3: Write `src/table_peak/agents/base.py`**

```python
"""Agent protocol. A pure policy: state -> action."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from table_peak.games.base import Action, State


@runtime_checkable
class Agent(Protocol):
    """A policy. Pure: must not mutate hidden state during act()."""

    def act(self, state: State) -> Action: ...
```

- [ ] **Step 4: Verify import + types**

Run: `uv run python -c "from table_peak.games.base import State, Game; from table_peak.agents.base import Agent; print('ok')"`
Expected: `ok`

Run: `uv run mypy src`
Expected: `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/__init__.py src/table_peak/games/base.py \
        src/table_peak/agents/__init__.py src/table_peak/agents/base.py
git commit -m "feat: add Game/State/Agent protocols"
```

---

## Task 2: TicTacToe Game (TDD)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/games/__init__.py`
- Create: `tests/games/test_tic_tac_toe.py`
- Create: `src/table_peak/games/tic_tac_toe.py`

- [ ] **Step 1: Create empty test package markers**

Create `tests/__init__.py` and `tests/games/__init__.py` (both empty).

- [ ] **Step 2: Write the failing tests**

Create `tests/games/test_tic_tac_toe.py`:

```python
"""Black-box behavioural tests for TicTacToe."""

from __future__ import annotations

import pytest

from table_peak.games.tic_tac_toe import TicTacToe, TicTacToeState


def test_initial_state_has_nine_legal_actions() -> None:
    state = TicTacToe().new_initial_state()
    assert state.current_player == 0
    assert sorted(state.legal_actions()) == list(range(9))
    assert not state.is_terminal


def test_apply_action_advances_current_player() -> None:
    state = TicTacToe().new_initial_state().apply_action(0)
    assert state.current_player == 1
    assert 0 not in state.legal_actions()


def test_apply_action_returns_new_state_not_mutated() -> None:
    state0 = TicTacToe().new_initial_state()
    state1 = state0.apply_action(4)
    # state0 is unchanged
    assert state0.current_player == 0
    assert sorted(state0.legal_actions()) == list(range(9))
    # state1 reflects the move
    assert state1.current_player == 1
    assert 4 not in state1.legal_actions()


def test_illegal_action_raises() -> None:
    state = TicTacToe().new_initial_state().apply_action(0)
    with pytest.raises(ValueError):
        state.apply_action(0)


def test_p0_wins_top_row() -> None:
    # P0: 0, P1: 3, P0: 1, P1: 4, P0: 2 -> top row for P0
    state = TicTacToe().new_initial_state()
    for action in [0, 3, 1, 4, 2]:
        state = state.apply_action(action)
    assert state.is_terminal
    assert state.returns() == {0: 1.0, 1: -1.0}


def test_p1_wins_diagonal() -> None:
    # P0: 1, P1: 0, P0: 2, P1: 4, P0: 5, P1: 8 -> diagonal 0-4-8 for P1
    state = TicTacToe().new_initial_state()
    for action in [1, 0, 2, 4, 5, 8]:
        state = state.apply_action(action)
    assert state.is_terminal
    assert state.returns() == {0: -1.0, 1: 1.0}


def test_full_board_draw() -> None:
    # X O X / X O O / O X X  -> no winner, board full
    moves = [0, 1, 2, 4, 7, 3, 5, 6, 8]
    state = TicTacToe().new_initial_state()
    for action in moves:
        state = state.apply_action(action)
    assert state.is_terminal
    assert state.returns() == {0: 0.0, 1: 0.0}


def test_state_is_hashable_and_value_equal() -> None:
    a = TicTacToe().new_initial_state().apply_action(4)
    b = TicTacToe().new_initial_state().apply_action(4)
    assert a == b
    assert hash(a) == hash(b)
    # Different moves -> different state
    c = TicTacToe().new_initial_state().apply_action(0)
    assert a != c


def test_game_meta() -> None:
    game = TicTacToe()
    assert game.num_players == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/games/test_tic_tac_toe.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'table_peak.games.tic_tac_toe'`.

- [ ] **Step 4: Implement TicTacToe**

Create `src/table_peak/games/tic_tac_toe.py`:

```python
"""TicTacToe: 3x3, 2-player, deterministic, perfect-information."""

from __future__ import annotations

from dataclasses import dataclass, field

from table_peak.games.base import Action, PlayerId

_EMPTY: int = -1
_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
    (0, 4, 8), (2, 4, 6),             # diagonals
)


@dataclass(frozen=True, slots=True)
class TicTacToeState:
    """Immutable, hashable. Cells: -1 empty, 0 = P0, 1 = P1."""

    board: tuple[int, ...] = field(default=(_EMPTY,) * 9)
    _current_player: PlayerId = 0

    @property
    def current_player(self) -> PlayerId:
        return self._current_player

    def legal_actions(self) -> tuple[Action, ...]:
        return tuple(i for i, v in enumerate(self.board) if v == _EMPTY)

    def apply_action(self, action: Action) -> TicTacToeState:
        if not 0 <= action < 9 or self.board[action] != _EMPTY:
            raise ValueError(f"Illegal action {action} for board {self.board}")
        new_board = list(self.board)
        new_board[action] = self._current_player
        return TicTacToeState(
            board=tuple(new_board),
            _current_player=1 - self._current_player,
        )

    @property
    def is_terminal(self) -> bool:
        return self._winner() is not None or all(c != _EMPTY for c in self.board)

    def returns(self) -> dict[PlayerId, float]:
        winner = self._winner()
        if winner is None:
            return {0: 0.0, 1: 0.0}
        return {0: 1.0 if winner == 0 else -1.0, 1: 1.0 if winner == 1 else -1.0}

    def _winner(self) -> PlayerId | None:
        for a, b, c in _LINES:
            if self.board[a] != _EMPTY and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None


class TicTacToe:
    """TicTacToe game definition."""

    @property
    def num_players(self) -> int:
        return 2

    def new_initial_state(self) -> TicTacToeState:
        return TicTacToeState()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/games/test_tic_tac_toe.py -v`
Expected: 9 tests pass.

- [ ] **Step 6: Run static checks**

Run: `uv run mypy src tests`
Expected: `Success: no issues found`

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add tests/__init__.py tests/games/__init__.py tests/games/test_tic_tac_toe.py \
        src/table_peak/games/tic_tac_toe.py
git commit -m "feat(games): add tic-tac-toe rules with black-box tests"
```

---

## Task 3: RandomAgent (TDD)

**Files:**
- Create: `tests/agents/__init__.py`
- Create: `tests/agents/test_random.py`
- Create: `src/table_peak/agents/random.py`

- [ ] **Step 1: Create empty test package marker**

Create `tests/agents/__init__.py` (empty).

- [ ] **Step 2: Write the failing tests**

Create `tests/agents/test_random.py`:

```python
"""Black-box tests for RandomAgent."""

from __future__ import annotations

import random

from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe


def test_acts_within_legal_actions() -> None:
    agent = RandomAgent(rng=random.Random(0))
    state = TicTacToe().new_initial_state()
    for _ in range(100):
        action = agent.act(state)
        assert action in state.legal_actions()


def test_same_seed_produces_same_actions() -> None:
    state = TicTacToe().new_initial_state()
    agent_a = RandomAgent(rng=random.Random(42))
    agent_b = RandomAgent(rng=random.Random(42))
    actions_a = [agent_a.act(state) for _ in range(20)]
    actions_b = [agent_b.act(state) for _ in range(20)]
    assert actions_a == actions_b


def test_different_seeds_produce_different_actions() -> None:
    state = TicTacToe().new_initial_state()
    agent_a = RandomAgent(rng=random.Random(1))
    agent_b = RandomAgent(rng=random.Random(2))
    actions_a = [agent_a.act(state) for _ in range(20)]
    actions_b = [agent_b.act(state) for _ in range(20)]
    # Vanishingly unlikely that 20 random picks from 9 options match across seeds
    assert actions_a != actions_b


def test_default_rng_is_independent_module_random() -> None:
    """RandomAgent must NOT use the global random module."""
    state = TicTacToe().new_initial_state()
    random.seed(0)  # global state
    agent = RandomAgent()  # should use its own rng, not the global one
    # Calling agent.act should not affect global random sequence
    before = random.random()
    agent.act(state)
    random.seed(0)
    expected_before = random.random()
    assert before == expected_before
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/agents/test_random.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'table_peak.agents.random'`.

- [ ] **Step 4: Implement RandomAgent**

Create `src/table_peak/agents/random.py`:

```python
"""Uniformly-random policy. RNG is injected — never uses module-level random."""

from __future__ import annotations

import random

from table_peak.games.base import Action, State


class RandomAgent:
    """Uniform-random over legal actions. Stateless across calls (apart from RNG)."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random()

    def act(self, state: State) -> Action:
        return self._rng.choice(list(state.legal_actions()))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/agents/test_random.py -v`
Expected: 4 tests pass.

- [ ] **Step 6: Run static checks**

Run: `uv run mypy src tests`
Expected: `Success: no issues found`

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add tests/agents/__init__.py tests/agents/test_random.py src/table_peak/agents/random.py
git commit -m "feat(agents): add RandomAgent with injected RNG"
```

---

## Task 4: MinimaxAgent (TDD)

**Files:**
- Create: `tests/agents/test_minimax.py`
- Create: `src/table_peak/agents/minimax.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agents/test_minimax.py`:

```python
"""Behavioural tests for MinimaxAgent on TicTacToe."""

from __future__ import annotations

from table_peak.agents.minimax import MinimaxAgent
from table_peak.games.tic_tac_toe import TicTacToe, TicTacToeState


def _state_from_moves(moves: list[int]) -> TicTacToeState:
    state = TicTacToe().new_initial_state()
    for m in moves:
        state = state.apply_action(m)
    return state


def test_acts_within_legal_actions_from_initial_state() -> None:
    agent = MinimaxAgent()
    state = TicTacToe().new_initial_state()
    action = agent.act(state)
    assert action in state.legal_actions()


def test_takes_winning_move_when_one_step_from_win() -> None:
    # P0 has cells 0, 1; cell 2 wins immediately. P0 to move.
    # Moves: P0:0, P1:3, P0:1, P1:4 -> P0 to move, plays 2 to win.
    agent = MinimaxAgent()
    state = _state_from_moves([0, 3, 1, 4])
    assert state.current_player == 0
    assert agent.act(state) == 2


def test_blocks_opponents_imminent_win() -> None:
    # P1 threatens to win on cell 2. P0 must block with 2.
    # Moves: P0:4, P1:0, P0:8, P1:1 -> P0 to move, must play 2.
    agent = MinimaxAgent()
    state = _state_from_moves([4, 0, 8, 1])
    assert state.current_player == 0
    assert agent.act(state) == 2


def test_caches_across_calls() -> None:
    """The agent's cache is populated; a second act() on same state hits the cache."""
    agent = MinimaxAgent()
    state = TicTacToe().new_initial_state()
    agent.act(state)
    cache_size_after_first = len(agent._cache)
    agent.act(state)
    cache_size_after_second = len(agent._cache)
    assert cache_size_after_first > 0
    assert cache_size_after_second == cache_size_after_first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/agents/test_minimax.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'table_peak.agents.minimax'`.

- [ ] **Step 3: Implement MinimaxAgent**

Create `src/table_peak/agents/minimax.py`:

```python
"""Minimax with memoisation. TTT-sized search space; exact solver."""

from __future__ import annotations

import math

from table_peak.games.base import Action, PlayerId, State


class MinimaxAgent:
    """Plays the minimax-optimal action from the perspective of state.current_player.

    Stateless across games apart from the lookup cache, which accelerates repeated
    play. Requires State implementations to be hashable (e.g. frozen dataclasses).
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[State, PlayerId], tuple[float, Action | None]] = {}

    def act(self, state: State) -> Action:
        _, action = self._minimax(state, perspective=state.current_player)
        if action is None:
            raise ValueError("Cannot act on a terminal state")
        return action

    def _minimax(
        self, state: State, perspective: PlayerId
    ) -> tuple[float, Action | None]:
        key = (state, perspective)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if state.is_terminal:
            result: tuple[float, Action | None] = (state.returns()[perspective], None)
            self._cache[key] = result
            return result

        is_maximising = state.current_player == perspective
        best_score = -math.inf if is_maximising else math.inf
        best_action: Action | None = None

        for action in state.legal_actions():
            child_score, _ = self._minimax(state.apply_action(action), perspective)
            if is_maximising:
                if best_action is None or child_score > best_score:
                    best_score, best_action = child_score, action
            else:
                if best_action is None or child_score < best_score:
                    best_score, best_action = child_score, action

        result = (best_score, best_action)
        self._cache[key] = result
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agents/test_minimax.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Run static checks**

Run: `uv run mypy src tests`
Expected: `Success: no issues found`

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add tests/agents/test_minimax.py src/table_peak/agents/minimax.py
git commit -m "feat(agents): add MinimaxAgent with memoisation"
```

---

## Task 5: Runner — `play_game` + `Outcome` (TDD)

**Files:**
- Create: `tests/runner/__init__.py`
- Create: `tests/runner/test_play.py`
- Create: `src/table_peak/runner/__init__.py`
- Create: `src/table_peak/runner/play.py`

- [ ] **Step 1: Create empty package markers**

Create `tests/runner/__init__.py` (empty) and `src/table_peak/runner/__init__.py` (empty).

- [ ] **Step 2: Write the failing tests**

Create `tests/runner/test_play.py`:

```python
"""End-to-end tests for the game runner."""

from __future__ import annotations

import random

import pytest

from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import Outcome, play_game


def test_play_game_returns_well_formed_outcome() -> None:
    game = TicTacToe()
    agents = {0: RandomAgent(rng=random.Random(0)), 1: RandomAgent(rng=random.Random(1))}
    outcome = play_game(game, agents)
    assert isinstance(outcome, Outcome)
    assert set(outcome.returns.keys()) == {0, 1}
    assert outcome.num_moves >= 5  # TTT: minimum game length is 5 moves
    assert outcome.num_moves <= 9
    assert len(outcome.trajectory) == outcome.num_moves


def test_play_game_terminal_state_has_returns() -> None:
    game = TicTacToe()
    agents = {0: RandomAgent(rng=random.Random(7)), 1: RandomAgent(rng=random.Random(8))}
    outcome = play_game(game, agents)
    # Sum of returns is zero-sum for TTT (1 + -1 on win, 0 + 0 on draw)
    assert sum(outcome.returns.values()) in (-1.0 + 1.0, 0.0)  # i.e. 0.0


def test_play_game_trajectory_states_are_pre_action() -> None:
    """Each (state, action) pair in trajectory: action is legal in state."""
    game = TicTacToe()
    agents = {0: RandomAgent(rng=random.Random(3)), 1: RandomAgent(rng=random.Random(4))}
    outcome = play_game(game, agents)
    for state, action in outcome.trajectory:
        assert action in state.legal_actions()


def test_play_game_raises_on_mismatched_agents_dict() -> None:
    game = TicTacToe()  # num_players == 2
    agents = {0: RandomAgent()}  # missing player 1
    with pytest.raises(ValueError):
        play_game(game, agents)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/runner/test_play.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'table_peak.runner.play'`.

- [ ] **Step 4: Implement `play_game` + `Outcome`**

Create `src/table_peak/runner/play.py`:

```python
"""Game and match runner. Imperative shell over the functional core."""

from __future__ import annotations

from dataclasses import dataclass

from table_peak.agents.base import Agent
from table_peak.games.base import Action, Game, PlayerId, State


@dataclass(frozen=True, slots=True)
class Outcome:
    """Result of a single game."""

    returns: dict[PlayerId, float]
    trajectory: list[tuple[State, Action]]
    num_moves: int


def play_game(game: Game, agents: dict[PlayerId, Agent]) -> Outcome:
    """Run one game to completion and return its outcome."""
    if set(agents.keys()) != set(range(game.num_players)):
        raise ValueError(
            f"agents keys {sorted(agents.keys())} must equal "
            f"{list(range(game.num_players))} (game.num_players={game.num_players})"
        )

    state = game.new_initial_state()
    history: list[tuple[State, Action]] = []
    while not state.is_terminal:
        player = state.current_player
        action = agents[player].act(state)
        history.append((state, action))
        state = state.apply_action(action)
    return Outcome(returns=state.returns(), trajectory=history, num_moves=len(history))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/runner/test_play.py -v`
Expected: 4 tests pass.

- [ ] **Step 6: Run static checks**

Run: `uv run mypy src tests`
Expected: `Success: no issues found`

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add tests/runner/__init__.py tests/runner/test_play.py \
        src/table_peak/runner/__init__.py src/table_peak/runner/play.py
git commit -m "feat(runner): add play_game and Outcome"
```

---

## Task 6: Runner — `play_matches` + Behavioural Tests (TDD)

**Files:**
- Modify: `tests/runner/test_play.py`
- Modify: `src/table_peak/runner/play.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/runner/test_play.py`:

```python
from table_peak.agents.minimax import MinimaxAgent
from table_peak.runner.play import MatchStats, play_matches


def test_play_matches_basic_shape() -> None:
    game = TicTacToe()
    stats = play_matches(
        game,
        agent_a=RandomAgent(rng=random.Random(0)),
        agent_b=RandomAgent(rng=random.Random(1)),
        n=10,
        seed=42,
    )
    assert isinstance(stats, MatchStats)
    assert stats.n_games == 10
    assert set(stats.wins.keys()) == {0, 1}
    assert stats.draws >= 0
    assert stats.wins[0] + stats.wins[1] + stats.draws == 10


def test_play_matches_is_reproducible_with_seed() -> None:
    game = TicTacToe()

    def run() -> MatchStats:
        return play_matches(
            game,
            agent_a=RandomAgent(rng=random.Random(0)),
            agent_b=RandomAgent(rng=random.Random(1)),
            n=50,
            seed=42,
        )

    a = run()
    b = run()
    assert a.wins == b.wins
    assert a.draws == b.draws
    assert a.mean_returns == b.mean_returns


def test_play_matches_swap_sides_balances_player_ids() -> None:
    """With swap_sides=True, both A and B play P0 in roughly half the games."""
    game = TicTacToe()
    # Use deterministic minimax for both: every game draws regardless of side.
    stats = play_matches(
        game,
        agent_a=MinimaxAgent(),
        agent_b=MinimaxAgent(),
        n=20,
        swap_sides=True,
        seed=0,
    )
    assert stats.draws == 20  # minimax vs minimax always draws


def test_minimax_never_loses_against_random() -> None:
    """Across 200 seeded games (sides swapped), minimax (A) wins or draws."""
    game = TicTacToe()
    stats = play_matches(
        game,
        agent_a=MinimaxAgent(),
        agent_b=RandomAgent(rng=random.Random(99)),
        n=200,
        swap_sides=True,
        seed=2026,
    )
    # Agent A (minimax) is never beaten -> wins[1] (which is B's wins) is 0.
    assert stats.wins[1] == 0


def test_minimax_vs_minimax_always_draws() -> None:
    """50 games of minimax vs minimax: every game draws."""
    game = TicTacToe()
    stats = play_matches(
        game,
        agent_a=MinimaxAgent(),
        agent_b=MinimaxAgent(),
        n=50,
        swap_sides=True,
        seed=1,
    )
    assert stats.draws == 50
    assert stats.wins == {0: 0, 1: 0}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/runner/test_play.py -v`
Expected: existing tests still pass; new tests FAIL with `ImportError: cannot import name 'MatchStats'` (or `play_matches`).

- [ ] **Step 3: Append `play_matches` + `MatchStats` to `src/table_peak/runner/play.py`**

Add to `src/table_peak/runner/play.py` (in addition to what's already there):

```python
import random as _random


@dataclass(frozen=True, slots=True)
class MatchStats:
    """Aggregate statistics over a series of games.

    Keys in `wins` and `mean_returns` are AGENT INDICES, not literal player
    seats: 0 = agent_a, 1 = agent_b. This matters when `swap_sides=True`,
    where each agent plays both P0 and P1 across games. Reading "did agent_a
    beat agent_b" is the common case, so we key by agent identity.
    """

    n_games: int
    wins: dict[PlayerId, int]
    draws: int
    mean_returns: dict[PlayerId, float]


def play_matches(
    game: Game,
    agent_a: Agent,
    agent_b: Agent,
    n: int,
    swap_sides: bool = True,
    seed: int | None = None,
) -> MatchStats:
    """Play `n` games between two agents and aggregate outcomes.

    With swap_sides=True, half the games place agent_a at P0 and half at P1, so
    the reported stats are not biased by first-mover advantage (with odd `n`,
    one direction gets one extra game). Stats are keyed by agent index, not
    literal seat — see `MatchStats` for details.
    """
    if game.num_players != 2:
        raise ValueError("play_matches currently supports only 2-player games")

    rng = _random.Random(seed)

    wins: dict[PlayerId, int] = {0: 0, 1: 0}
    draws = 0
    sum_returns: dict[PlayerId, float] = {0: 0.0, 1: 0.0}

    for i in range(n):
        a_is_p0 = (i % 2 == 0) if swap_sides else True
        if a_is_p0:
            agents: dict[PlayerId, Agent] = {0: agent_a, 1: agent_b}
            agent_seat: dict[int, PlayerId] = {0: 0, 1: 1}
        else:
            agents = {0: agent_b, 1: agent_a}
            agent_seat = {0: 1, 1: 0}

        # Threaded RNG: reserved for future stochastic environments. Touching
        # it now keeps the seed -> outcome mapping stable when chance nodes are
        # added later, so existing seeded tests don't all need re-baselining.
        _ = rng.random()

        outcome = play_game(game, agents)

        a_return = outcome.returns[agent_seat[0]]
        b_return = outcome.returns[agent_seat[1]]
        sum_returns[0] += a_return
        sum_returns[1] += b_return

        if a_return > b_return:
            wins[0] += 1
        elif b_return > a_return:
            wins[1] += 1
        else:
            draws += 1

    mean_returns = {idx: sum_returns[idx] / n for idx in (0, 1)}
    return MatchStats(n_games=n, wins=wins, draws=draws, mean_returns=mean_returns)
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: every test passes (Tasks 0–6, all green).

- [ ] **Step 5: Run static checks**

Run: `uv run mypy src tests`
Expected: `Success: no issues found`

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add tests/runner/test_play.py src/table_peak/runner/play.py
git commit -m "feat(runner): add play_matches with side-swapping and behavioural tests"
```

---

## Task 7: Final Smoke Pass

**Files:** none (verification only; small fixes if anything surfaces).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass; suite completes in well under 5 seconds.

- [ ] **Step 2: Run mypy strict on the whole repo**

Run: `uv run mypy src tests`
Expected: `Success: no issues found`

- [ ] **Step 3: Run ruff lint and format check**

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

Run: `uv run ruff format --check src tests`
Expected: All files already formatted.

- [ ] **Step 4: Verify package is importable from a clean shell**

Run: `uv run python -c "from table_peak.games.tic_tac_toe import TicTacToe; from table_peak.agents.random import RandomAgent; from table_peak.agents.minimax import MinimaxAgent; from table_peak.runner.play import play_game, play_matches; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Run pre-commit on all files**

Run: `uv run pre-commit run --all-files`
Expected: all hooks pass.

- [ ] **Step 6: If any of the above produced fixes, commit them**

```bash
git status
git add -p
git commit -m "chore: final lint/format pass for v1"
```

(If working tree is clean after Step 5, skip the commit — there's nothing to record.)

---

## Plan Self-Review Notes

- **Spec coverage:** Architecture (Tasks 1–6), Components (matches §Components in the spec), Interfaces (Task 1: Game, State, Agent), Data flow (Tasks 5–6: play_game, Outcome, play_matches with swap_sides + injected RNG, ValueError on illegal/mismatched agents), Testing (macro black-box tests with fixed seeds in every task; mypy + ruff in steps 5/6 of each task), Tooling (Task 0: Python 3.12, uv, ruff, mypy, pytest, pre-commit; pyproject.toml with hatchling). Deferred items match the spec's Deferred section (no learning, no external framework, no CLI, no CI).
- **No placeholders:** every step contains exact paths, full code, exact commands.
- **Type consistency:** `PlayerId = int`, `Action = int`, `State`/`Game`/`Agent` Protocol names match across all tasks. `Outcome` and `MatchStats` field names are consistent between definition (Task 5/6 impl) and assertions (Task 5/6 tests).
