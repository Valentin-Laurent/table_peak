# Training Progress Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a terminal-rendered live training-metrics viewer (plotext) backed by a `RunStore` Port + filesystem run-dir convention, plus a thin training-launcher entry-point that uses the new run-dir layout.

**Architecture:** Producer/consumer decoupled by the filesystem. `Run` (producer-side) coordinates a per-run dir under `runs/<id>/`. `RunStore` (consumer-side Port) hides the dir convention from renderers; `FileRunStore` is the default filesystem adapter. `viz.py` is the only renderer in v1 — a plotext CLI that polls and redraws. `train.py` wires `Run` + default `HParams` + `train()` for production launches.

**Tech Stack:** Python 3.12, `plotext` (new dep), existing `CSVMetricsLogger` and `FileCheckpointStore`, `argparse`, pytest, mypy --strict, ruff.

**Spec:** `docs/superpowers/specs/2026-05-10-training-progress-viewer-design.md`

**Forbidden zones (this feature owns exclusive write):**
- `src/table_peak/training/run.py`
- `src/table_peak/training/viz.py`
- `src/table_peak/training/train.py`
- `tests/training/test_run.py`
- `tests/training/test_viz.py`
- `tests/training/test_train.py`
- `runs/**`

Additive single edits to shared files: `pyproject.toml` (add `plotext`), `.gitignore` (add `runs/`).

**Sibling forbidden zones to respect (do NOT write):** none — this is the only in-flight feature.

**Test commands (controller may need to fall back to direct venv-python; subagents in auto mode use uv):**
- `uv run pytest tests/training/<file> -v`
- `uv run mypy --strict src tests`
- `uv run ruff check src tests && uv run ruff format --check src tests`
- Fallback: `/Users/valentinlaurent/code/perso/table_peak/.venv/bin/python -m pytest <args>`

---

## Task 1: Add `plotext` dependency and gitignore `runs/`

**Files:**
- Modify: `pyproject.toml` (add to `dependencies`)
- Modify: `.gitignore` (add `runs/`)

- [ ] **Step 1: Add `plotext` to project dependencies**

Edit `pyproject.toml`. Locate the `dependencies = [...]` array and add `"plotext>=5.3"`:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "torch>=2.5",
    "plotext>=5.3",
]
```

- [ ] **Step 2: Sync the lockfile**

Run: `uv sync`

Expected: lockfile updates with `plotext` added; no errors.

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "import plotext; print(plotext.__version__)"`

Expected: prints a version (e.g. `5.3.x`).

- [ ] **Step 4: Add `runs/` to .gitignore**

Edit `.gitignore`. Append a new section before the existing `# Git worktrees` block (or after it):

```gitignore
# Training run artifacts (created by table_peak.training.run.Run)
runs/
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .gitignore
git commit -m "chore: add plotext dep and gitignore runs/ for training viewer"
```

---

## Task 2: `Run` (producer-side coordinator)

**Files:**
- Create: `src/table_peak/training/run.py`
- Create: `tests/training/test_run.py`

- [ ] **Step 1: Write failing tests for `Run`**

Create `tests/training/test_run.py`:

```python
"""Tests for the Run producer-side coordinator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from table_peak.training.run import Run


def test_create_makes_dir_with_timestamp_id(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    assert run.dir.exists()
    assert run.dir.parent == tmp_path
    # YYYYMMDD-HHMMSS prefix; 15 chars
    assert len(run.dir.name) >= 15
    assert run.dir.name[8] == "-"


def test_create_with_name_appends_suffix(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path, name="my-experiment")
    assert run.dir.name.endswith("-my-experiment")


def test_metrics_logger_writes_inside_dir(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    logger = run.metrics_logger(fields=["loss"])
    logger.log(step=1, loss=0.5)
    logger.close()
    csv_path = run.dir / "metrics.csv"
    assert csv_path.exists()
    contents = csv_path.read_text()
    assert "step,loss" in contents
    assert "1,0.5" in contents


def test_checkpoint_store_points_inside_dir(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    store = run.checkpoint_store()
    # FileCheckpointStore exposes _root via construction; we test via behavior
    # by saving a dummy checkpoint and checking the path.
    import torch
    from torch import nn

    net = nn.Linear(2, 2)
    opt = torch.optim.SGD(net.parameters(), lr=0.1)
    store.save(gen=1, net=net, optimizer=opt, step=1)
    expected = run.dir / "checkpoints" / "gen_0001.pt"
    assert expected.exists()


def test_write_hparams_serializes_dataclass(tmp_path: Path) -> None:
    @dataclass(frozen=True)
    class FakeHParams:
        lr: float = 1e-3
        seed: int = 42

    run = Run.create(root=tmp_path)
    run.write_hparams(FakeHParams())
    hp_path = run.dir / "hparams.json"
    assert hp_path.exists()
    payload = json.loads(hp_path.read_text())
    assert payload["lr"] == 1e-3
    assert payload["seed"] == 42


def test_write_hparams_rejects_non_dataclass(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    with pytest.raises(TypeError):
        run.write_hparams({"lr": 1e-3})  # plain dict not accepted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_run.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'table_peak.training.run'`.

