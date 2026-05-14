"""Tests for the Run producer-side coordinator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from table_peak.training.run import FileRunStore, Run, RunStore


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


def test_filerunstore_implements_protocol(tmp_path: Path) -> None:
    store: RunStore = FileRunStore(root=tmp_path)
    assert isinstance(store, RunStore)


def test_list_runs_returns_chronological_order(tmp_path: Path) -> None:
    # Microsecond-resolution IDs make sequential runs distinct and ordered.
    r1 = Run.create(root=tmp_path, name="first")
    r2 = Run.create(root=tmp_path, name="second")
    r3 = Run.create(root=tmp_path, name="third")
    store = FileRunStore(root=tmp_path)
    ids = store.list_runs()
    assert ids == [r1.dir.name, r2.dir.name, r3.dir.name]


def test_list_runs_empty_root(tmp_path: Path) -> None:
    store = FileRunStore(root=tmp_path)
    assert store.list_runs() == []


def test_latest_returns_last(tmp_path: Path) -> None:
    Run.create(root=tmp_path, name="a")
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
