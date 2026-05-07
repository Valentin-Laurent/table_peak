"""Self-play episode generation + OpponentSampler Port."""

from __future__ import annotations

import random

from table_peak.agents.random import RandomAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.training.self_play import (
    OpponentSampler,
    SelfOpponentSampler,
    generate_episode,
)


def test_self_opponent_sampler_returns_configured_agent() -> None:
    agent = RandomAgent(random.Random(0))
    sampler = SelfOpponentSampler(agent)

    assert sampler.sample() is agent


def test_self_opponent_sampler_satisfies_protocol() -> None:
    sampler = SelfOpponentSampler(RandomAgent(random.Random(0)))
    assert isinstance(sampler, OpponentSampler)


def test_generate_episode_terminates_with_legal_play() -> None:
    a0 = RandomAgent(random.Random(1))
    a1 = RandomAgent(random.Random(2))

    episode = generate_episode(TicTacToe(), agent_p0=a0, agent_p1=a1)

    assert 5 <= len(episode) <= 9
    for sample in episode:
        assert sample.action in sample.state.legal_actions()


def test_generate_episode_returns_zero_sum_for_ttt() -> None:
    a0 = RandomAgent(random.Random(1))
    a1 = RandomAgent(random.Random(2))

    episode = generate_episode(TicTacToe(), agent_p0=a0, agent_p1=a1)

    # In TTT the per-step return assigned to a sample is the player's terminal
    # return. Across the whole episode, P0's and P1's returns sum to 0.
    by_player_returns: dict[int, set[float]] = {0: set(), 1: set()}
    for sample in episode:
        by_player_returns[sample.state.current_player].add(sample.ret)
    # Each player has exactly one terminal return assigned to all their steps.
    assert all(len(v) == 1 for v in by_player_returns.values())
    p0_ret = next(iter(by_player_returns[0]))
    p1_ret = next(iter(by_player_returns[1]))
    assert p0_ret + p1_ret == 0.0


def test_generate_episode_attributes_returns_per_player_perspective() -> None:
    """Force a P0 win with scripted agents to verify per-player return assignment."""
    from table_peak.games.base import Action, State

    class ScriptedAgent:  # test-only stateful fixture; violates the Agent Protocol's purity rule
        def __init__(self, moves: list[Action]) -> None:
            self._moves = list(moves)

        def act(self, state: State) -> Action:
            return self._moves.pop(0)

    # P0: 0, 1, 2  (top row). P1: 3, 4 (interleaved).
    # Sequence: P0 -> 0; P1 -> 3; P0 -> 1; P1 -> 4; P0 -> 2 -> WIN
    p0 = ScriptedAgent([0, 1, 2])
    p1 = ScriptedAgent([3, 4])

    episode = generate_episode(TicTacToe(), agent_p0=p0, agent_p1=p1)

    p0_returns = {s.ret for s in episode if s.state.current_player == 0}
    p1_returns = {s.ret for s in episode if s.state.current_player == 1}
    assert p0_returns == {1.0}
    assert p1_returns == {-1.0}
