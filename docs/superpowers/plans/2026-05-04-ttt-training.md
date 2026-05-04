# TTT Training (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-play REINFORCE-with-baseline training loop that produces a `NeuralAgent` for tic-tac-toe, with three Port-shaped infrastructure seams (`OpponentSampler`, `CheckpointStore`, `MetricsLogger`) ready for the eventual partial-info game work.

**Architecture:** New `src/table_peak/training/` package (one file per concern) and `src/table_peak/agents/neural.py` (inference-only `NeuralAgent`). Functional core stays pure; `training/` is the imperative shell. One-way dependency: `training/ → agents/` only.

**Tech Stack:** Python 3.12, PyTorch (CPU), pytest, mypy strict, ruff. Frozen dataclasses for `HParams`. CSV for metrics. Plain file I/O for checkpoints.

**Reference spec:** `docs/superpowers/specs/2026-05-04-ttt-training-design.md` (commit `a97e9f6`).

---

## Conventions (read once)

The repo follows these conventions — match them in every file you create:

- `from __future__ import annotations` at the top of every module.
- One-line module docstrings (look at `src/table_peak/games/base.py` for the style).
- Frozen dataclasses where data is immutable: `@dataclass(frozen=True, slots=True)`.
- Protocols use `@runtime_checkable`; type aliases reuse `PlayerId = int`, `Action = int` from `table_peak.games.base`.
- ruff line-length 100; selected rules `E, F, W, I, B, UP, SIM, RUF`.
- `mypy --strict` must pass.
- Tests mirror `src/table_peak/` under `tests/`.
- All commits pass pre-commit (ruff + mypy via the project's `.pre-commit-config.yaml`).

## File structure

**Created:**

```
src/table_peak/agents/neural.py
src/table_peak/training/__init__.py
src/table_peak/training/encoder.py
src/table_peak/training/policy_net.py
src/table_peak/training/buffer.py
src/table_peak/training/self_play.py
src/table_peak/training/reinforce.py
src/table_peak/training/checkpoint.py
src/table_peak/training/metrics.py
src/table_peak/training/eval.py
src/table_peak/training/loop.py

tests/agents/test_neural.py
tests/training/__init__.py
tests/training/test_encoder.py
tests/training/test_policy_net.py
tests/training/test_buffer.py
tests/training/test_self_play.py
tests/training/test_reinforce.py
tests/training/test_checkpoint.py
tests/training/test_metrics.py
tests/training/test_eval.py
tests/training/test_loop.py
```

**Modified:**

- `pyproject.toml` — add `torch` dependency; register `slow` pytest marker.

---

## Task 0: Add torch dependency, create package skeleton, register slow marker

**Files:**
- Modify: `pyproject.toml`
- Create: `src/table_peak/training/__init__.py` (empty)
- Create: `tests/training/__init__.py` (empty)

- [ ] **Step 1: Add torch via uv**

Run: `uv add "torch>=2.5"`

Expected: `pyproject.toml` updated; `uv.lock` updated; torch installed in `.venv`. CPU-only wheel on macOS ARM is fine.

- [ ] **Step 2: Register the `slow` pytest marker**

Modify `pyproject.toml`. Replace:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra --tb=short"
```

with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra --tb=short"
markers = [
    "slow: end-to-end smoke training; takes minutes",
]
```

- [ ] **Step 3: Create empty package files**

```bash
touch src/table_peak/training/__init__.py
touch tests/training/__init__.py
```

- [ ] **Step 4: Verify torch imports and tests still pass**

Run: `uv run python -c "import torch; print(torch.__version__)"`
Expected: torch version printed, no error.

Run: `uv run pytest -q`
Expected: all existing tests pass; no new tests yet.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/table_peak/training/__init__.py tests/training/__init__.py
git commit -m "chore(training): add torch dep, training package skeleton, slow marker"
```

---

## Task 1: Encoder Port + TTTEncoder

The encoder turns a `State` into the network's input tensor in **current-player perspective**: channel 0 is the player-to-move's pieces, channel 1 is the opponent's, channel 2 is empty. This lets a single net handle both seats.

**Files:**
- Create: `src/table_peak/training/encoder.py`
- Test: `tests/training/test_encoder.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_encoder.py`:

```python
"""Encoder: State -> tensors in current-player perspective."""

from __future__ import annotations

import torch

from table_peak.games.tic_tac_toe import TicTacToe, TicTacToeState
from table_peak.training.encoder import TTTEncoder


def test_encode_empty_board_p0_to_move() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state()  # P0 to move, empty board

    tensor = enc.encode(state)

    assert tensor.shape == (3, 3, 3)
    assert tensor.dtype == torch.float32
    # ch0 = mine (P0): all zeros. ch1 = opp (P1): all zeros. ch2 = empty: all ones.
    assert torch.equal(tensor[0], torch.zeros(3, 3))
    assert torch.equal(tensor[1], torch.zeros(3, 3))
    assert torch.equal(tensor[2], torch.ones(3, 3))


def test_encode_after_p0_plays_center_now_p1_to_move() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state().apply_action(4)  # P0 plays center; now P1 to move

    tensor = enc.encode(state)

    # current_player is now P1.
    # ch0 = mine (P1's pieces): all zeros (P1 hasn't played).
    # ch1 = opp (P0's pieces): 1 at center, 0 elsewhere.
    # ch2 = empty: 0 at center, 1 elsewhere.
    expected_opp = torch.zeros(3, 3)
    expected_opp[1, 1] = 1.0
    expected_empty = torch.ones(3, 3)
    expected_empty[1, 1] = 0.0
    assert torch.equal(tensor[0], torch.zeros(3, 3))
    assert torch.equal(tensor[1], expected_opp)
    assert torch.equal(tensor[2], expected_empty)


def test_encode_legal_mask_matches_legal_actions() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state().apply_action(4).apply_action(0)
    # board: P1 at 0, P0 at 4. Legal: 1, 2, 3, 5, 6, 7, 8.

    mask = enc.encode_legal_mask(state)

    assert mask.shape == (9,)
    assert mask.dtype == torch.bool
    expected = torch.tensor([False, True, True, True, False, True, True, True, True])
    assert torch.equal(mask, expected)


def test_encode_flat_returns_27d_view() -> None:
    enc = TTTEncoder()
    state = TicTacToe().new_initial_state()

    flat = enc.encode_flat(state)

    assert flat.shape == (27,)
    assert flat.dtype == torch.float32
    # First 9 (mine) zeros, next 9 (opp) zeros, last 9 (empty) ones.
    assert torch.equal(flat[:9], torch.zeros(9))
    assert torch.equal(flat[9:18], torch.zeros(9))
    assert torch.equal(flat[18:], torch.ones(9))


def test_encoder_protocol_runtime_check() -> None:
    from table_peak.training.encoder import Encoder

    assert isinstance(TTTEncoder(), Encoder)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_encoder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'table_peak.training.encoder'`.

- [ ] **Step 3: Implement the encoder**

Create `src/table_peak/training/encoder.py`:

```python
"""Encoder Port + TTT encoder. Pure: State -> tensors in current-player perspective."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import torch

from table_peak.games.base import State
from table_peak.games.tic_tac_toe import TicTacToeState


@runtime_checkable
class Encoder(Protocol):
    """Port: turn a State into NN inputs from the current player's perspective."""

    def encode(self, state: State) -> torch.Tensor: ...

    def encode_flat(self, state: State) -> torch.Tensor: ...

    def encode_legal_mask(self, state: State) -> torch.Tensor: ...


class TTTEncoder:
    """3x3x3 channel encoding for TicTacToe.

    Channels: [mine, opp, empty] from state.current_player's perspective.
    """

    def encode(self, state: State) -> torch.Tensor:
        if not isinstance(state, TicTacToeState):
            raise TypeError(f"TTTEncoder expects TicTacToeState, got {type(state).__name__}")
        me = state.current_player
        opp = 1 - me
        mine = torch.tensor(
            [1.0 if c == me else 0.0 for c in state.board], dtype=torch.float32
        ).reshape(3, 3)
        opp_t = torch.tensor(
            [1.0 if c == opp else 0.0 for c in state.board], dtype=torch.float32
        ).reshape(3, 3)
        empty = torch.tensor(
            [1.0 if c == -1 else 0.0 for c in state.board], dtype=torch.float32
        ).reshape(3, 3)
        return torch.stack([mine, opp_t, empty], dim=0)

    def encode_flat(self, state: State) -> torch.Tensor:
        return self.encode(state).reshape(-1)

    def encode_legal_mask(self, state: State) -> torch.Tensor:
        legal = set(state.legal_actions())
        return torch.tensor([i in legal for i in range(9)], dtype=torch.bool)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_encoder.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/encoder.py tests/training/test_encoder.py
git commit -m "feat(training): add Encoder Port and TTTEncoder"
```

---

## Task 2: PolicyValueNet

Tiny MLP: `27 → 64 → 64`, then split into a 9-logit policy head and a `tanh`-bounded scalar value head.

**Files:**
- Create: `src/table_peak/training/policy_net.py`
- Test: `tests/training/test_policy_net.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_policy_net.py`:

```python
"""PolicyValueNet: tiny MLP with policy + value heads."""

from __future__ import annotations

import torch

from table_peak.training.policy_net import PolicyValueNet


def test_forward_shapes_for_batch() -> None:
    net = PolicyValueNet()
    batch = torch.zeros((4, 27))

    logits, value = net(batch)

    assert logits.shape == (4, 9)
    assert value.shape == (4, 1)


def test_value_is_bounded_in_minus_one_to_one() -> None:
    net = PolicyValueNet()
    # Use random inputs to span the input space.
    torch.manual_seed(0)
    batch = torch.randn((32, 27))

    _, value = net(batch)

    assert torch.all(value >= -1.0)
    assert torch.all(value <= 1.0)


def test_forward_is_deterministic_given_seed() -> None:
    torch.manual_seed(123)
    net1 = PolicyValueNet()
    torch.manual_seed(123)
    net2 = PolicyValueNet()
    batch = torch.zeros((1, 27))

    out1 = net1(batch)
    out2 = net2(batch)

    assert torch.equal(out1[0], out2[0])
    assert torch.equal(out1[1], out2[1])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_policy_net.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the network**

Create `src/table_peak/training/policy_net.py`:

```python
"""PolicyValueNet: small MLP with policy and value heads. Pure forward pass."""

from __future__ import annotations

import torch
from torch import nn


class PolicyValueNet(nn.Module):
    """27 -> 64 -> 64, split into 9-logit policy head and tanh-bounded value head."""

    def __init__(self, hidden: int = 64) -> None:
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(27, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
        )
        self.policy_head = nn.Linear(hidden, 9)
        self.value_head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.trunk(x)
        logits = self.policy_head(h)
        value = torch.tanh(self.value_head(h))
        return logits, value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_policy_net.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/policy_net.py tests/training/test_policy_net.py
git commit -m "feat(training): add PolicyValueNet (MLP, two heads)"
```

---

## Task 3: NeuralAgent (inference-only)

Implements the existing `Agent` Protocol. Owns a `PolicyValueNet` and an `Encoder`. `act()` masks illegal actions, then either argmax (greedy, `temperature=0`) or samples from the softmax (`temperature>0`).

**Files:**
- Create: `src/table_peak/agents/neural.py`
- Test: `tests/agents/test_neural.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agents/test_neural.py`:

```python
"""NeuralAgent: inference-only Agent backed by a PolicyValueNet + Encoder."""

from __future__ import annotations

import random

import torch

from table_peak.agents.base import Agent
from table_peak.agents.neural import NeuralAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import play_game
from table_peak.training.encoder import TTTEncoder
from table_peak.training.policy_net import PolicyValueNet


def _make_agent(*, temperature: float = 0.0, seed: int = 0) -> NeuralAgent:
    torch.manual_seed(seed)
    net = PolicyValueNet()
    return NeuralAgent(
        net=net, encoder=TTTEncoder(), temperature=temperature, rng=random.Random(seed)
    )


def test_neural_agent_satisfies_agent_protocol() -> None:
    assert isinstance(_make_agent(), Agent)


def test_act_returns_legal_action_on_initial_state() -> None:
    agent = _make_agent()
    state = TicTacToe().new_initial_state()

    action = agent.act(state)

    assert action in state.legal_actions()


def test_greedy_act_is_deterministic_for_same_state() -> None:
    agent = _make_agent(temperature=0.0)
    state = TicTacToe().new_initial_state()

    actions = {agent.act(state) for _ in range(5)}

    assert len(actions) == 1


def test_act_respects_legal_mask_late_game() -> None:
    agent = _make_agent()
    state = TicTacToe().new_initial_state()
    # Fill cells 0..6, both players alternate.
    for i in range(7):
        state = state.apply_action(i)
    # Legal actions remaining: 7, 8.
    assert state.legal_actions() == (7, 8)

    action = agent.act(state)

    assert action in (7, 8)


def test_neural_agent_plays_complete_game_against_random() -> None:
    agent = _make_agent()
    rng = random.Random(0)
    from table_peak.agents.random import RandomAgent

    outcome = play_game(TicTacToe(), {0: agent, 1: RandomAgent(rng)})

    assert outcome.num_moves >= 5
    assert outcome.num_moves <= 9


def test_sampling_mode_can_produce_multiple_actions() -> None:
    # With temperature=1.0 and 100 samples on the empty board, expect at least
    # two distinct chosen actions (extremely unlikely to be all the same).
    agent = _make_agent(temperature=1.0, seed=42)
    state = TicTacToe().new_initial_state()

    actions = {agent.act(state) for _ in range(100)}

    assert len(actions) >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/agents/test_neural.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement NeuralAgent**

Create `src/table_peak/agents/neural.py`:

```python
"""NeuralAgent: inference-only policy backed by a PolicyValueNet + Encoder."""

from __future__ import annotations

import random

import torch

from table_peak.games.base import Action, State
from table_peak.training.encoder import Encoder
from table_peak.training.policy_net import PolicyValueNet


class NeuralAgent:
    """Wraps a PolicyValueNet + Encoder. Implements the Agent Protocol.

    temperature == 0 -> greedy argmax over masked logits.
    temperature  > 0 -> sample from softmax(logits / T) over legal actions.
    """

    def __init__(
        self,
        net: PolicyValueNet,
        encoder: Encoder,
        *,
        temperature: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self._net = net
        self._encoder = encoder
        self._temperature = float(temperature)
        self._rng = rng if rng is not None else random.Random()

    def act(self, state: State) -> Action:
        self._net.eval()
        with torch.no_grad():
            x = self._encoder.encode_flat(state).unsqueeze(0)
            logits, _ = self._net(x)
            mask = self._encoder.encode_legal_mask(state).unsqueeze(0)
            masked = logits.masked_fill(~mask, float("-inf"))

        if self._temperature == 0.0:
            return int(masked.argmax(dim=-1).item())

        probs = torch.softmax(masked / self._temperature, dim=-1).squeeze(0).tolist()
        # rng.choices with weights matches torch.multinomial draws but stays in
        # Python's RNG so reproducibility is governed by the injected rng.
        return int(self._rng.choices(range(9), weights=probs, k=1)[0])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agents/test_neural.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/agents/neural.py tests/agents/test_neural.py
git commit -m "feat(agents): add NeuralAgent (inference-only, policy+value net)"
```

---

## Task 4: TrajectoryBuffer + Sample/Episode types

On-policy buffer. Constructed fresh per update; no clear semantics needed.

**Files:**
- Create: `src/table_peak/training/buffer.py`
- Test: `tests/training/test_buffer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_buffer.py`:

```python
"""TrajectoryBuffer: on-policy collection, batched on demand."""

from __future__ import annotations

import torch

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.buffer import Episode, Sample, TrajectoryBuffer
from table_peak.training.encoder import TTTEncoder


def _trivial_episode() -> Episode:
    state = TicTacToe().new_initial_state()
    s1 = state
    s2 = s1.apply_action(0)
    s3 = s2.apply_action(1)
    return [
        Sample(state=s1, action=0, ret=1.0),
        Sample(state=s2, action=1, ret=-1.0),
        Sample(state=s3, action=2, ret=1.0),
    ]


def test_empty_buffer_reports_zero_size() -> None:
    buf = TrajectoryBuffer()
    assert len(buf) == 0


def test_add_episode_increases_size_by_sample_count() -> None:
    buf = TrajectoryBuffer()
    buf.add(_trivial_episode())
    buf.add(_trivial_episode())
    assert len(buf) == 6


def test_as_batch_returns_tensors_of_correct_shape() -> None:
    buf = TrajectoryBuffer()
    buf.add(_trivial_episode())  # 3 samples
    buf.add(_trivial_episode())  # 3 more

    states, actions, returns, masks = buf.as_batch(TTTEncoder())

    assert states.shape == (6, 27)
    assert actions.shape == (6,)
    assert returns.shape == (6,)
    assert masks.shape == (6, 9)
    assert states.dtype == torch.float32
    assert actions.dtype == torch.long
    assert returns.dtype == torch.float32
    assert masks.dtype == torch.bool


def test_as_batch_preserves_action_and_return_order() -> None:
    buf = TrajectoryBuffer()
    ep = _trivial_episode()
    buf.add(ep)

    _, actions, returns, _ = buf.as_batch(TTTEncoder())

    assert actions.tolist() == [s.action for s in ep]
    assert returns.tolist() == [s.ret for s in ep]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_buffer.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement buffer + types**

Create `src/table_peak/training/buffer.py`:

```python
"""On-policy trajectory buffer + Sample/Episode types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import torch

from table_peak.games.base import Action, State
from table_peak.training.encoder import Encoder


@dataclass(frozen=True, slots=True)
class Sample:
    """One (state, action, return) triple from a single player's perspective."""

    state: State
    action: Action
    ret: float


Episode: TypeAlias = list[Sample]


class TrajectoryBuffer:
    """Collects per-step samples from self-play episodes; batches on demand."""

    def __init__(self) -> None:
        self._samples: list[Sample] = []

    def __len__(self) -> int:
        return len(self._samples)

    def add(self, episode: Episode) -> None:
        self._samples.extend(episode)

    def as_batch(
        self, encoder: Encoder
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        states = torch.stack([encoder.encode_flat(s.state) for s in self._samples])
        actions = torch.tensor([s.action for s in self._samples], dtype=torch.long)
        returns = torch.tensor([s.ret for s in self._samples], dtype=torch.float32)
        masks = torch.stack([encoder.encode_legal_mask(s.state) for s in self._samples])
        return states, actions, returns, masks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_buffer.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/buffer.py tests/training/test_buffer.py
git commit -m "feat(training): add TrajectoryBuffer + Sample/Episode types"
```

---

## Task 5: OpponentSampler Port + SelfOpponentSampler + generate_episode

`generate_episode` is the training-side episode generator. It captures per-player samples (with terminal returns assigned to all of that player's steps) — `runner.play_game` only reports an aggregate `Outcome`, which is why we need a separate generator here.

**Files:**
- Create: `src/table_peak/training/self_play.py`
- Test: `tests/training/test_self_play.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_self_play.py`:

```python
"""Self-play episode generation + OpponentSampler Port."""

from __future__ import annotations

import random

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.self_play import (
    OpponentSampler,
    SelfOpponentSampler,
    generate_episode,
)


def test_self_opponent_sampler_returns_configured_agent() -> None:
    agent = RandomAgent(random.Random(0))
    sampler = SelfOpponentSampler(agent)

    assert sampler.sample() is agent


def test_self_opponent_sampler_satisfies_protocol() -> None:
    sampler = SelfOpponentSampler(RandomAgent(random.Random(0)))
    assert isinstance(sampler, OpponentSampler)


def test_generate_episode_terminates_with_legal_play() -> None:
    a0 = RandomAgent(random.Random(1))
    a1 = RandomAgent(random.Random(2))

    episode = generate_episode(TicTacToe(), agent_p0=a0, agent_p1=a1)

    assert 5 <= len(episode) <= 9
    for sample in episode:
        assert sample.action in sample.state.legal_actions()


def test_generate_episode_returns_zero_sum_for_ttt() -> None:
    a0 = RandomAgent(random.Random(1))
    a1 = RandomAgent(random.Random(2))

    episode = generate_episode(TicTacToe(), agent_p0=a0, agent_p1=a1)

    # In TTT the per-step return assigned to a sample is the player's terminal
    # return. Across the whole episode, P0's and P1's returns sum to 0.
    by_player_returns: dict[int, set[float]] = {0: set(), 1: set()}
    for sample in episode:
        by_player_returns[sample.state.current_player].add(sample.ret)
    # Each player has exactly one terminal return assigned to all their steps.
    assert all(len(v) == 1 for v in by_player_returns.values())
    p0_ret = next(iter(by_player_returns[0]))
    p1_ret = next(iter(by_player_returns[1]))
    assert p0_ret + p1_ret == 0.0


def test_generate_episode_attributes_returns_per_player_perspective() -> None:
    """Force a P0 win: P0 always picks first legal slot; P1 also picks first
    legal — P0 plays 0, 1, 2 if uncontested ... but P1 will block.
    Use scripted agents instead.
    """
    from table_peak.games.base import Action, State

    class ScriptedAgent:
        def __init__(self, moves: list[Action]) -> None:
            self._moves = list(moves)

        def act(self, state: State) -> Action:
            return self._moves.pop(0)

    # P0: 0, 1, 2  (top row). P1: 3, 4 (interleaved).
    # Sequence: P0 -> 0; P1 -> 3; P0 -> 1; P1 -> 4; P0 -> 2 -> WIN
    p0 = ScriptedAgent([0, 1, 2])
    p1 = ScriptedAgent([3, 4])

    episode = generate_episode(TicTacToe(), agent_p0=p0, agent_p1=p1)

    p0_returns = {s.ret for s in episode if s.state.current_player == 0}
    p1_returns = {s.ret for s in episode if s.state.current_player == 1}
    assert p0_returns == {1.0}
    assert p1_returns == {-1.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_self_play.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement self-play module**

Create `src/table_peak/training/self_play.py`:

```python
"""Self-play episode generation and opponent-sampling Port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from table_peak.agents.base import Agent
from table_peak.games.base import Action, Game, State
from table_peak.training.buffer import Episode, Sample


@runtime_checkable
class OpponentSampler(Protocol):
    """Port: provides the opponent agent for a given training game."""

    def sample(self) -> Agent: ...


class SelfOpponentSampler:
    """Default sampler: always returns the same (currently-training) agent."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def sample(self) -> Agent:
        return self._agent


def generate_episode(game: Game, agent_p0: Agent, agent_p1: Agent) -> Episode:
    """Play one full game; return per-player samples with terminal returns.

    Each step's `ret` is the terminal return for the player who acted at that
    step. This is the form REINFORCE consumes (Monte Carlo return, no
    discount, no bootstrap).
    """
    state = game.new_initial_state()
    pending_p0: list[tuple[State, Action]] = []
    pending_p1: list[tuple[State, Action]] = []

    while not state.is_terminal:
        player = state.current_player
        actor = agent_p0 if player == 0 else agent_p1
        action = actor.act(state)
        if player == 0:
            pending_p0.append((state, action))
        else:
            pending_p1.append((state, action))
        state = state.apply_action(action)

    returns = state.returns()
    episode: Episode = []
    for s, a in pending_p0:
        episode.append(Sample(state=s, action=a, ret=returns[0]))
    for s, a in pending_p1:
        episode.append(Sample(state=s, action=a, ret=returns[1]))
    return episode
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_self_play.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/self_play.py tests/training/test_self_play.py
git commit -m "feat(training): add OpponentSampler port and generate_episode"
```

---

## Task 6: REINFORCE update_step (loss + backward)

Single update step. Loss = `policy + value_coef * value − entropy_coef * entropy`. The advantage is the Monte Carlo return minus the (detached) value baseline; the policy gradient does not propagate into the value head.

**Files:**
- Create: `src/table_peak/training/reinforce.py`
- Test: `tests/training/test_reinforce.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_reinforce.py`:

```python
"""REINFORCE-with-baseline update step."""

from __future__ import annotations

import torch

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.buffer import Sample, TrajectoryBuffer
from table_peak.training.encoder import TTTEncoder
from table_peak.training.policy_net import PolicyValueNet
from table_peak.training.reinforce import update_step


def _toy_buffer() -> TrajectoryBuffer:
    """Cook up a small batch where the optimal action is always 'cell 0' with
    return +1.0 for the actor. Repeated training on this batch should reduce
    loss monotonically over a few steps."""
    state = TicTacToe().new_initial_state()
    buf = TrajectoryBuffer()
    buf.add(
        [
            Sample(state=state, action=0, ret=1.0),
            Sample(state=state, action=0, ret=1.0),
            Sample(state=state, action=0, ret=1.0),
            Sample(state=state, action=0, ret=1.0),
        ]
    )
    return buf


def test_update_step_returns_required_metric_keys() -> None:
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    buf = _toy_buffer()

    metrics = update_step(
        net, opt, buf, encoder=TTTEncoder(), value_coef=0.5, entropy_coef=0.01
    )

    for key in ("policy_loss", "value_loss", "entropy", "mean_return"):
        assert key in metrics


def test_update_step_produces_no_nan() -> None:
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    buf = _toy_buffer()

    metrics = update_step(
        net, opt, buf, encoder=TTTEncoder(), value_coef=0.5, entropy_coef=0.01
    )

    for v in metrics.values():
        assert not torch.isnan(torch.tensor(v))
        assert not torch.isinf(torch.tensor(v))


def test_repeated_updates_decrease_policy_loss_on_fixed_batch() -> None:
    """Sanity: training works. With a constant batch where action 0 is the
    only one ever taken with return +1, the policy must move probability mass
    onto action 0, which reduces -log p(a|s) and thus policy_loss."""
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-2)
    buf = _toy_buffer()
    enc = TTTEncoder()

    losses: list[float] = []
    for _ in range(20):
        metrics = update_step(net, opt, buf, encoder=enc, value_coef=0.5, entropy_coef=0.0)
        losses.append(metrics["policy_loss"])

    # Strict monotone-down isn't required; first should be larger than last.
    assert losses[0] > losses[-1]
    # And the last should be substantially smaller, e.g. half-or-less.
    assert losses[-1] <= losses[0] * 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_reinforce.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement update_step**

Create `src/table_peak/training/reinforce.py`:

```python
"""REINFORCE-with-baseline update step."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from table_peak.training.buffer import TrajectoryBuffer
from table_peak.training.encoder import Encoder


def update_step(
    net: nn.Module,
    optimizer: torch.optim.Optimizer,
    buffer: TrajectoryBuffer,
    *,
    encoder: Encoder,
    value_coef: float,
    entropy_coef: float,
) -> dict[str, float]:
    """One REINFORCE-with-baseline gradient step. Returns scalar metrics."""
    states, actions, returns, masks = buffer.as_batch(encoder)
    net.train()

    logits, values = net(states)
    masked_logits = logits.masked_fill(~masks, float("-inf"))
    log_probs = F.log_softmax(masked_logits, dim=-1)
    chosen_log_probs = log_probs.gather(-1, actions.unsqueeze(-1)).squeeze(-1)

    values_flat = values.squeeze(-1)
    advantages = returns - values_flat.detach()

    policy_loss = -(chosen_log_probs * advantages).mean()
    value_loss = F.mse_loss(values_flat, returns)
    # Entropy: -sum p log p, computed safely on the masked distribution.
    probs = log_probs.exp()
    entropy = -(probs * log_probs.clamp_min(-1e9)).sum(dim=-1).mean()

    loss = policy_loss + value_coef * value_loss - entropy_coef * entropy

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if torch.isnan(loss) or torch.isinf(loss):
        raise RuntimeError(f"Loss is non-finite: {loss.item()}")

    return {
        "policy_loss": float(policy_loss.item()),
        "value_loss": float(value_loss.item()),
        "entropy": float(entropy.item()),
        "mean_return": float(returns.mean().item()),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_reinforce.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/reinforce.py tests/training/test_reinforce.py
git commit -m "feat(training): add REINFORCE-with-baseline update_step"
```

---

## Task 7: CheckpointStore Port + FileCheckpointStore

**Files:**
- Create: `src/table_peak/training/checkpoint.py`
- Test: `tests/training/test_checkpoint.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_checkpoint.py`:

```python
"""CheckpointStore: save and load training state by generation."""

from __future__ import annotations

from pathlib import Path

import torch

from table_peak.training.checkpoint import CheckpointStore, FileCheckpointStore
from table_peak.training.policy_net import PolicyValueNet


def test_file_checkpoint_store_satisfies_protocol(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    assert isinstance(store, CheckpointStore)


def test_save_then_load_roundtrips_net_and_optimizer_state(tmp_path: Path) -> None:
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    # Take a synthetic step so the optimizer has nontrivial state.
    x = torch.zeros((1, 27))
    logits, _ = net(x)
    logits.sum().backward()
    opt.step()

    store = FileCheckpointStore(tmp_path)
    store.save(gen=42, net=net, optimizer=opt, step=100)

    fresh_net = PolicyValueNet()
    fresh_opt = torch.optim.Adam(fresh_net.parameters(), lr=1e-3)
    step = store.load(gen=42, net=fresh_net, optimizer=fresh_opt)

    assert step == 100
    for p_orig, p_loaded in zip(net.parameters(), fresh_net.parameters(), strict=True):
        assert torch.equal(p_orig, p_loaded)


def test_list_generations_returns_sorted_unique_ints(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for gen in (5, 1, 10, 1):  # duplicate 1 => overwrite, not a duplicate listing
        store.save(gen=gen, net=net, optimizer=opt, step=0)

    assert store.list_generations() == [1, 5, 10]


def test_save_creates_missing_directory(tmp_path: Path) -> None:
    nested = tmp_path / "deeper" / "still_deeper"
    store = FileCheckpointStore(nested)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)

    store.save(gen=0, net=net, optimizer=opt, step=0)

    assert (nested / "gen_0000.pt").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_checkpoint.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement checkpoint module**

Create `src/table_peak/training/checkpoint.py`:

```python
"""Checkpoint Port + file-backed adapter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import torch
from torch import nn


@runtime_checkable
class CheckpointStore(Protocol):
    """Port: persist and restore training state keyed by generation."""

    def save(
        self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer, step: int
    ) -> None: ...

    def load(self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer) -> int:
        """Loads state into the provided net and optimizer in place; returns step."""
        ...

    def list_generations(self) -> list[int]: ...


class FileCheckpointStore:
    """Writes `gen_NNNN.pt` files under a root directory."""

    _PATTERN = re.compile(r"gen_(\d{4,})\.pt$")

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _path(self, gen: int) -> Path:
        return self._root / f"gen_{gen:04d}.pt"

    def save(
        self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer, step: int
    ) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "net": net.state_dict(),
                "optimizer": optimizer.state_dict(),
                "step": step,
            },
            self._path(gen),
        )

    def load(self, gen: int, net: nn.Module, optimizer: torch.optim.Optimizer) -> int:
        payload = torch.load(self._path(gen), weights_only=True)
        net.load_state_dict(payload["net"])
        optimizer.load_state_dict(payload["optimizer"])
        return int(payload["step"])

    def list_generations(self) -> list[int]:
        if not self._root.exists():
            return []
        gens: list[int] = []
        for p in self._root.iterdir():
            m = self._PATTERN.match(p.name)
            if m:
                gens.append(int(m.group(1)))
        return sorted(set(gens))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_checkpoint.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/checkpoint.py tests/training/test_checkpoint.py
git commit -m "feat(training): add CheckpointStore port + FileCheckpointStore"
```

---

## Task 8: MetricsLogger Port + CSVMetricsLogger

Schema is fixed at construction; subsequent `log()` calls validate keys. Keeps the CSV well-formed.

**Files:**
- Create: `src/table_peak/training/metrics.py`
- Test: `tests/training/test_metrics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_metrics.py`:

```python
"""MetricsLogger: append-only CSV logger."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from table_peak.training.metrics import CSVMetricsLogger, MetricsLogger


def test_csv_logger_satisfies_protocol(tmp_path: Path) -> None:
    logger = CSVMetricsLogger(tmp_path / "metrics.csv", fields=["loss"])
    assert isinstance(logger, MetricsLogger)
    logger.close()


def test_log_writes_header_and_rows(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    logger = CSVMetricsLogger(path, fields=["policy_loss", "value_loss"])

    logger.log(step=1, policy_loss=0.5, value_loss=0.2)
    logger.log(step=2, policy_loss=0.4, value_loss=0.15)
    logger.close()

    with open(path) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0] == {"step": "1", "policy_loss": "0.5", "value_loss": "0.2"}
    assert rows[1] == {"step": "2", "policy_loss": "0.4", "value_loss": "0.15"}


def test_log_with_unknown_field_raises(tmp_path: Path) -> None:
    logger = CSVMetricsLogger(tmp_path / "m.csv", fields=["loss"])

    with pytest.raises(ValueError, match="unknown field"):
        logger.log(step=1, loss=0.5, mystery=1.0)

    logger.close()


def test_log_missing_field_writes_empty_string(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    logger = CSVMetricsLogger(path, fields=["a", "b"])

    logger.log(step=1, a=1.0)  # 'b' missing
    logger.close()

    with open(path) as f:
        rows = list(csv.DictReader(f))

    assert rows == [{"step": "1", "a": "1.0", "b": ""}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement metrics module**

Create `src/table_peak/training/metrics.py`:

```python
"""MetricsLogger Port + CSV-backed adapter."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import IO, Protocol, runtime_checkable


@runtime_checkable
class MetricsLogger(Protocol):
    """Port: append a metrics row keyed by step."""

    def log(self, step: int, **fields: float) -> None: ...

    def close(self) -> None: ...


class CSVMetricsLogger:
    """Append metrics to a CSV file. Schema is fixed at construction."""

    def __init__(self, path: Path, fields: Iterable[str]) -> None:
        self._path = Path(path)
        self._fields = list(fields)
        self._all_columns = ["step", *self._fields]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file: IO[str] = open(self._path, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self._all_columns)
        self._writer.writeheader()
        self._file.flush()

    def log(self, step: int, **fields: float) -> None:
        unknown = set(fields) - set(self._fields)
        if unknown:
            raise ValueError(f"unknown field(s): {sorted(unknown)}")
        row: dict[str, str] = {"step": str(step)}
        for name in self._fields:
            row[name] = str(fields[name]) if name in fields else ""
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_metrics.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/metrics.py tests/training/test_metrics.py
git commit -m "feat(training): add MetricsLogger port + CSVMetricsLogger"
```

---

## Task 9: cross_table evaluation helper

Pairwise side-swapped evaluation across a list of named agents. Reuses `runner.play_matches`. The result is the rectangular matrix that PSRO will eventually consume as a meta-game payoff table.

**Files:**
- Create: `src/table_peak/training/eval.py`
- Test: `tests/training/test_eval.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_eval.py`:

```python
"""cross_table: pairwise side-swapped evaluation across named agents."""

from __future__ import annotations

import random

from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import MatchStats
from table_peak.training.eval import cross_table


def test_cross_table_contains_all_ordered_pairs() -> None:
    agents = [
        ("rand1", RandomAgent(random.Random(1))),
        ("rand2", RandomAgent(random.Random(2))),
        ("minimax", MinimaxAgent()),
    ]

    table = cross_table(agents, game=TicTacToe(), n_per_pair=20, seed=0)

    # Lower triangle only (i < j) — pair (a, b) is enough since play_matches
    # already swaps sides.
    expected_pairs = {("rand1", "rand2"), ("rand1", "minimax"), ("rand2", "minimax")}
    assert set(table.keys()) == expected_pairs
    for stats in table.values():
        assert isinstance(stats, MatchStats)
        assert stats.n_games == 20


def test_cross_table_minimax_never_loses_to_random() -> None:
    agents = [
        ("random", RandomAgent(random.Random(0))),
        ("minimax", MinimaxAgent()),
    ]

    table = cross_table(agents, game=TicTacToe(), n_per_pair=200, seed=0)

    stats = table[("random", "minimax")]
    # play_matches keys: 0 = first agent (random), 1 = second agent (minimax).
    assert stats.wins[0] == 0  # random never beats minimax
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_eval.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement eval module**

Create `src/table_peak/training/eval.py`:

```python
"""Pairwise cross-table evaluation across named agents."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from table_peak.agents.base import Agent
from table_peak.games.base import Game
from table_peak.runner.play import MatchStats, play_matches

EvalTable: TypeAlias = dict[tuple[str, str], MatchStats]


def cross_table(
    agents: Sequence[tuple[str, Agent]],
    *,
    game: Game,
    n_per_pair: int,
    seed: int,
) -> EvalTable:
    """For every i < j pair (a_i, a_j), call play_matches with side-swapping.

    Each entry's MatchStats keys are: 0 = a_i, 1 = a_j (per play_matches'
    agent-index convention).
    """
    table: EvalTable = {}
    for i in range(len(agents)):
        name_i, agent_i = agents[i]
        for j in range(i + 1, len(agents)):
            name_j, agent_j = agents[j]
            table[(name_i, name_j)] = play_matches(
                game=game,
                agent_a=agent_i,
                agent_b=agent_j,
                n=n_per_pair,
                swap_sides=True,
                seed=seed + i * 1000 + j,
            )
    return table
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_eval.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/training/eval.py tests/training/test_eval.py
git commit -m "feat(training): add cross_table evaluation helper"
```

---

## Task 10: HParams + train() orchestration + end-to-end smoke test

The spine. `train()` wires everything together; the smoke test asserts the v2 success criteria (≥95% non-loss vs Random; ≤5% loss vs Minimax with zero wins).

**Files:**
- Create: `src/table_peak/training/loop.py`
- Test: `tests/training/test_loop.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/training/test_loop.py`:

```python
"""train(): full self-play REINFORCE loop. The smoke test is the v2 spine."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
import torch

from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.neural import NeuralAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import play_matches
from table_peak.training.checkpoint import FileCheckpointStore
from table_peak.training.loop import HParams, train
from table_peak.training.metrics import CSVMetricsLogger


def test_hparams_defaults_are_set() -> None:
    hp = HParams()
    assert hp.games_per_update >= 1
    assert hp.total_updates >= 1
    assert hp.lr > 0


def test_train_runs_and_writes_checkpoints_and_metrics(tmp_path: Path) -> None:
    """Tiny budget — verifies orchestration wires everything correctly."""
    hp = HParams(
        games_per_update=4,
        total_updates=3,
        eval_every=2,
        eval_n_per_pair=4,  # keep this non-slow test quick
        checkpoint_every=2,
        seed=42,
    )
    ckpt = FileCheckpointStore(tmp_path / "ckpt")
    metrics = CSVMetricsLogger(
        tmp_path / "m.csv",
        fields=[
            "policy_loss",
            "value_loss",
            "entropy",
            "mean_return",
            "non_loss_vs_random",
            "loss_vs_minimax",
        ],
    )

    agent = train(
        game=TicTacToe(),
        hparams=hp,
        checkpoint_store=ckpt,
        metrics_logger=metrics,
    )

    assert isinstance(agent, NeuralAgent)
    # At least one mid-run checkpoint plus the final one.
    assert len(ckpt.list_generations()) >= 1
    assert (tmp_path / "m.csv").exists()


@pytest.mark.slow
def test_smoke_training_meets_v2_success_criteria(tmp_path: Path) -> None:
    """End-to-end smoke. Must complete in <5 min CPU and meet criteria 1+2.

    Criterion 1: trained agent achieves >=95% non-loss vs Random over 500 games.
    Criterion 2: trained agent has <=5% loss vs Minimax over 200 games AND zero wins.
    """
    hp = HParams()  # production defaults — tuned to fit the 5-min budget
    ckpt = FileCheckpointStore(tmp_path / "ckpt")
    metrics = CSVMetricsLogger(
        tmp_path / "m.csv",
        fields=[
            "policy_loss",
            "value_loss",
            "entropy",
            "mean_return",
            "non_loss_vs_random",
            "loss_vs_minimax",
        ],
    )

    trained = train(
        game=TicTacToe(),
        hparams=hp,
        checkpoint_store=ckpt,
        metrics_logger=metrics,
    )
    # train() returns a greedy NeuralAgent (temperature=0); use directly.

    # Criterion 1: >=95% non-loss vs Random.
    vs_random = play_matches(
        game=TicTacToe(),
        agent_a=trained,
        agent_b=RandomAgent(random.Random(0)),
        n=500,
        swap_sides=True,
        seed=0,
    )
    non_loss_rate = (vs_random.wins[0] + vs_random.draws) / vs_random.n_games
    assert non_loss_rate >= 0.95, f"non-loss vs Random was {non_loss_rate:.3f}"

    # Criterion 2: <=5% loss AND zero wins vs Minimax.
    vs_minimax = play_matches(
        game=TicTacToe(),
        agent_a=trained,
        agent_b=MinimaxAgent(),
        n=200,
        swap_sides=True,
        seed=0,
    )
    loss_rate = vs_minimax.wins[1] / vs_minimax.n_games
    win_count = vs_minimax.wins[0]
    assert win_count == 0, f"NeuralAgent beat Minimax {win_count} times — minimax bug"
    assert loss_rate <= 0.05, f"loss vs Minimax was {loss_rate:.3f}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_loop.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement HParams + train()**

Create `src/table_peak/training/loop.py`:

```python
"""HParams + top-level train() orchestration for REINFORCE self-play."""

from __future__ import annotations

import random
from dataclasses import dataclass

import torch

from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.neural import NeuralAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import Game
from table_peak.training.buffer import TrajectoryBuffer
from table_peak.training.checkpoint import CheckpointStore
from table_peak.training.encoder import TTTEncoder
from table_peak.training.eval import cross_table
from table_peak.training.metrics import MetricsLogger
from table_peak.training.policy_net import PolicyValueNet
from table_peak.training.reinforce import update_step
from table_peak.training.self_play import SelfOpponentSampler, generate_episode


@dataclass(frozen=True, slots=True)
class HParams:
    """Hyperparameters for v2 REINFORCE-with-baseline self-play training.

    Defaults are tuned for the <5-minute CPU smoke-test budget on TTT.
    """

    games_per_update: int = 32
    total_updates: int = 1000
    lr: float = 1e-3
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    train_temperature: float = 1.0
    eval_every: int = 200
    eval_n_per_pair: int = 100
    checkpoint_every: int = 250
    seed: int = 42


def train(
    *,
    game: Game,
    hparams: HParams,
    checkpoint_store: CheckpointStore,
    metrics_logger: MetricsLogger,
) -> NeuralAgent:
    """Self-play REINFORCE-with-baseline. Returns the final greedy NeuralAgent."""
    torch.manual_seed(hparams.seed)
    rng = random.Random(hparams.seed)

    encoder = TTTEncoder()
    net = PolicyValueNet()
    optimizer = torch.optim.Adam(net.parameters(), lr=hparams.lr)

    train_agent = NeuralAgent(
        net=net, encoder=encoder, temperature=hparams.train_temperature, rng=rng
    )
    sampler = SelfOpponentSampler(train_agent)

    eval_random_agent = RandomAgent(random.Random(hparams.seed + 1))
    eval_minimax_agent = MinimaxAgent()  # reused across evals; cache persists

    for update in range(1, hparams.total_updates + 1):
        buf = TrajectoryBuffer()
        for _ in range(hparams.games_per_update):
            opponent = sampler.sample()
            episode = generate_episode(game, agent_p0=train_agent, agent_p1=opponent)
            buf.add(episode)

        loss_metrics = update_step(
            net,
            optimizer,
            buf,
            encoder=encoder,
            value_coef=hparams.value_coef,
            entropy_coef=hparams.entropy_coef,
        )

        is_eval_step = update % hparams.eval_every == 0 or update == hparams.total_updates
        if is_eval_step:
            greedy_agent = NeuralAgent(net=net, encoder=encoder, temperature=0.0)
            table = cross_table(
                [
                    ("trained", greedy_agent),
                    ("random", eval_random_agent),
                    ("minimax", eval_minimax_agent),
                ],
                game=game,
                n_per_pair=hparams.eval_n_per_pair,
                seed=hparams.seed + update,
            )
            vs_random = table[("trained", "random")]
            vs_minimax = table[("trained", "minimax")]
            non_loss = (vs_random.wins[0] + vs_random.draws) / vs_random.n_games
            loss_vs_minimax = vs_minimax.wins[1] / vs_minimax.n_games
            metrics_logger.log(
                step=update,
                **loss_metrics,
                non_loss_vs_random=non_loss,
                loss_vs_minimax=loss_vs_minimax,
            )
        else:
            metrics_logger.log(step=update, **loss_metrics)

        if update % hparams.checkpoint_every == 0:
            checkpoint_store.save(gen=update, net=net, optimizer=optimizer, step=update)

    checkpoint_store.save(
        gen=hparams.total_updates,
        net=net,
        optimizer=optimizer,
        step=hparams.total_updates,
    )
    metrics_logger.close()
    return NeuralAgent(net=net, encoder=encoder, temperature=0.0)
```

- [ ] **Step 4: Run the non-slow tests**

Run: `uv run pytest tests/training/test_loop.py -m "not slow" -v`
Expected: 2 passed (`test_hparams_defaults_are_set`, `test_train_runs_and_writes_checkpoints_and_metrics`).

- [ ] **Step 5: Run the smoke test**

Run: `uv run pytest tests/training/test_loop.py::test_smoke_training_meets_v2_success_criteria -v -s`
Expected: PASS in under 5 minutes. If criteria fail: increase `HParams.total_updates` first (1500, then 2000); only reach for algorithm changes if budget tuning doesn't close the gap. If wall time blows past 5 minutes: lower `games_per_update` (e.g., 16) or `eval_n_per_pair` (e.g., 50).

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q -m "not slow"`
Expected: full non-slow suite passes in under a few seconds.

Run: `uv run pytest -q`
Expected: full suite (including slow) passes.

- [ ] **Step 7: Static checks**

Run: `uv run ruff check src tests`
Expected: clean. Fix any reported issues.

Run: `uv run ruff format src tests`
Expected: no changes (formatter is a no-op if you wrote ruff-compatible code).

Run: `uv run mypy`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/table_peak/training/loop.py tests/training/test_loop.py
git commit -m "feat(training): add HParams and train() with end-to-end smoke test"
```

---

## Final verification

- [ ] **Run the full suite once more, including the slow smoke test:**

```bash
uv run pytest -q
```

Expected: every test (including the smoke test) passes.

- [ ] **Confirm spec criteria are met:**

The smoke test (`test_smoke_training_meets_v2_success_criteria`) asserts:
- ≥95% non-loss vs `RandomAgent` over 500 side-swapped games
- ≤5% loss vs `MinimaxAgent` over 200 side-swapped games
- Zero wins vs `MinimaxAgent` (a win = bug in `agents/minimax.py`)
- Wall time < 5 minutes on CPU (pytest will not time it; you should observe the elapsed time)

- [ ] **Sanity-check the output artefacts:**

```bash
ls -la /tmp/pytest-of-*/pytest-current/test_smoke*/ckpt 2>/dev/null || true
# In a real training run from a script, you'll see gen_*.pt files and m.csv.
```