- [ ] **Step 3: Implement `Run`**

Create `src/table_peak/training/run.py`:

```python
"""Run: producer-side coordinator for a training run dir.

A `Run` owns one directory under `runs/<id>/` and produces the metrics logger
and checkpoint store wired to it. The directory layout is the seam consumed
by `RunStore` (see same module, below — added in Task 3).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from table_peak.training.checkpoint import FileCheckpointStore
from table_peak.training.metrics import CSVMetricsLogger


class Run:
    """One training run rooted at `<root>/<run_id>/`."""

    def __init__(self, dir: Path) -> None:
        self._dir = dir

    @property
    def dir(self) -> Path:
        return self._dir

    @classmethod
    def create(cls, *, root: Path = Path("runs"), name: str | None = None) -> Run:
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_id = f"{timestamp}-{name}" if name else timestamp
        run_dir = Path(root) / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return cls(run_dir)

    def metrics_logger(self, fields: Iterable[str]) -> CSVMetricsLogger:
        return CSVMetricsLogger(self._dir / "metrics.csv", fields=fields)

    def checkpoint_store(self) -> FileCheckpointStore:
        return FileCheckpointStore(self._dir / "checkpoints")

    def write_hparams(self, hparams: object) -> None:
        if not dataclasses.is_dataclass(hparams) or isinstance(hparams, type):
            raise TypeError(
                f"write_hparams expects a dataclass instance, got {type(hparams).__name__}"
            )
        payload = dataclasses.asdict(hparams)
        (self._dir / "hparams.json").write_text(json.dumps(payload, indent=2, default=str))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_run.py -v`

Expected: all 6 tests PASS.

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy --strict src tests && uv run ruff check src tests && uv run ruff format src tests`

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/training/run.py tests/training/test_run.py
git commit -m "feat(training): add Run producer-side coordinator for run dirs"
```

---

## Task 3: `RunStore` Port + `FileRunStore` adapter

**Files:**
- Modify: `src/table_peak/training/run.py` (append `RunStore` Protocol + `FileRunStore` class)
- Modify: `tests/training/test_run.py` (append RunStore tests)

- [ ] **Step 1: Write failing tests for `RunStore`**

Append to `tests/training/test_run.py`:

