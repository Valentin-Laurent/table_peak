"""Seat-balanced evaluation of a trained agent vs a uniform-random opponent."""

from __future__ import annotations

import random
from typing import Any

import numpy as np
from open_spiel.python import rl_environment


def aggregate_results(games: list[tuple[float, float]]) -> dict[str, float]:
    """games: list of (my_raw_return, opp_raw_return). Higher return == better."""
    wins = sum(1.0 if me > opp else 0.5 if me == opp else 0.0 for me, opp in games)
    margins = [me - opp for me, opp in games]
    return {
        "win_rate": wins / len(games),
        "mean_margin": float(np.mean(margins)),
        "n_games": float(len(games)),
    }


def evaluate(game: Any, agents: list[Any], n_games: int, seed: int = 0) -> dict[str, float]:
    """Eval the self-play agents vs a uniform-random opponent, balanced across seats.

    `agents` is indexed by player_id. On the agent's turn we use `agents[pid]`
    (whose `player_id == pid`), so the agent always reads the legal-action mask for
    the seat it is actually playing. The other seat plays uniformly at random.
    """
    env = rl_environment.Environment(game)
    rng = random.Random(seed)
    results: list[tuple[float, float]] = []
    for g in range(n_games):
        agent_seat = g % 2  # alternate seats for balance
        time_step = env.reset()
        while not time_step.last():
            pid = time_step.observations["current_player"]
            if pid == agent_seat:
                action = agents[pid].step(time_step, is_evaluation=True).action
            else:
                legal = time_step.observations["legal_actions"][pid]
                action = rng.choice(legal)
            time_step = env.step([action])
        rewards = time_step.rewards  # raw Skyjo returns at terminal
        results.append((rewards[agent_seat], rewards[1 - agent_seat]))
    return aggregate_results(results)


def measure_episode_lengths(game: Any, n_games: int, seed: int = 0) -> dict[str, float]:
    """Random-vs-random episode lengths, to confirm games end under the 2000 cap."""
    env = rl_environment.Environment(game)
    rng = random.Random(seed)
    lengths: list[int] = []
    for _ in range(n_games):
        time_step = env.reset()
        steps = 0
        while not time_step.last():
            pid = time_step.observations["current_player"]
            legal = time_step.observations["legal_actions"][pid]
            time_step = env.step([rng.choice(legal)])
            steps += 1
        lengths.append(steps)
    return {"median": float(np.median(lengths)), "max": float(np.max(lengths))}
