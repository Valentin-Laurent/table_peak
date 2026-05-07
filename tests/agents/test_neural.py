"""NeuralAgent: inference-only Agent backed by a PolicyValueNet + Encoder."""

from __future__ import annotations

import random

import torch

from table_peak.agents.base import Agent
from table_peak.agents.neural import NeuralAgent
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.runner.play import play_game
from table_peak.training.encoder import TTTEncoder
from table_peak.training.policy_net import PolicyValueNet


def _make_agent(*, temperature: float = 0.0, seed: int = 0) -> NeuralAgent:
    torch.manual_seed(seed)
    net = PolicyValueNet()
    return NeuralAgent(
        net=net, encoder=TTTEncoder(), temperature=temperature, rng=random.Random(seed)
    )


def test_neural_agent_satisfies_agent_protocol() -> None:
    assert isinstance(_make_agent(), Agent)


def test_act_returns_legal_action_on_initial_state() -> None:
    agent = _make_agent()
    state = TicTacToe().new_initial_state()

    action = agent.act(state)

    assert action in state.legal_actions()


def test_greedy_act_is_deterministic_for_same_state() -> None:
    agent = _make_agent(temperature=0.0)
    state = TicTacToe().new_initial_state()

    actions = {agent.act(state) for _ in range(5)}

    assert len(actions) == 1


def test_act_respects_legal_mask_late_game() -> None:
    agent = _make_agent()
    state = TicTacToe().new_initial_state()
    # Fill cells 0..6, both players alternate.
    for i in range(7):
        state = state.apply_action(i)
    # Legal actions remaining: 7, 8.
    assert state.legal_actions() == (7, 8)

    action = agent.act(state)

    assert action in (7, 8)


def test_neural_agent_plays_complete_game_against_random() -> None:
    agent = _make_agent()
    rng = random.Random(0)
    from table_peak.agents.random import RandomAgent

    outcome = play_game(TicTacToe(), {0: agent, 1: RandomAgent(rng)})

    assert outcome.num_moves >= 5
    assert outcome.num_moves <= 9


def test_sampling_mode_can_produce_multiple_actions() -> None:
    # With temperature=1.0 and 100 samples on the empty board, expect at least
    # two distinct chosen actions (extremely unlikely to be all the same).
    agent = _make_agent(temperature=1.0, seed=42)
    state = TicTacToe().new_initial_state()

    actions = {agent.act(state) for _ in range(100)}

    assert len(actions) >= 2