```python
import time

from table_peak.training.run import FileRunStore, RunStore


def test_filerunstore_implements_protocol(tmp_path: Path) -> None:
    store: RunStore = FileRunStore(root=tmp_path)
    assert isinstance(store, RunStore)


def test_list_runs_returns_chronological_order(tmp_path: Path) -> None:
    # Create three runs with distinguishable timestamps.
    r1 = Run.create(root=tmp_path, name="first")
    time.sleep(1.1)  # ensure timestamp tick
    r2 = Run.create(root=tmp_path, name="second")
    time.sleep(1.1)
    r3 = Run.create(root=tmp_path, name="third")
    store = FileRunStore(root=tmp_path)
    ids = store.list_runs()
    assert ids == [r1.dir.name, r2.dir.name, r3.dir.name]


def test_list_runs_empty_root(tmp_path: Path) -> None:
    store = FileRunStore(root=tmp_path)
    assert store.list_runs() == []


def test_latest_returns_last(tmp_path: Path) -> None:
    Run.create(root=tmp_path, name="a")
    time.sleep(1.1)
    r = Run.create(root=tmp_path, name="b")
    store = FileRunStore(root=tmp_path)
    assert store.latest() == r.dir.name


def test_latest_none_for_empty_root(tmp_path: Path) -> None:
    store = FileRunStore(root=tmp_path)
    assert store.latest() is None


def test_iter_rows_returns_all_rows_from_zero(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    logger = run.metrics_logger(fields=["loss"])
    logger.log(step=1, loss=0.5)
    logger.log(step=2, loss=0.4)
    logger.close()
    store = FileRunStore(root=tmp_path)
    rows_with_offsets = list(store.iter_rows(run.dir.name, since_byte=0))
    assert len(rows_with_offsets) == 2
    rows = [r for r, _ in rows_with_offsets]
    assert rows[0] == {"step": "1", "loss": "0.5"}
    assert rows[1] == {"step": "2", "loss": "0.4"}
    # Offsets must strictly increase
    offsets = [o for _, o in rows_with_offsets]
    assert offsets[0] < offsets[1]


def test_iter_rows_incremental_with_since_byte(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    logger = run.metrics_logger(fields=["loss"])
    logger.log(step=1, loss=0.5)
    store = FileRunStore(root=tmp_path)
    first_pass = list(store.iter_rows(run.dir.name, since_byte=0))
    assert len(first_pass) == 1
    last_offset = first_pass[-1][1]
    # Append another row, then resume from last_offset
    logger.log(step=2, loss=0.4)
    logger.close()
    second_pass = list(store.iter_rows(run.dir.name, since_byte=last_offset))
    assert len(second_pass) == 1
    assert second_pass[0][0] == {"step": "2", "loss": "0.4"}


def test_iter_rows_unknown_run_raises(tmp_path: Path) -> None:
    store = FileRunStore(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        list(store.iter_rows("nonexistent-run", since_byte=0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_run.py -v`

Expected: new tests FAIL (`RunStore`, `FileRunStore` not importable).

- [ ] **Step 3: Implement `RunStore` and `FileRunStore`**

Append to `src/table_peak/training/run.py`:

```python
import csv
import io
from collections.abc import Iterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class RunStore(Protocol):
    """Consumer-side port: list runs and read their metrics rows."""

    def list_runs(self) -> list[str]: ...

    def latest(self) -> str | None: ...

    def iter_rows(
        self, run_id: str, since_byte: int = 0
    ) -> Iterator[tuple[dict[str, str], int]]:
        """Yield (row_dict, new_byte_offset) pairs from `metrics.csv` for run_id.

        On the first call, pass `since_byte=0`. On subsequent calls, pass the
        last yielded offset to read only newly-appended rows. Stops when no
        more complete rows are available; partial trailing bytes are skipped
        and surface on the next call.

        Raises `FileNotFoundError` if the run dir does not exist.
        """
        ...


class FileRunStore:
    """Filesystem adapter: each run lives at `<root>/<run_id>/`."""

    def __init__(self, *, root: Path = Path("runs")) -> None:
        self._root = Path(root)

    def list_runs(self) -> list[str]:
        if not self._root.exists():
            return []
        return sorted(p.name for p in self._root.iterdir() if p.is_dir())

    def latest(self) -> str | None:
        runs = self.list_runs()
        return runs[-1] if runs else None

    def metrics_path(self, run_id: str) -> Path:
        """Where this adapter stores the metrics CSV for a run.

        Adapter-specific helper used by the file-aware viewer to read the
        header row directly. Not part of the `RunStore` Protocol on purpose;
        non-filesystem adapters won't have a meaningful path.
        """
        return self._root / run_id / "metrics.csv"

    def iter_rows(
        self, run_id: str, since_byte: int = 0
    ) -> Iterator[tuple[dict[str, str], int]]:
        run_dir = self._root / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"run dir does not exist: {run_dir}")
        csv_path = run_dir / "metrics.csv"
        if not csv_path.exists():
            return
        with csv_path.open("rb") as f:
            # Read header once (always from byte 0) to know column names.
            f.seek(0)
            header_line = f.readline()
            if not header_line.endswith(b"\n"):
                # Header not yet flushed completely; nothing to yield.
                return
            header_end = f.tell()
            fieldnames = header_line.decode("utf-8").strip().split(",")

            # Seek to wherever the consumer asked to resume from, but never
            # before the end of the header.
            start = max(since_byte, header_end)
            f.seek(start)
            remainder = f.read()

        # Walk only complete lines; drop any partial trailing bytes.
        last_newline = remainder.rfind(b"\n")
        if last_newline < 0:
            return
        complete_block = remainder[: last_newline + 1].decode("utf-8")
        new_offset = start + last_newline + 1
        reader = csv.DictReader(io.StringIO(complete_block), fieldnames=fieldnames)
        # Track per-row offsets so callers can resume mid-stream.
        running = start
        for raw_row, line in zip(reader, complete_block.splitlines(keepends=True), strict=False):
            running += len(line.encode("utf-8"))
            yield dict(raw_row), running
        # Final offset == new_offset; the loop already advanced `running` to it.
```

