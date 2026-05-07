"""Self-play episode generation and opponent-sampling Port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from table_peak.agents.base import Agent
from table_peak.games.base import Action, Game, State
from table_peak.training.buffer import Episode, Sample


@runtime_checkable
class OpponentSampler(Protocol):
    """Port: provides the opponent agent for a given training game."""

    def sample(self) -> Agent: ...


class SelfOpponentSampler:
    """Default sampler: always returns the same (currently-training) agent."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def sample(self) -> Agent:
        return self._agent


def generate_episode(game: Game, agent_p0: Agent, agent_p1: Agent) -> Episode:
    """Play one full game; return per-player samples with terminal returns.

    Each step's `ret` is the terminal return for the player who acted at that
    step. This is the form REINFORCE consumes (Monte Carlo return, no
    discount, no bootstrap).

    Note: samples are grouped by player (all P0 steps, then all P1 steps), not
    interleaved chronologically. This is harmless for REINFORCE (each sample is
    an independent (s, a, r) triple), but consumers that need temporal order
    must reconstruct it from `state.current_player` or by re-playing.
    """
    state = game.new_initial_state()
    pending_p0: list[tuple[State, Action]] = []
    pending_p1: list[tuple[State, Action]] = []

    while not state.is_terminal:
        player = state.current_player
        actor = agent_p0 if player == 0 else agent_p1
        action = actor.act(state)
        if player == 0:
            pending_p0.append((state, action))
        else:
            pending_p1.append((state, action))
        state = state.apply_action(action)

    returns = state.returns()
    episode: Episode = []
    for s, a in pending_p0:
        episode.append(Sample(state=s, action=a, ret=returns[0]))
    for s, a in pending_p1:
        episode.append(Sample(state=s, action=a, ret=returns[1]))
    return episode
