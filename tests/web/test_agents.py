"""Tests for the web-layer agent registry."""

from __future__ import annotations

from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.web.agents import AGENT_REGISTRY


def test_registry_contains_random_and_minimax() -> None:
    assert set(AGENT_REGISTRY.keys()) == {"Random", "Minimax"}


def test_registry_does_not_contain_human() -> None:
    """`Human` is mapped to `None` by the route handler, not the registry."""
    assert "Human" not in AGENT_REGISTRY


def test_factories_produce_working_agents() -> None:
    """Each factory returns a fresh Agent that picks a legal action."""
    state = TicTacToe().new_initial_state()
    for name, factory in AGENT_REGISTRY.items():
        agent = factory()
        assert agent.act(state) in state.legal_actions(), (
            f"{name} factory produced an agent that played an illegal action"
        )


def test_factories_produce_independent_instances() -> None:
    """Calling the factory twice returns two distinct agents."""
    for factory in AGENT_REGISTRY.values():
        a = factory()
        b = factory()
        assert a is not b
