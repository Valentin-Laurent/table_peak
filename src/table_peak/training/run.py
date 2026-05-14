"""Run: producer-side coordinator for a training run dir.

A `Run` owns one directory under `runs/<id>/` and produces the metrics logger
and checkpoint store wired to it. The directory layout is the seam consumed
by `RunStore` (see same module, below — added in Task 3).
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

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
        # Microsecond suffix keeps IDs unique (and lex-chronological) even for
        # runs launched within the same second; second-resolution would collide
        # on mkdir(exist_ok=False).
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S-%f")
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


@runtime_checkable
class RunStore(Protocol):
    """Consumer-side port: list runs and read their metrics rows."""

    def list_runs(self) -> list[str]: ...

    def latest(self) -> str | None: ...

    def iter_rows(self, run_id: str, since_byte: int = 0) -> Iterator[tuple[dict[str, str], int]]:
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

    def iter_rows(self, run_id: str, since_byte: int = 0) -> Iterator[tuple[dict[str, str], int]]:
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
        reader = csv.DictReader(io.StringIO(complete_block), fieldnames=fieldnames)
        # Track per-row offsets so callers can resume mid-stream.
        running = start
        for raw_row, line in zip(reader, complete_block.splitlines(keepends=True), strict=True):
            running += len(line.encode("utf-8"))
            yield dict(raw_row), running
