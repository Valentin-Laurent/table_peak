"""NFSP and DQN training cells for the Skyjo feasibility spike."""

from __future__ import annotations

from typing import Any

from open_spiel.python import rl_environment
from open_spiel.python.pytorch import dqn, nfsp

from spikes.evaluation import evaluate
from spikes.payoff import PayoffMode, zero_sum_returns

HIDDEN_LAYERS = [128, 128]
NUM_TRAIN_EPISODES = 2000  # short directional budget
NUM_EVAL_GAMES = 400


def _zero_sum_terminal(time_step: Any, mode: PayoffMode) -> Any:
    """Return a copy of a terminal TimeStep with zero-sum rewards."""
    zs = zero_sum_returns(time_step.rewards, mode)
    return time_step._replace(rewards=zs)


def _train(agents: list[Any], game: Any, mode: PayoffMode) -> None:
    env = rl_environment.Environment(game)
    for _ in range(NUM_TRAIN_EPISODES):
        time_step = env.reset()
        while not time_step.last():
            pid = time_step.observations["current_player"]
            agent_output = agents[pid].step(time_step)
            time_step = env.step([agent_output.action])
        final = _zero_sum_terminal(time_step, mode)
        for agent in agents:
            agent.step(final)


def _make_specs(game: Any) -> tuple[int, int]:
    env = rl_environment.Environment(game)
    state_size = env.observation_spec()["info_state"][0]
    num_actions = env.action_spec()["num_actions"]
    return state_size, num_actions


def run_nfsp_cell(game: Any, mode: PayoffMode) -> dict[str, float]:
    state_size, num_actions = _make_specs(game)
    agents = [
        nfsp.NFSP(
            player_id=p,
            state_representation_size=state_size,
            num_actions=num_actions,
            hidden_layers_sizes=HIDDEN_LAYERS,
            reservoir_buffer_capacity=int(2e5),
            anticipatory_param=0.1,
        )
        for p in range(2)
    ]
    _train(agents, game, mode)
    return evaluate(game, agents[0], NUM_EVAL_GAMES)


def run_dqn_cell(game: Any, mode: PayoffMode) -> dict[str, float]:
    state_size, num_actions = _make_specs(game)
    agents = [
        dqn.DQN(
            player_id=p,
            state_representation_size=state_size,
            num_actions=num_actions,
            hidden_layers_sizes=HIDDEN_LAYERS,
            replay_buffer_capacity=int(1e5),
            batch_size=128,
        )
        for p in range(2)
    ]
    _train(agents, game, mode)
    return evaluate(game, agents[0], NUM_EVAL_GAMES)