Note: the `import` lines at the top of the file should be consolidated — keep `from __future__ import annotations` first, then std lib (`csv`, `dataclasses`, `io`, `json`, `from collections.abc import Iterable, Iterator`, `from datetime import datetime, timezone`, `from pathlib import Path`, `from typing import Protocol, runtime_checkable`), then third-party project imports (`from table_peak.training.checkpoint ...`, `from table_peak.training.metrics ...`). Run `uv run ruff format` to autosort.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_run.py -v`

Expected: all tests PASS (12 total: 6 from Task 2 + 8 new).

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy --strict src tests && uv run ruff check src tests && uv run ruff format src tests`

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/training/run.py tests/training/test_run.py
git commit -m "feat(training): add RunStore Port and FileRunStore filesystem adapter"
```

---

## Task 4: Viewer data layer (pure parse functions)

**Files:**
- Create: `src/table_peak/training/viz.py` (data-layer functions only this task)
- Create: `tests/training/test_viz.py`

- [ ] **Step 1: Write failing tests for viewer data layer**

Create `tests/training/test_viz.py`:

```python
"""Tests for the viz data layer (pure parse / classify functions)."""

from __future__ import annotations

from table_peak.training.viz import ColumnSeries, parse_metrics


def test_parse_metrics_classifies_numeric_column() -> None:
    rows = [
        {"step": "1", "loss": "0.5"},
        {"step": "2", "loss": "0.4"},
        {"step": "3", "loss": "0.3"},
    ]
    series = parse_metrics(rows, header=["step", "loss"])
    assert "loss" in series
    s = series["loss"]
    assert s.kind == "numeric"
    assert s.points == [(1, 0.5), (2, 0.4), (3, 0.3)]
    assert s.latest_text is None


def test_parse_metrics_skips_step_column() -> None:
    rows = [{"step": "1", "loss": "0.5"}]
    series = parse_metrics(rows, header=["step", "loss"])
    assert "step" not in series


def test_parse_metrics_handles_sparse_numeric_column() -> None:
    rows = [
        {"step": "1", "loss": "0.5", "eval": ""},
        {"step": "2", "loss": "0.4", "eval": "0.9"},
        {"step": "3", "loss": "0.3", "eval": ""},
        {"step": "4", "loss": "0.2", "eval": "0.95"},
    ]
    series = parse_metrics(rows, header=["step", "loss", "eval"])
    eval_s = series["eval"]
    assert eval_s.kind == "numeric"
    # Empty cells skipped
    assert eval_s.points == [(2, 0.9), (4, 0.95)]


def test_parse_metrics_classifies_text_column_as_text() -> None:
    rows = [
        {"step": "1", "phase": "warmup"},
        {"step": "2", "phase": "main"},
    ]
    series = parse_metrics(rows, header=["step", "phase"])
    s = series["phase"]
    assert s.kind == "text"
    assert s.points == []
    assert s.latest_text == "main"


def test_parse_metrics_text_column_with_empty_cells_uses_last_filled() -> None:
    rows = [
        {"step": "1", "phase": "warmup"},
        {"step": "2", "phase": ""},
        {"step": "3", "phase": "main"},
        {"step": "4", "phase": ""},
    ]
    series = parse_metrics(rows, header=["step", "phase"])
    assert series["phase"].latest_text == "main"


