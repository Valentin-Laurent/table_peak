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


def test_run_training_creates_run_dir_with_artifacts(tmp_path: Path, tiny_hparams: HParams) -> None:
    run_dir = run_training(root=tmp_path, name="smoke", hparams=tiny_hparams)
    assert run_dir.exists()
    assert run_dir.parent == tmp_path
    assert (run_dir / "metrics.csv").exists()
    assert (run_dir / "hparams.json").exists()
    assert (run_dir / "checkpoints").exists()


def test_run_training_writes_parseable_hparams(tmp_path: Path, tiny_hparams: HParams) -> None:
    run_dir = run_training(root=tmp_path, name=None, hparams=tiny_hparams)
    payload = json.loads((run_dir / "hparams.json").read_text())
    assert payload["total_updates"] == 2


def test_run_training_metrics_csv_has_rows(tmp_path: Path, tiny_hparams: HParams) -> None:
    run_dir = run_training(root=tmp_path, name=None, hparams=tiny_hparams)
    contents = (run_dir / "metrics.csv").read_text().strip().splitlines()
    # 1 header + 2 update rows
    assert len(contents) >= 3


def test_run_training_runs_resolves_via_FileRunStore(tmp_path: Path, tiny_hparams: HParams) -> None:
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
