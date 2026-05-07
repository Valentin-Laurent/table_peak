"""HParams + top-level train() orchestration for REINFORCE self-play."""

from __future__ import annotations

import random
from dataclasses import dataclass

import torch

from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.neural import NeuralAgent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import Game
from table_peak.training.buffer import TrajectoryBuffer
from table_peak.training.checkpoint import CheckpointStore
from table_peak.training.encoder import TTTEncoder
from table_peak.training.eval import cross_table
from table_peak.training.metrics import MetricsLogger
from table_peak.training.policy_net import PolicyValueNet
from table_peak.training.reinforce import update_step
from table_peak.training.self_play import SelfOpponentSampler, generate_episode


@dataclass(frozen=True, slots=True)
class HParams:
    """Hyperparameters for v2 REINFORCE-with-baseline self-play training.

    Defaults are tuned for the <5-minute CPU smoke-test budget on TTT.

    ``random_opponent_fraction`` controls a mixed-opponent strategy: pure
    self-play was found to cycle (the agent oscillates around ~70% non-loss vs
    Random) because gradient updates from symmetric self-games provide no
    stable signal. Mixing in RandomAgent games (with opponent samples filtered
    out of the buffer) breaks the cycle and drives convergence to ≥95%.
    """

    games_per_update: int = 64
    total_updates: int = 4000
    lr: float = 1e-3
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    train_temperature: float = 1.0
    random_opponent_fraction: float = 0.7
    eval_every: int = 200
    eval_n_per_pair: int = 100
    checkpoint_every: int = 250
    seed: int = 42


def train(
    *,
    game: Game,
    hparams: HParams,
    checkpoint_store: CheckpointStore,
    metrics_logger: MetricsLogger,
) -> NeuralAgent:
    """Self-play REINFORCE-with-baseline. Returns the final greedy NeuralAgent."""
    torch.manual_seed(hparams.seed)
    rng = random.Random(hparams.seed)

    encoder = TTTEncoder()
    net = PolicyValueNet()
    optimizer = torch.optim.Adam(net.parameters(), lr=hparams.lr)

    train_agent = NeuralAgent(
        net=net, encoder=encoder, temperature=hparams.train_temperature, rng=rng
    )
    sampler = SelfOpponentSampler(train_agent)
    random_opponent = RandomAgent(random.Random(hparams.seed + 2))

    eval_random_agent = RandomAgent(random.Random(hparams.seed + 1))
    eval_minimax_agent = MinimaxAgent()  # reused across evals; cache persists

    for update in range(1, hparams.total_updates + 1):
        buf = TrajectoryBuffer()
        for _ in range(hparams.games_per_update):
            use_random = rng.random() < hparams.random_opponent_fraction
            opponent = random_opponent if use_random else sampler.sample()
            # Alternate train agent between P0 and P1 so it learns both sides.
            train_as_p0 = rng.random() < 0.5
            if train_as_p0:
                episode = generate_episode(game, agent_p0=train_agent, agent_p1=opponent)
                train_player = 0
            else:
                episode = generate_episode(game, agent_p0=opponent, agent_p1=train_agent)
                train_player = 1
            if use_random:
                # When opponent is non-neural, only train on the neural agent's moves.
                # Opponent's random actions would add noise to the gradient.
                episode = [s for s in episode if s.state.current_player == train_player]
            buf.add(episode)

        loss_metrics = update_step(
            net,
            optimizer,
            buf,
            encoder=encoder,
            value_coef=hparams.value_coef,
            entropy_coef=hparams.entropy_coef,
        )

        is_eval_step = update % hparams.eval_every == 0 or update == hparams.total_updates
        if is_eval_step:
            greedy_agent = NeuralAgent(net=net, encoder=encoder, temperature=0.0)
            table = cross_table(
                [
                    ("trained", greedy_agent),
                    ("random", eval_random_agent),
                    ("minimax", eval_minimax_agent),
                ],
                game=game,
                n_per_pair=hparams.eval_n_per_pair,
                seed=hparams.seed + update,
            )
            vs_random = table[("trained", "random")]
            vs_minimax = table[("trained", "minimax")]
            non_loss = (vs_random.wins[0] + vs_random.draws) / vs_random.n_games
            loss_vs_minimax = vs_minimax.wins[1] / vs_minimax.n_games
            metrics_logger.log(
                step=update,
                **loss_metrics,
                non_loss_vs_random=non_loss,
                loss_vs_minimax=loss_vs_minimax,
            )
        else:
            metrics_logger.log(step=update, **loss_metrics)

        if update % hparams.checkpoint_every == 0 and update < hparams.total_updates:
            checkpoint_store.save(gen=update, net=net, optimizer=optimizer, step=update)

    checkpoint_store.save(
        gen=hparams.total_updates,
        net=net,
        optimizer=optimizer,
        step=hparams.total_updates,
    )
    metrics_logger.close()
    return NeuralAgent(net=net, encoder=encoder, temperature=0.0)
