"""train(): full self-play REINFORCE loop. The smoke test is the v2 spine."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.neural import NeuralAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import play_matches
from table_peak.training.checkpoint import FileCheckpointStore
from table_peak.training.loop import HParams, train
from table_peak.training.metrics import CSVMetricsLogger


def test_hparams_defaults_are_set() -> None:
    hp = HParams()
    assert hp.games_per_update >= 1
    assert hp.total_updates >= 1
    assert hp.lr > 0


def test_train_runs_and_writes_checkpoints_and_metrics(tmp_path: Path) -> None:
    """Tiny budget — verifies orchestration wires everything correctly."""
    hp = HParams(
        games_per_update=4,
        total_updates=3,
        eval_every=2,
        eval_n_per_pair=4,  # keep this non-slow test quick
        checkpoint_every=2,
        seed=42,
    )
    ckpt = FileCheckpointStore(tmp_path / "ckpt")
    metrics = CSVMetricsLogger(
        tmp_path / "m.csv",
        fields=[
            "policy_loss",
            "value_loss",
            "entropy",
            "mean_return",
            "non_loss_vs_random",
            "loss_vs_minimax",
        ],
    )

    agent = train(
        game=TicTacToe(),
        hparams=hp,
        checkpoint_store=ckpt,
        metrics_logger=metrics,
    )

    assert isinstance(agent, NeuralAgent)
    # At least one mid-run checkpoint plus the final one.
    assert len(ckpt.list_generations()) >= 1
    assert (tmp_path / "m.csv").exists()


@pytest.mark.slow
def test_smoke_training_meets_v2_success_criteria(tmp_path: Path) -> None:
    """End-to-end smoke. Must complete in <5 min CPU and meet criteria 1+2.

    Criterion 1: trained agent achieves >=95% non-loss vs Random over 500 games.
    Criterion 2: trained agent has <=5% loss vs Minimax over 200 games AND zero wins.
    """
    hp = HParams()  # production defaults — tuned to fit the 5-min budget
    ckpt = FileCheckpointStore(tmp_path / "ckpt")
    metrics = CSVMetricsLogger(
        tmp_path / "m.csv",
        fields=[
            "policy_loss",
            "value_loss",
            "entropy",
            "mean_return",
            "non_loss_vs_random",
            "loss_vs_minimax",
        ],
    )

    trained = train(
        game=TicTacToe(),
        hparams=hp,
        checkpoint_store=ckpt,
        metrics_logger=metrics,
    )
    # train() returns a greedy NeuralAgent (temperature=0); use directly.

    # Criterion 1: >=95% non-loss vs Random.
    vs_random = play_matches(
        game=TicTacToe(),
        agent_a=trained,
        agent_b=RandomAgent(random.Random(0)),
        n=500,
        swap_sides=True,
        seed=0,
    )
    non_loss_rate = (vs_random.wins[0] + vs_random.draws) / vs_random.n_games
    assert non_loss_rate >= 0.95, f"non-loss vs Random was {non_loss_rate:.3f}"

    # Criterion 2: <=5% loss AND zero wins vs Minimax.
    vs_minimax = play_matches(
        game=TicTacToe(),
        agent_a=trained,
        agent_b=MinimaxAgent(),
        n=200,
        swap_sides=True,
        seed=0,
    )
    loss_rate = vs_minimax.wins[1] / vs_minimax.n_games
    win_count = vs_minimax.wins[0]
    assert win_count == 0, f"NeuralAgent beat Minimax {win_count} times — minimax bug"
    assert loss_rate <= 0.05, f"loss vs Minimax was {loss_rate:.3f}"
