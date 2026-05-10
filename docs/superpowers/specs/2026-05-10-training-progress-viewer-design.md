# Training Progress Viewer — Design

**Date:** 2026-05-10
**Status:** Drafted

## Goal

Surface visibility into in-progress training runs via a terminal viewer. Decouple producer (training) from consumer (viewer) through a `RunStore` Port + filesystem convention so future renderers (web, notebook) drop in as adapters without changing the training side.

The TTT smoke run (~62s) is the immediate test bed; the load-bearing motivation is upcoming hours/days runs (Skyjo, Skull King, etc.) where post-hoc CSV inspection won't suffice and where comparing across hparam sweeps will become routine.

## Non-goals (v1)

- No multi-run listing/compare in viewer (CLI takes one run only; `--latest` resolution is the only multi-run touch).
- No web UI (different adapter, future).
- No run-status tracking (no "running"/"completed"/"failed" markers; viewer keeps polling until Ctrl-C).
- No inotify / fs-event subscriptions (poll the file).
- No custom dashboard layout or metric grouping config (viewer is schema-agnostic — one panel per CSV column).
- No notebook / Jupyter integration.
- No checkpoint browsing.
- No HParams overrides via CLI flags on the training entry-point (defaults only; tweak via script for now).

## Success criteria

Binary, machine-checkable:

1. `python -m table_peak.training.train` produces `runs/<run_id>/` containing `metrics.csv`, `hparams.json`, `checkpoints/`. `run_id` is timestamp-derived and lex-sorts chronologically.
2. `python -m table_peak.training.viz --latest` (or `--run <id>`), launched in a second terminal during step 1, renders live-updating plotext charts. New rows appear in the viewer within ~1s of being written.
3. Viewer renders TTT metrics (`policy_loss`, `value_loss`, `entropy`, `total_loss`, `non_loss_vs_random`, `loss_vs_minimax`) without any TTT-specific code path — purely from the CSV header.
4. `RunStore` Port + `FileRunStore` adapter exist; the viewer never imports `Run` or training internals.
5. `mypy --strict`, `ruff check`, `ruff format --check` clean. Macro tests pass.

## Architecture

### Style

Continue the v2 functional-core / imperative-shell pattern with a loose hex-arch flavor: pure modules where possible, Port Protocols at boundaries, default adapter co-located with the Port.

### Module layout

```
src/table_peak/training/
├── ... (unchanged: encoder, policy_net, buffer, self_play, reinforce, eval, checkpoint, metrics, loop)
├── run.py            # NEW — Run (producer) + RunStore Port + FileRunStore (consumer)
├── viz.py            # NEW — plotext terminal viewer; entry-point via __main__
└── train.py          # NEW — production entry-point: builds Run + default HParams, calls train()
```

`loop.py` does not change. The `Run` concept is purely additive; existing tests that construct their own loggers remain valid.

### Key architectural decisions

