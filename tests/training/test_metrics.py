"""MetricsLogger: append-only CSV logger."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from table_peak.training.metrics import CSVMetricsLogger, MetricsLogger


def test_csv_logger_satisfies_protocol(tmp_path: Path) -> None:
    logger = CSVMetricsLogger(tmp_path / "metrics.csv", fields=["loss"])
    assert isinstance(logger, MetricsLogger)
    logger.close()


def test_log_writes_header_and_rows(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    logger = CSVMetricsLogger(path, fields=["policy_loss", "value_loss"])

    logger.log(step=1, policy_loss=0.5, value_loss=0.2)
    logger.log(step=2, policy_loss=0.4, value_loss=0.15)
    logger.close()

    with open(path) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0] == {"step": "1", "policy_loss": "0.5", "value_loss": "0.2"}
    assert rows[1] == {"step": "2", "policy_loss": "0.4", "value_loss": "0.15"}


def test_log_with_unknown_field_raises(tmp_path: Path) -> None:
    logger = CSVMetricsLogger(tmp_path / "m.csv", fields=["loss"])

    with pytest.raises(ValueError, match="unknown field"):
        logger.log(step=1, loss=0.5, mystery=1.0)

    logger.close()


def test_log_missing_field_writes_empty_string(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    logger = CSVMetricsLogger(path, fields=["a", "b"])

    logger.log(step=1, a=1.0)  # 'b' missing
    logger.close()

    with open(path) as f:
        rows = list(csv.DictReader(f))

    assert rows == [{"step": "1", "a": "1.0", "b": ""}]
