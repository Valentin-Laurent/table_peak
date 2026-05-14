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
    "mean_return",
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
