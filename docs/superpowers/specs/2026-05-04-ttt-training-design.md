# TTT Training (v2) — Design

**Date:** 2026-05-04
**Status:** Shipped (with mid-implementation amendment, see "Algorithm" → "Self-play recipe")

## Goal

Build the v2 training infrastructure on top of the v1 framework: a self-play REINFORCE-with-baseline training loop that produces a `NeuralAgent` for tic-tac-toe. The TTT learning result is a smoke test; the load-bearing deliverable is the **transferable training stack** — neural net, optimizer, trajectory collection, opponent abstraction, checkpoints, eval harness — shaped so the eventual swap to NFSP / Deep CFR for partial-info card games (Skyjo, Skull King, 6 nimmt!, Coinche) is mostly a loss-function change plus `information_state` plumbing.

## Non-goals (v2)

- No PSRO population manager, Nash solver, or meta-game machinery (Skyjo-era, not now).
- No NFSP, Deep CFR, MCTS, or AlphaZero.
- No partial-info, no chance nodes, no simultaneous moves.
- No distributed / async self-play, no GPU-specific optimization.
- No Hydra / OmegaConf (frozen `HParams` dataclass instead).
- No W&B / TensorBoard / MLflow (CSV + `print()`).
- No CLI (invoked via `python -m table_peak.training.loop` or a tiny script).
- No formal resume-training test (we save enough to resume; we don't lock in the contract yet).

## Success criteria

Binary, machine-checkable:

1. Trained `NeuralAgent` achieves **≥95% non-loss rate** vs `RandomAgent` over 500 seeded games (side-swapped).
2. Trained `NeuralAgent` achieves **≤5% loss rate** vs `MinimaxAgent` over 200 seeded games (side-swapped). **Any win by `NeuralAgent` is a test failure** (signal of a bug in `agents/minimax.py`, since correct minimax cannot be beaten on TTT).
3. End-to-end smoke training run completes in **< 5 minutes on CPU**.
4. `NeuralAgent` plugs into existing `runner.play_game` / `runner.play_matches` unchanged.

## Architecture

### Style

Continue the v1 functional core / imperative shell pattern, with a loose hexagonal flavor: pure domain core (`games/`, `agents/`), Port Protocols at infrastructure boundaries, concrete adapters co-located with their ports.

### Module layout

```
src/table_peak/
├── games/             # unchanged (pure)
├── agents/
│   ├── base.py
│   ├── random.py
│   ├── minimax.py
│   └── neural.py      # NEW — NeuralAgent (inference only)
├── runner/            # unchanged
└── training/          # NEW — imperative shell for learning
    ├── encoder.py     # Encoder Port + TTT encoder
    ├── policy_net.py  # PolicyValueNet (tiny MLP, two heads)
    ├── buffer.py      # TrajectoryBuffer (on-policy)
    ├── self_play.py   # generate_episode, OpponentSampler Port + SelfOpponentSampler
    ├── reinforce.py   # update_step (loss + backward)
    ├── eval.py        # cross_table evaluation helper
    ├── checkpoint.py  # CheckpointStore Port + FileCheckpointStore
    ├── metrics.py     # MetricsLogger Port + CSVMetricsLogger
    └── loop.py        # train(...) — top-level orchestration + HParams
```

### Key architectural decisions

- **One-way dependency: `training/ → agents/`, never reverse.** `NeuralAgent` is inference-only; it never imports from `training/`. This keeps it usable from the web UI, evals, and future PSRO populations without dragging in optimizer or training-loop machinery.
- **`runner/` stays untouched.** The trainer needs per-player sample/return capture, which the existing `play_game` doesn't provide. `training/self_play.py` is its own episode generator. Avoiding a retrofit of `runner.play_game` keeps it boring and reusable.
- **No `Trainer` class.** `loop.train(hparams, ports...)` is a top-level function. No hidden state to encapsulate.
- **Flat `training/` package, one thing per file.** Each module can be replaced wholesale (e.g., `reinforce.py` → `nfsp.py`) without touching its siblings. That is the transferable scaffolding paying for itself.
- **No `ports/` or `adapters/` subfolders yet.** v2 introduces three Ports (`OpponentSampler`, `CheckpointStore`, `MetricsLogger`); each port + its default adapter share one file. The folder split earns its keep at ≥3 adapters per port, not now.

## Interfaces

Three new Port Protocols at the infrastructure seams. Each is co-located with its default adapter in the same module.

### `Encoder` (in `training/encoder.py`)

Pure transformation `State → Tensor` in **current-player perspective** — the network always sees "my pieces / opp pieces / empty," so a single net handles both P0 and P1 without a symmetry break. The TTT encoder produces a `(3, 3, 3)` tensor (channels: mine, opp, empty) and a `bool[9]` legal-action mask.

A Protocol so future games (Skyjo, etc.) can ship their own encoder without touching `policy_net.py`.

### `OpponentSampler` (in `training/self_play.py`)

Provides the opponent agent for a given training game. Default `SelfOpponentSampler` returns the currently-training agent (pure self-play). The Protocol is the seam for future opponent mixing (random + self curriculum) and eventually PSRO meta-strategy sampling.

**Note:** the v2 `train()` loop does not use `SelfOpponentSampler` exclusively — see "Self-play recipe" below for the mixed-opponent strategy that was needed to converge.

### `CheckpointStore` (in `training/checkpoint.py`)

Save/load the full training state (net weights + optimizer state + step counter + hparams snapshot), keyed by generation index. `FileCheckpointStore` writes `gen_NNNN.pt` files. The hparams snapshot allows mismatch detection on resume.

### `MetricsLogger` (in `training/metrics.py`)

Append a row per `log(step, **fields)` call. `CSVMetricsLogger` writes a CSV; `print()`-flavored stdout sibling is fine to add. W&B/TensorBoard are deferred — same Port, future adapter.

### `HParams` (frozen dataclass in `training/loop.py`)

Plain frozen dataclass: `games_per_update`, `total_updates`, `lr`, `entropy_coef`, `value_coef`, `train_temperature`, `random_opponent_fraction`, `eval_every`, `eval_n_per_pair`, `checkpoint_every`, `seed`. Defaults tuned for the <5-min smoke-test budget.

## Algorithm: REINFORCE with value baseline

### Why this and not vanilla REINFORCE

Vanilla REINFORCE has high variance on small action spaces; convergence is noisy. Adding a value-head baseline (subtracted from Monte Carlo returns to form the advantage) costs ~10 lines and one extra head, removes most of the variance. This is essentially actor-critic with Monte Carlo returns — a smaller code surface than full PPO, a much bigger training-stability improvement than vanilla.

### Why not PPO / DQN / AlphaZero-mini

- PPO: ~3× the code (clipping, GAE, multi-epoch updates) for stability we don't need on TTT-scale rewards.
- DQN: weaker pedagogical link to the eventual CFR/NFSP world for partial-info games.
- AlphaZero-mini: MCTS doesn't transfer cleanly to imperfect-info (would require ISMCTS, a different beast). Bigger upfront cost, less long-arc payoff.

### Loss

For each `(state, action, return)` sample:

- `advantage = return − value(state).detach()`
- `policy_loss = −log π(action | state) · advantage` (advantage-weighted policy gradient)
- `value_loss = MSE(value(state), return)`
- `entropy = −Σ π(a) log π(a)` over legal actions only
- `total_loss = policy_loss + value_coef · value_loss − entropy_coef · entropy`

### Algorithm-shape decisions

- **Returns are Monte Carlo, per-player perspective.** Same trajectory contributes samples for both P0 and P1 with their respective returns from `state.returns()`.
- **Value baseline is detached** so the policy gradient does not leak into value-head training.
- **No discount factor.** TTT episodes are bounded (≤9 moves) and reward is purely terminal; discounting adds nothing and removes a hyperparameter.
- **Entropy bonus** (`entropy_coef = 0.01`) prevents premature policy collapse.
- **Action sampling:** `temperature=1.0` (softmax over legal actions) during training; `temperature=0` (argmax) for eval / production inference.
- **Legal-action masking** is applied to logits (`-inf` on illegal) before softmax, both at training and inference.

### Network shape

Tiny MLP, ~5K parameters. `27 → 64 → 64`, then split into a 9-logit policy head and a `tanh`-bounded scalar value head. Bounded to `[-1, 1]` to match return range. CPU is plenty fast for this scale.

## Training loop (data flow)

The orchestration in `loop.train(...)`:

1. Initialize net, optimizer, `NeuralAgent` (with training temperature), `SelfOpponentSampler`.
2. For each update step (up to `total_updates`):
   - Generate `games_per_update` self-play episodes via `self_play.generate_episode`. Each episode contributes per-player `(state, action, return)` samples to a fresh `TrajectoryBuffer`.
   - Run `reinforce.update_step(net, opt, buffer, hparams)`. Log loss components.
   - Every `eval_every` steps: run `eval.cross_table([trained, random, minimax])`, log non-loss / loss / draw rates.
   - Every `checkpoint_every` steps: `checkpoint_store.save(gen=update, ...)`.
3. Final checkpoint at `gen=total_updates`.

### Self-play episode shape decisions

- **Dedicated training-side episode generator** in `training/self_play.py`, rather than retrofitting `runner.play_game`. The trainer needs per-player sample/return capture; `play_game` returns an aggregate `Outcome`. Keeping the training loop's needs out of `runner/` preserves its reusability.
- **Trajectory buffer is on-policy and cleared after every update.** No reservoir, no replay. The eventual NFSP swap will introduce a separate buffer abstraction; making this one polymorphic now would over-fit the design.
- **Encoding happens at batch construction time**, not per-sample during play. Cleaner CPU/tensor boundary, single conversion site.

### Self-play recipe (post-implementation amendment)

The original plan called for pure self-play via `SelfOpponentSampler`. During implementation, that recipe plateaued at ~70% non-loss vs Random across 1000–10000 updates: gradient updates from symmetric self-games provided no stable signal, so the policy oscillated rather than converging. To meet success criterion 1 within the 5-min budget, three orthogonal changes were folded directly into `train()`:

1. **Mixed opponents (`random_opponent_fraction = 0.7`).** 70 % of training games use a fresh `RandomAgent` opponent instead of the self-play sampler. This breaks the self-play cycle without the cost of maintaining a population.
2. **Side alternation.** Per game, the trained agent is randomly assigned to P0 or P1 (50/50). Without this, training is biased toward one seat while evaluation uses `swap_sides=True`.
3. **Filtered buffer when opponent is non-neural.** When the opponent is a `RandomAgent`, only the trained agent's own (state, action, return) samples enter the buffer — the random opponent's actions did not come from the policy under training, so attributing the terminal return to them adds pure noise.

These live inline in `train()` rather than behind a new Port. They are TTT-specific learning-stability fixes; if a future game needs the same pattern, the right move is to extract a `RandomMixingSampler` adapter at that point. Today, YAGNI.

`SelfOpponentSampler` and the `OpponentSampler` Protocol remain in `training/self_play.py` — the seam is correct, even though the v2 default loop reaches around it for the random-opponent fraction. The PSRO eventual replacement will use the Port for meta-strategy sampling and almost certainly drop the inline mixing.

## Eval (`eval.py`)

`cross_table(agents: list[(name, Agent)], game, n_per_pair, seed) → EvalTable` runs each ordered pair side-swapped, returns a rectangular `MatchStats` matrix. v2 uses `[("trained", agent), ("random", RandomAgent()), ("minimax", MinimaxAgent())]`. The matrix shape is also what the future PSRO meta-game payoff uses; same code path. Internally calls `runner.play_matches`.

A baseline measurement of the **freshly-initialized** `NeuralAgent` vs Random is taken before training and logged, to give the success-criterion-1 number a clean before/after read.

## Tech & tooling

| Concern | Choice | Why |
|---|---|---|
| NN framework | **PyTorch** | Default; no JAX ramp / ecosystem cost; CPU is fine for TTT |
| Device | **CPU** primary, MPS/CUDA opportunistic | Tiny net, device portability not load-bearing |
| Optimizer | **Adam, lr=1e-3** | Standard; no LR schedule; one less hyperparameter |
| Config | **Frozen `HParams` dataclass** | Hydra/OmegaConf deferred |
| Logging | **CSV via `MetricsLogger` Port + `print()`** | W&B et al. deferred; CSV is plottable later |
| Reproducibility | **Single `seed` threaded through `random.Random` and `torch.manual_seed`** | Matches v1 runner approach |
| Type checker / lint | **mypy --strict, ruff** | Same as v1 |
| Tests | **pytest** | Same as v1 |

## Testing

Aligned with project test guidelines: macro, black-box, fast.

| Test | What it asserts | Budget |
|---|---|---|
| Encoder roundtrip on known boards | Tensor shape/values match expected for hand-crafted positions | <0.1s |
| `NeuralAgent` plays a complete game (random init) | Returns legal action every move; episode terminates | <1s |
| Self-play episode generates well-formed `Episode` | Per-player samples + correct returns | <1s |
| `update_step` reduces loss on a fixed micro-batch | Single step decreases loss; no NaN/Inf | <2s |
| **End-to-end smoke training** | Success criteria 1 + 2 after a full budgeted run | < 5 min |
| Static layer | `mypy --strict`, `ruff check`, `ruff format` | <5s |

The end-to-end smoke training test is the spine. The others catch regressions cheaply during development.

**What we don't test:** individual NN weights, gradient values, optimizer-state internals, per-loss-component thresholds — all white-box and refactor-fragile.

### Error handling

- **Illegal action by trained net** (would mean masking is broken): `assert action in legal_actions` inside `generate_episode`. Hard fail in dev.
- **Loss NaN/Inf:** detect after `loss.backward()`, raise. No silent skip-step.
- **Checkpoint dir doesn't exist:** create on first save.
- **No retry/backoff:** training is single-process, local disk; failures are deterministic.

## Deferred (explicit YAGNI for v2)

These re-enter the design when concrete need shows up:

- PSRO population manager, Nash solver, empirical meta-game matrix abstractions.
- NFSP, Deep CFR, MCTS, AlphaZero variants.
- Distributed / async self-play, parallel episode generation.
- W&B, TensorBoard, MLflow.
- Hydra, OmegaConf.
- Dedicated `ports/` and `adapters/` subfolders (will earn their place when any single port grows to 3+ adapters).
- GPU-specific optimization, mixed precision.
- Formal resumable-training contract (we save enough to resume; we don't test the round-trip yet).
- CLI for training (invocation via `python -m` or a tiny script suffices).
- Web UI integration of `NeuralAgent` (trivial follow-up via `web/agents.py` registry once a checkpoint exists).

## Open questions / risks

- **REINFORCE convergence on TTT in <5 min CPU.** Resolved — pure self-play did not close the gap; the inline mixed-opponent + side-alternation + filtered-buffer recipe documented under "Self-play recipe" did, in ~62 s wall time on CPU.
- **PSRO transition cost.** The three Port Protocols (`OpponentSampler`, `CheckpointStore`, `MetricsLogger`) are designed to make the eventual PSRO leap mechanical (population manager + Nash solver + per-generation snapshots). Validated only at design time; the actual transition will exercise it.