def test_parse_metrics_empty_rows_returns_empty_series_for_each_column() -> None:
    series = parse_metrics([], header=["step", "loss"])
    assert "loss" in series
    s = series["loss"]
    # No data; default to numeric (will simply have no points to plot).
    assert s.kind == "numeric"
    assert s.points == []


def test_columnseries_shape() -> None:
    s = ColumnSeries(name="x", kind="numeric", points=[(1, 0.5)], latest_text=None)
    assert s.name == "x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_viz.py -v`

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the data layer**

Create `src/table_peak/training/viz.py`:

```python
"""Live training-metrics viewer (plotext terminal renderer).

This module has two layers:
  * Pure data layer (`ColumnSeries`, `parse_metrics`) — tested in isolation.
  * Imperative shell (CLI + render loop) — added in Task 5.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ColumnSeries:
    """Parsed series for one CSV column."""

    name: str
    kind: Literal["numeric", "text"]
    points: list[tuple[int, float]] = field(default_factory=list)
    latest_text: str | None = None


def parse_metrics(
    rows: Iterable[dict[str, str]],
    header: list[str],
) -> dict[str, ColumnSeries]:
    """Classify each non-`step` column and aggregate its filled values.

    A column is `numeric` if every non-empty cell parses as float; otherwise
    `text`. Empty cells are always skipped (sparse columns are common — eval
    metrics fire every N steps). Step column is excluded from the output.

    For numeric columns, `points` is the list of (step, value) for filled
    cells. For text columns, `latest_text` holds the last non-empty value.
    """
    rows_list = list(rows)
    series: dict[str, ColumnSeries] = {}
    for col in header:
        if col == "step":
            continue
        # Two-pass: first determine numeric vs text by trying to parse all
        # non-empty cells; second pass extracts filled values.
        non_empty = [r[col] for r in rows_list if r.get(col, "")]
        is_numeric = True
        for v in non_empty:
            try:
                float(v)
            except ValueError:
                is_numeric = False
                break
        if is_numeric:
            points: list[tuple[int, float]] = []
            for r in rows_list:
                cell = r.get(col, "")
                if cell == "":
                    continue
                try:
                    step = int(r["step"])
                except (KeyError, ValueError):
                    continue
                points.append((step, float(cell)))
            series[col] = ColumnSeries(name=col, kind="numeric", points=points)
        else:
            latest = next(
                (r[col] for r in reversed(rows_list) if r.get(col, "")),
                None,
            )
            series[col] = ColumnSeries(name=col, kind="text", latest_text=latest)
    return series
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_viz.py -v`

Expected: all 7 tests PASS.

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy --strict src tests && uv run ruff check src tests && uv run ruff format src tests`

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/training/viz.py tests/training/test_viz.py
git commit -m "feat(training): add viz data layer (ColumnSeries, parse_metrics)"
```

---

## Task 5: Viewer CLI + plotext rendering

**Files:**
- Modify: `src/table_peak/training/viz.py` (add CLI, render loop)
- Create: `src/table_peak/training/__main__.py`-style entry — but plotext viz lives in `viz.py`, invoked via `python -m table_peak.training.viz`
- Modify: `tests/training/test_viz.py` (add CLI / smoke tests)

- [ ] **Step 1: Write failing tests for CLI**

Append to `tests/training/test_viz.py`:

