# External implementations — evaluation log

Curated record of third-party implementations we evaluated for reuse in `table_peak`. One section per project. Each entry should cover what it is, what reuse we considered, what we found, and the decision.

## Skyjo — Guillaume-Barthe/Skyjo

- **Repo:** https://github.com/Guillaume-Barthe/Skyjo
- **What it is:** Python Skyjo environment (1- and 2-player) wrapped as `gym.Env`, plus PPO agents trained with `stable_baselines3` and a small `tkinter` UI for human play.
- **Evaluated:** 2026-05-02
- **Decision:** Do not reuse. Defer the Skyjo engine entirely for now.

### What we considered reusing

- The `Card` class and a few board utilities (`init_board`, `get_board_as_int`, `undiscovered_tiles`, `compute_score`).
- The `SkyjoEnv` game logic (deck composition, turn structure, scoring, end-of-game).
- The pre-trained PPO agents in `trained_models/`.

### Why we did not reuse

1. **No license.** The repo ships no `LICENSE` file. Under default copyright law all rights are reserved, so vendoring the code is not legally clear.
2. **Rule discrepancies vs. official Skyjo.**
   - `erase_column` skips columns of zeros; official rules erase any three-of-a-kind column.
   - "Discard drawn card" reveals a *random* hidden card; official rules let the player choose which card to reveal.
   - No "last turn for everyone" trigger and no score doubling when the trigger player isn't lowest.
   - Initial 2 revealed cards are random; official rules let the player choose.
   - Single round only; no game-to-100 multi-round play.
   - 2-player observation exposes the opponent's hidden card values (partial-info leak).
3. **Architecture mismatch.** The env mutates state in place; `table_peak` uses an immutable `State` Protocol with `apply_action(self) -> State`. Adapting either side is more work than rewriting clean.
4. **Trained agents not transferable.** The PPO models are tied to a specific 27-dim observation, `MultiDiscrete([2, 13])` action space, bespoke reward shaping, and the non-official rules above. Different rules invalidate the policy; different obs/action shapes prevent loading the weights at all. "Retrain on a corrected env" is indistinguishable from training from scratch.

### Reference value retained

Even without code reuse, the repo is useful as a reference for: deck composition, a workable two-phase action shape, RL feasibility with PPO on this game, and confirmation that mid-thousands of training steps are needed for reasonable play. Worth revisiting if and when we implement our own Skyjo engine.
