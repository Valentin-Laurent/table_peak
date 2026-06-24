# open_spiel training feasibility spike (Skyjo) — design

**Bead:** `table_peak-2vs.6` · **Brainstorm:** `table_peak-17r` · **Gates:** `table_peak-2vs.4`
**Date:** 2026-06-24

## Purpose

De-risk the learning track before planning the real proof-of-learning agent (`2vs.4`).
Prove that open_spiel's NFSP and Deep CFR can actually run end-to-end on the registered
`skyjo` game, and surface the **training-payoff decision** with evidence rather than a guess.

This is a **spike**: it produces findings, not reusable infrastructure. The real
train → checkpoint → play harness is `2vs.4`'s job. Fixed at **2 players**.

## Decisions

- **Success bar:** runs + directional signal. A config "passes" when it (a) completes N
  training iterations without crashing, and (b) shows a weak learning signal afterward
  (beats `RandomAgent` above chance). Not required to beat the heuristic — that's `2vs.4`.
- **Backend:** **PyTorch (CPU)**. Already declared in `pyproject.toml` (`torch>=2.5`); the
  venv is simply unsynced, so step 0 is `make sync`, not a new dependency. Use the
  `open_spiel/python/pytorch/` implementations.
- **Algorithms:** **NFSP** and **DQN** are the two viable candidates, each probed across
  both payoffs. **Deep CFR** is demoted to a single time-boxed *feasibility verdict* (see
  Risks) — its exhaustive own-action tree traversal makes a real training cell impractical
  on Skyjo's game length.
- **Payoff:** probe **both** zero-sum representations (win/loss and score-margin). The
  spike reports which gives the cleaner learning signal.
- **Payoff transform location:** applied to the **terminal `TimeStep.rewards` inside the
  RL training loop** (NFSP/DQN), via the pure `zero_sum_returns()` function. The real Skyjo
  engine is left untouched. (The earlier draft put a shared `returns()`-overriding wrapper at
  state level so Deep CFR's direct `state.returns()` call would see it too; once Deep CFR was
  demoted to a feasibility-only probe with no learning cell, there was no signal to keep
  comparable, so the probe simply runs on the base game and the loop-level transform suffices.)
- **Code location:** kept in-repo under `spikes/`, clearly marked disposable, and
  **excluded from ruff** (`[tool.ruff] extend-exclude = ["spikes"]`). pytest (`testpaths`)
  and mypy (`files`) already ignore it. The working reward-wrapper and env setup are
  exactly what `2vs.4` will start from, so keeping them is nearly free.

## Experiment matrix

Two viable RL methods × two payoffs = 4 training cells, plus one Deep CFR feasibility cell.
Each training cell runs for a short fixed budget:

|          | win/loss ±1 | score-margin |
| -------- | ----------- | ------------ |
| **NFSP** | run 1       | run 2        |
| **DQN**  | run 3       | run 4        |
| **Deep CFR** | feasibility verdict only — time-boxed, single iteration, no signal expected ||

DQN is chosen as the second method because open_spiel's NFSP is built on a DQN inner agent,
so they share observation/network plumbing — minimal extra surface.