```python
import subprocess
import sys
from pathlib import Path

import pytest

from table_peak.training.run import Run


def _run_viz(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "table_peak.training.viz", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_viz_latest_renders_one_frame_and_exits(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    logger = run.metrics_logger(fields=["loss", "eval"])
    logger.log(step=1, loss=0.5)
    logger.log(step=2, loss=0.4, eval=0.9)
    logger.log(step=3, loss=0.3)
    logger.close()
    proc = _run_viz(["--root", str(tmp_path), "--latest", "--frames", "1"])
    assert proc.returncode == 0, proc.stderr


def test_viz_explicit_run_id(tmp_path: Path) -> None:
    run = Run.create(root=tmp_path)
    logger = run.metrics_logger(fields=["loss"])
    logger.log(step=1, loss=0.5)
    logger.close()
    proc = _run_viz(
        ["--root", str(tmp_path), "--run", run.dir.name, "--frames", "1"]
    )
    assert proc.returncode == 0, proc.stderr


def test_viz_run_not_found(tmp_path: Path) -> None:
    proc = _run_viz(
        ["--root", str(tmp_path), "--run", "does-not-exist", "--frames", "1"]
    )
    assert proc.returncode != 0
    assert "does-not-exist" in (proc.stderr + proc.stdout)


def test_viz_latest_with_no_runs_errors(tmp_path: Path) -> None:
    proc = _run_viz(["--root", str(tmp_path), "--latest", "--frames", "1"])
    assert proc.returncode != 0
    assert "no runs" in (proc.stderr + proc.stdout).lower()


def test_viz_waits_for_header_then_succeeds(tmp_path: Path) -> None:
    # Create a run dir with no CSV yet, write the CSV header (and no rows)
    # before the viewer's wait timeout fires.
    run = Run.create(root=tmp_path)
    logger = run.metrics_logger(fields=["loss"])
    logger.log(step=1, loss=0.1)
    logger.close()
    proc = _run_viz(
        ["--root", str(tmp_path), "--run", run.dir.name, "--frames", "1"]
    )
    assert proc.returncode == 0, proc.stderr
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `uv run pytest tests/training/test_viz.py -v -k "viz_"`

Expected: FAIL — CLI not implemented.

- [ ] **Step 3: Implement CLI + render loop**

Append to `src/table_peak/training/viz.py`:

```python
import argparse
import sys
import time
from pathlib import Path

import plotext as plt

from table_peak.training.run import FileRunStore


_HEADER_WAIT_SECONDS = 10.0


def _resolve_run_id(store: FileRunStore, *, run: str | None, latest: bool) -> str:
    if run is not None:
        runs = set(store.list_runs())
        if run not in runs:
            raise SystemExit(f"viz: run not found: {run}")
        return run
    if latest:
        latest_id = store.latest()
        if latest_id is None:
            raise SystemExit("viz: no runs found in --root")
        return latest_id
    raise SystemExit("viz: must pass either --run RUN_ID or --latest")


def _wait_for_header(store: FileRunStore, run_id: str, *, timeout: float) -> None:
    """Block until at least the CSV header line is flushed, or raise."""
    deadline = time.monotonic() + timeout
    csv_path = store.metrics_path(run_id)
    while time.monotonic() < deadline:
        if csv_path.exists():
            with csv_path.open("rb") as f:
                first = f.readline()
            if first.endswith(b"\n"):
                return
        time.sleep(0.2)
    raise SystemExit(f"viz: timed out waiting for metrics.csv header (run={run_id})")


def _read_header(store: FileRunStore, run_id: str) -> list[str]:
    with store.metrics_path(run_id).open("r") as f:
        header_line = f.readline().rstrip("\n")
    return header_line.split(",")


def _render(series: dict[str, ColumnSeries], run_id: str) -> None:
    plt.clear_terminal()
    plt.clf()
    numeric = {n: s for n, s in series.items() if s.kind == "numeric" and s.points}
    text = {n: s for n, s in series.items() if s.kind == "text"}
    panel_count = max(1, len(numeric))
    plt.subplots(panel_count, 1)
    if not numeric:
        plt.subplot(1, 1)
        plt.title(f"{run_id} — no numeric data yet")
    else:
        for i, (name, s) in enumerate(numeric.items(), start=1):
            plt.subplot(i, 1)
            xs = [p[0] for p in s.points]
            ys = [p[1] for p in s.points]
            plt.plot(xs, ys, marker="dot")
            plt.title(name)
            plt.xlabel("step")
    plt.show()
    if text:
        # Append latest text values below the chart as plain stdout.
        bits = [f"{n}={s.latest_text}" for n, s in text.items() if s.latest_text]
        if bits:
            print("  ".join(bits))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m table_peak.training.viz",
        description="Live training-metrics viewer (plotext)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", type=str, help="explicit run_id under --root")
    group.add_argument("--latest", action="store_true", help="use the most recent run")
    parser.add_argument("--root", type=Path, default=Path("runs"), help="runs dir (default: runs)")
    parser.add_argument(
        "--poll-seconds", type=float, default=1.0, help="poll interval (default: 1.0s)"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=None,
        help="render N frames then exit (test mode); omit for infinite loop",
    )
    args = parser.parse_args(argv)

    store = FileRunStore(root=args.root)
    run_id = _resolve_run_id(store, run=args.run, latest=args.latest)
    _wait_for_header(store, run_id, timeout=_HEADER_WAIT_SECONDS)
    header = _read_header(store, run_id)

    frames_drawn = 0
    try:
        while args.frames is None or frames_drawn < args.frames:
            rows_with_offsets = list(store.iter_rows(run_id, since_byte=0))
            rows = [r for r, _ in rows_with_offsets]
            series = parse_metrics(rows, header=header)
            _render(series, run_id)
            frames_drawn += 1
            if args.frames is not None and frames_drawn >= args.frames:
                break
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all viz tests to verify they pass**

