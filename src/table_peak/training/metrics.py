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
        self._file: IO[str] = open(self._path, "w", newline="")  # noqa: SIM115
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
