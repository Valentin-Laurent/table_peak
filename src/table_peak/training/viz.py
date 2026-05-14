"""Live training-metrics viewer (plotext terminal renderer).

This module has two layers:
  * Pure data layer (`ColumnSeries`, `parse_metrics`) — tested in isolation.
  * Imperative shell (CLI + render loop) — added in Task 5.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import plotext as plt

from table_peak.training.run import FileRunStore


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
    rows: list[dict[str, str]] = []
    offset = 0
    try:
        while args.frames is None or frames_drawn < args.frames:
            # Read only newly-appended rows each poll; the full curve is kept
            # in `rows` so the chart still shows history.
            for row, new_offset in store.iter_rows(run_id, since_byte=offset):
                rows.append(row)
                offset = new_offset
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