Run: `uv run pytest tests/training/test_viz.py -v`

Expected: all PASS.

- [ ] **Step 5: Manual sanity render**

Run:
```bash
uv run python -c "
from pathlib import Path
from table_peak.training.run import Run
import tempfile, os
d = Path(tempfile.mkdtemp())
r = Run.create(root=d)
log = r.metrics_logger(fields=['policy_loss', 'value_loss', 'non_loss'])
for s in range(1, 21):
    if s % 5 == 0:
        log.log(step=s, policy_loss=1.0/s, value_loss=0.5/s, non_loss=0.5+s/40)
    else:
        log.log(step=s, policy_loss=1.0/s, value_loss=0.5/s)
log.close()
print('root:', d)
print('run :', r.dir.name)
"
# Then run viz manually with --frames 1 against the printed root.
```

This step is optional confirmation; if the previous tests pass, the CLI works.

- [ ] **Step 6: Type-check and lint**

Run: `uv run mypy --strict src tests && uv run ruff check src tests && uv run ruff format src tests`

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/table_peak/training/viz.py tests/training/test_viz.py src/table_peak/training/run.py
git commit -m "feat(training): add viz CLI with plotext rendering and header wait"
```

---

## Task 6: Training entry-point + end-to-end smoke

**Files:**
- Create: `src/table_peak/training/train.py`
- Create: `tests/training/test_train.py`

- [ ] **Step 1: Write failing tests for the training entry-point**

Create `tests/training/test_train.py`:

```python
"""Tests for the training entry-point (train.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from table_peak.training.loop import HParams
from table_peak.training.run import FileRunStore
from table_peak.training.train import run_training


@pytest.fixture
def tiny_hparams() -> HParams:
    return HParams(
        games_per_update=2,
        total_updates=2,
        eval_every=2,
        eval_n_per_pair=2,
        checkpoint_every=10,
    )


def test_run_training_creates_run_dir_with_artifacts(
    tmp_path: Path, tiny_hparams: HParams
) -> None:
    run_dir = run_training(root=tmp_path, name="smoke", hparams=tiny_hparams)
    assert run_dir.exists()
    assert run_dir.parent == tmp_path
    assert (run_dir / "metrics.csv").exists()
    assert (run_dir / "hparams.json").exists()
    assert (run_dir / "checkpoints").exists()


def test_run_training_writes_parseable_hparams(
    tmp_path: Path, tiny_hparams: HParams
) -> None:
    run_dir = run_training(root=tmp_path, name=None, hparams=tiny_hparams)
    payload = json.loads((run_dir / "hparams.json").read_text())
    assert payload["total_updates"] == 2


def test_run_training_metrics_csv_has_rows(
    tmp_path: Path, tiny_hparams: HParams
) -> None:
    run_dir = run_training(root=tmp_path, name=None, hparams=tiny_hparams)
    contents = (run_dir / "metrics.csv").read_text().strip().splitlines()
    # 1 header + 2 update rows
    assert len(contents) >= 3


def test_run_training_runs_resolves_via_FileRunStore(
    tmp_path: Path, tiny_hparams: HParams
) -> None:
    run_dir = run_training(root=tmp_path, name=None, hparams=tiny_hparams)
    store = FileRunStore(root=tmp_path)
    assert run_dir.name in store.list_runs()
    assert store.latest() == run_dir.name


def test_run_training_then_viz_smoke(tmp_path: Path, tiny_hparams: HParams) -> None:
    """End-to-end: train.py produces a dir, viz.py renders one frame from it."""
    run_dir = run_training(root=tmp_path, name=None, hparams=tiny_hparams)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "table_peak.training.viz",
            "--root",
            str(tmp_path),
            "--run",
            run_dir.name,
            "--frames",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/training/test_train.py -v`

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the training entry-point**

Create `src/table_peak/training/train.py`:

```python
"""Production launcher for a training run.