A **zero-sum payoff wrapper** overrides `returns()` on top of Skyjo's raw `GENERAL_SUM`
returns (shared by `rl_environment` and Deep CFR's direct `returns()` call):

- **win/loss ±1:** winner +1, loser −1, tie 0/0. Clean 2-player zero-sum; safest baseline
  for both algorithms' convergence assumptions. Discards score-margin information.
- **score-margin:** reward = (opponent_score − my_score), normalized. Antisymmetric
  (still zero-sum), richer gradient, but larger/noisier scale may hurt stability.

The wrapper is the one piece of "real" thinking the spike surfaces for `2vs.4`.

## What each cell measures (two gates)

- **Plumbing gate:** N iterations complete with no error on (a) long 2000-move games,
  (b) the general-sum → zero-sum payoff handoff, (c) legal-action masking. As a one-time
  setup check, assert the observation tensor is well-formed at the fixed 2-player size.
- **Signal gate:** after short training, the agent beats `RandomAgent` above chance
  (e.g. > 55% win-rate over M eval games). Directional only.

**Eval hygiene** (so the signal gate can't pass on a degenerate policy):

- **Seat-balanced eval** — evaluate with the agent as both P0 and P1 (even split), report
  combined win-rate; Skyjo has a first-mover effect.
- **Log score-margin, not just win-rate** — a real win should also show a favorable
  average score-margin vs random, catching trivial/degenerate wins.
- **Episode-length check** — once, on the random baseline, measure median/max episode
  length. Confirm games end naturally well under the 2000 cap (otherwise truncated returns
  pollute the signal).

## Deliverable

A short findings note (the artifact that gates `2vs.4`):

- Per-cell pass/fail on both gates.
- Which payoff gives the cleaner signal.
- **Deep CFR feasibility verdict** — does it run on explicit-stochastic + long games, or
  is it impractical here?
- **Recommended config** for `2vs.4`.

Findings also captured via `bd remember` so the next session inherits them.

## Risks & kill-switches

- **Deep CFR blowup (expected):** open_spiel's `pytorch/deep_cfr.py` recurses into *every*
  legal action at the traverser's own decision nodes (only chance/opponent are sampled),
  so a single traversal is exponential in the number of own decisions — near-certainly
  impractical on Skyjo's game length. Its eval path also calls `exploitability.nash_conv`,
  which enumerates the whole game; set `print_nash_convs=False`. Run Deep CFR only as a
  time-boxed, single-iteration probe with a hard wall-clock cap; the expected, valuable
  finding is "confirmed impractical, here's why."
- **Zero-sum API friction:** open_spiel's CFR/NFSP utilities may expect a zero-sum *game*,
  not just a zero-sum *reward*. If Skyjo's `GENERAL_SUM` registration blocks an algorithm
  from loading at all, that is a finding — and a flag that `2vs.4` may need a registered
  zero-sum Skyjo variant.

## Out of scope

- N-player (> 2) training.
- A reusable/production training harness, checkpoint format, or web wiring (`2vs.4`, `2vs.5`).
- Hyperparameter tuning beyond what's needed to clear the signal gate.
- Beating the heuristic agent (`2vs.2`).

## Stress Test Results: open_spiel training feasibility spike

Adversarial review (`table_peak-da2`), 5 branches, all resolved. Grounded in the installed
open_spiel source and project config.

### Resolved Decisions
- **NN backend:** PyTorch CPU. Discovered `torch`/`jax` both fail to import, but `torch>=2.5`
  is already declared in `pyproject.toml` — the venv is just unsynced. Step 0 = `make sync`.
- **Deep CFR demoted:** its `_traverse_game_tree` does an exhaustive walk of the traverser's
  own-action subtree (exponential in own decisions), so a real training cell is impractical
  on Skyjo. Demoted to a time-boxed feasibility verdict; **DQN added as the genuine second
  RL method** alongside NFSP.
- **Payoff transform at state/game level:** Deep CFR reads `state.returns()` directly,
  bypassing any env wrapper, so the zero-sum transform must override `returns()` to stay
  consistent across all consumers.
- **Eval hygiene:** seat-balanced eval, log score-margin alongside win-rate, one-time
  episode-length check on the random baseline.
- **Quality gates:** exclude `spikes/` from ruff only; pytest/mypy already ignore it.

### Changes Made
- Matrix is now NFSP + DQN (2 payoffs each) + a single Deep CFR feasibility cell.
- Backend named (PyTorch) with `make sync` as the prerequisite.
- Reward "wrapper" re-specified as a `returns()`-overriding state/game wrapper.
- Added eval-hygiene requirements, observation-tensor sanity check, and `print_nash_convs=False`.
- Added `[tool.ruff] extend-exclude = ["spikes"]`.

### Deferred / Parking Lot
- DQN-vs-PPO: chose DQN (shares NFSP plumbing); PPO untried unless DQN disappoints.
- N-player, checkpoint format, web wiring, heuristic comparison — all `2vs.4`+.

### Confidence Assessment
- Overall: **High** for NFSP/DQN running and producing a directional signal.
- Areas of concern: Deep CFR is expected to be confirmed impractical (by design, not a
  surprise); the open question is purely whether the verdict is "slow" vs "won't finish one
  traversal." Signal strength after a *short* budget is inherently uncertain — that's why
  the bar is directional, not strength-based.