- **`Run` is producer-side only; `RunStore` is consumer-side only.** They share a directory convention but no Python types. The viewer must not import `Run` (and won't need to). This is the hex seam.
- **Single `run.py` module hosts both sides.** They share the dir layout as a single source of truth. Splitting into `run.py` + `run_store.py` earns its keep when `RunStore` grows a second adapter (e.g., S3) — not now.
- **`train()` signature unchanged.** The wiring `Run → CSVMetricsLogger + FileCheckpointStore` happens in the *caller* (the new `train.py` entry-point). Keeps `train()` flexible (tests pass their own loggers) and keeps `Run` from being load-bearing for `train()`.
- **Schema-agnostic viewer.** plotext panels are generated from the CSV header at runtime. No hardcoded TTT column names. When Skyjo training emits a different schema, the viewer adapts with no code change.
- **Polling, not inotify.** Viewer polls the CSV every ~1s, reads new lines from last byte offset. Cross-platform, zero-dep, sufficient at this scale.

## Interfaces

### `Run` (producer-side, in `training/run.py`)

```
Run.create(*, root: Path = Path("runs"), name: str | None = None) -> Run
```

Creates `runs/<run_id>/` and returns a handle. `run_id` = `YYYYMMDD-HHMMSS[-<name>]` (timestamp + optional human label). Format chosen for chronological lex-sort and trivial `--latest` resolution.

`Run` exposes:
- `.dir: Path` — the run directory
- `.metrics_logger(fields: Iterable[str]) -> CSVMetricsLogger` — wired to `<dir>/metrics.csv`
- `.checkpoint_store() -> FileCheckpointStore` — wired to `<dir>/checkpoints/`
- `.write_hparams(hparams: object) -> None` — dumps to `<dir>/hparams.json` (uses `dataclasses.asdict` for dataclass instances; raises for unsupported types)

### `RunStore` Port (consumer-side, in `training/run.py`)

```python
@runtime_checkable
class RunStore(Protocol):
    def list_runs(self) -> list[str]: ...
    def latest(self) -> str | None: ...
    def iter_rows(
        self, run_id: str, since_byte: int = 0
    ) -> Iterator[tuple[dict[str, str], int]]: ...
```

`iter_rows` yields `(row_dict, new_byte_offset)` for incremental reads. Returns columns as `dict[str, str]` — the consumer is responsible for casting. Numeric-looking values become floats in the renderer; non-numeric values are surfaced as a latest-text panel.

`FileRunStore(root: Path = Path("runs"))` is the default adapter.

### Viewer entry-point (in `training/viz.py`)

CLI: `python -m table_peak.training.viz [--run RUN_ID] [--latest] [--root PATH] [--poll-seconds N]`

Behavior:
- Resolves `run_id` via `--run` or `RunStore.latest()` (from `--latest`).
- Reads the CSV header to determine columns.
- Polls every `--poll-seconds` (default 1.0).
- Renders one plotext panel per numeric column; eval columns (sparsely populated) skip empty cells.
- Ctrl-C exits cleanly.

plotext is a runtime dependency (added in this feature).

### Training entry-point (in `training/train.py`)

CLI: `python -m table_peak.training.train [--name NAME] [--root PATH]`

Wires: `Run.create(name=...)` → constructs `CSVMetricsLogger` + `FileCheckpointStore` from the Run → writes `hparams.json` → calls `train(...)` with default `HParams` and `TicTacToe()` as the `Game`. This is the production launcher; other configurations remain the domain of test code or one-off scripts.

## Run directory convention

```
runs/
└── 20260510-143012-tttsmoke/
    ├── hparams.json           # serialized HParams + metadata (started_at, game name)
    ├── metrics.csv            # CSVMetricsLogger output
    └── checkpoints/
        └── gen_NNNN.pt
```

`runs/` lives at repo root, gitignored. Override via `--root` on either entry-point; tests use `tmp_path`.

## Data flow

1. User runs `python -m table_peak.training.train [--name NAME]`.
2. `Run.create()` makes `runs/<id>/`, writes `hparams.json`.
3. `train()` runs; `CSVMetricsLogger` appends one row per update step, flushing after each.
4. In another terminal, user runs `python -m table_peak.training.viz --latest`.
5. Viewer resolves `<id>` via `RunStore.latest()`, opens `metrics.csv`, reads header, polls for new rows, redraws panels.
6. Training ends; CSV stops growing; viewer keeps polling until Ctrl-C (no completion signal in v1).

## Schema-agnostic rendering

- Header determines the column set.
- Each non-`step` column gets a panel. Numeric-castable values are plotted; non-numeric values display as the latest text value (forward-compat for future string metrics, e.g., "current opponent").
- Sparse columns (e.g., `non_loss_vs_random` populated every 200 steps) are plotted only at filled steps.

## Tech & tooling

| Concern | Choice | Why |
|---|---|---|
| Renderer | **plotext** | Inline ASCII charts; works over SSH; no GUI; tiny pure-Python dep |
| Watcher mechanism | **Polling (1s default)** | Cross-platform, zero platform-specific deps, sufficient at this data scale |
| Run ID format | **`YYYYMMDD-HHMMSS[-<name>]`** | Lex-chronological; trivially `--latest`-able; human-readable |
| HParams snapshot | **JSON via `dataclasses.asdict`** | Compatible with frozen `HParams`; readable; no schema lock-in |
| Lint / type | **ruff, mypy --strict** | Project standard |

## Testing

Aligned with project test guidelines (macro, black-box, fast).

| Test | What it asserts | Budget |
|---|---|---|
| `Run.create()` produces a valid run dir | Dir exists; `hparams.json` is parseable when written; loggers point inside the dir | <0.1s |
| `Run.metrics_logger(...)` writes inside the dir | Returned `CSVMetricsLogger` appends to `<dir>/metrics.csv` | <0.1s |
| `FileRunStore.list_runs()` returns chronological order | Lex sort matches creation order across ≥3 runs | <0.1s |
| `FileRunStore.latest()` | Returns the last-ordered ID; `None` for empty `runs/` | <0.1s |
| `FileRunStore.iter_rows()` incremental | Returns only new rows after `since_byte`; offsets advance correctly across reads | <0.5s |
| Viewer wiring (single-frame mode) | With a sample run dir + a test-only `--frames=1` flag, viewer renders one frame and exits 0 | <1s |
| Training entry-point smoke (5 updates) | `python -m table_peak.training.train` with `total_updates=5` produces a valid run dir | <2s |
| Static layer | `mypy --strict`; `ruff check`; `ruff format --check` | <5s |

**What we don't test:** plotext rendering output (white-box, terminal-dependent), the interactive watch loop's redraw cycle, real-time race conditions between writer and reader (covered by integration only at the byte-offset level).

## Error handling

- **`--run NONEXISTENT`:** clear error, exit non-zero.
- **`--latest` with no runs in `--root`:** clear error, exit non-zero.
- **CSV header not yet written when viewer starts:** viewer retries up to ~10s (race: viewer launched before training writes the header), then errors.
- **Partial row mid-read (training writes a row while viewer reads):** `CSVMetricsLogger.flush()` runs after each `writerow`; viewer reads up to last `\n`; any partial trailing bytes stay in the next read via the byte-offset return.
- **Non-numeric column values:** rendered as latest text panel; do not crash plotting.
- **Training crash mid-run:** no detection in v1; viewer keeps polling until Ctrl-C (deliberate).

## Forbidden zones

This feature owns exclusive write access during its in-flight window to:

```
src/table_peak/training/run.py
src/table_peak/training/viz.py
src/table_peak/training/train.py
tests/training/test_run.py
tests/training/test_viz.py
tests/training/test_train.py
runs/**
```

Additive single edits to shared files (NOT claimed exclusive — siblings may also touch these; merge-time conflicts will be rare and trivial):

- `pyproject.toml` — adds `plotext` to `dependencies`
- `.gitignore` — adds `runs/`

## Deferred (explicit YAGNI)

These re-enter the design when concrete need shows up:

- Multi-run listing/compare/overlay in viewer (Port already supports it).
- Web adapter (FastAPI in existing `web/`).
- Notebook / Jupyter adapter.
- Run-status markers (`running`/`completed`/`failed`).
- inotify / fs-event subscriptions.
- Run pruning / disk-space management.
- HParams overrides via CLI flags on the training entry-point.
- Checkpoint browsing in the viewer.
- Color/theme config.
- Run tagging / search / filtering.

## Open questions / risks

- **plotext API stability.** Small library, active maintenance; the viewer uses ~5 entry points. Risk is low; if it breaks we swap renderer adapters (other Port consumers unaffected).
- **CSV concurrent read/write semantics.** `csv.DictWriter.writerow` + `flush()` produces line-atomic writes for short rows on POSIX. The viewer reads up to the last `\n` and tracks byte offset. Verified empirically; documented in tests.
- **Polling cost.** Negligible — a TTT CSV is at most ~250KB at `total_updates=4000` × ~7 columns × ~50 bytes. Per-step incremental reads via byte offset keep this O(1) per poll regardless of run length.