Wires `Run` + default `HParams` + `train()` so a single `python -m
table_peak.training.train` invocation produces a self-contained `runs/<id>/`
dir consumable by `viz.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.loop import HParams, train
from table_peak.training.run import Run


_LOGGED_FIELDS = (
    # Loss components from update_step
    "policy_loss",
    "value_loss",
    "entropy",
    "total_loss",
    # Eval rates
    "non_loss_vs_random",
    "loss_vs_minimax",
)


def run_training(
    *,
    root: Path = Path("runs"),
    name: str | None = None,
    hparams: HParams | None = None,
) -> Path:
    """Run training under a fresh `Run`. Returns the run dir path."""
    hparams = hparams or HParams()
    run = Run.create(root=root, name=name)
    run.write_hparams(hparams)
    metrics = run.metrics_logger(fields=_LOGGED_FIELDS)
    checkpoints = run.checkpoint_store()
    train(
        game=TicTacToe(),
        hparams=hparams,
        checkpoint_store=checkpoints,
        metrics_logger=metrics,
    )
    return run.dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m table_peak.training.train",
        description="Launch a TTT REINFORCE training run with default HParams",
    )
    parser.add_argument("--name", type=str, default=None, help="optional human label")
    parser.add_argument("--root", type=Path, default=Path("runs"), help="runs dir")
    args = parser.parse_args(argv)
    run_dir = run_training(root=args.root, name=args.name)
    print(f"run complete: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Verify the field tuple matches what `loop.train()` actually logs:
- `update_step` returns `policy_loss`, `value_loss`, `entropy`, `total_loss` (check `src/table_peak/training/reinforce.py`'s return type).
- `loop.train()` logs `non_loss_vs_random` and `loss_vs_minimax` on eval steps.

If the names differ, adjust `_LOGGED_FIELDS` to match the runtime keys; `CSVMetricsLogger` will raise on unknown keys.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/training/test_train.py -v`

Expected: all PASS. The whole-file run takes ~10–20 s because of 3-agent eval; under the project's slow budget.

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy --strict src tests && uv run ruff check src tests && uv run ruff format src tests`

Expected: clean.

- [ ] **Step 6: Run the full test suite to catch regressions**

Run: `uv run pytest -q`

Expected: all tests pass (existing + new). The slow-marked smoke training in `test_loop.py` may also run; if it dominates wall-time, restrict with `-m "not slow"` for a quick pre-commit check.

- [ ] **Step 7: Commit**

```bash
git add src/table_peak/training/train.py tests/training/test_train.py
git commit -m "feat(training): add train.py entry-point wiring Run + default HParams"
```

---

## Final verification

- [ ] **Step 1: Confirm full lint and type-check pass**

Run: `uv run mypy --strict src tests && uv run ruff check src tests && uv run ruff format --check src tests`

- [ ] **Step 2: Confirm the full test suite passes**

Run: `uv run pytest -q`

- [ ] **Step 3: Manual end-to-end (optional)**

Two terminals:
```bash
# terminal 1
uv run python -m table_peak.training.train --name dev-smoke
```
```bash
# terminal 2
uv run python -m table_peak.training.viz --latest
```
Verify the viewer redraws as the run progresses, and that Ctrl-C exits cleanly.

- [ ] **Step 4: Branch is ready for merge to main**

The feature ships when:
1. All tests pass.
2. mypy / ruff clean.
3. Optional manual smoke confirmed.

Merge follows the parallel-feature-development Phase 3 routine (rebase onto main, fast-forward, drop the in-flight entry).
