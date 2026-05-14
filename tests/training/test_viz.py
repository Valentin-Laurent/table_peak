"""Tests for the viz data layer (pure parse / classify functions)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from table_peak.training.run import Run
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
    proc = _run_viz(["--root", str(tmp_path), "--run", run.dir.name, "--frames", "1"])
    assert proc.returncode == 0, proc.stderr


def test_viz_run_not_found(tmp_path: Path) -> None:
    proc = _run_viz(["--root", str(tmp_path), "--run", "does-not-exist", "--frames", "1"])
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
    proc = _run_viz(["--root", str(tmp_path), "--run", run.dir.name, "--frames", "1"])
    assert proc.returncode == 0, proc.stderr
