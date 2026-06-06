"""Black-box tests for the generic pyspiel adapter."""

from __future__ import annotations

import random

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.skyjo  # noqa: F401
from table_peak.games._pyspiel_adapter import PyspielGameAdapter


def _game(seed: int = 0) -> PyspielGameAdapter:
    inner = pyspiel.load_game("skyjo", {"num_players": 2, "seed": seed})
    return PyspielGameAdapter(inner, seed=seed)


def test_adapter_exposes_protocol_surface() -> None:
    game = _game()
    assert game.num_players == 2
    state = game.new_initial_state()
    # Chance was auto-resolved during new_initial_state.
    assert state.current_player >= 0
    assert state.is_terminal is False
    assert len(state.legal_actions()) > 0


def test_apply_action_returns_new_state_and_resolves_subsequent_chance() -> None:
    game = _game()
    state = game.new_initial_state()
    legal = state.legal_actions()
    s2 = state.apply_action(legal[0])
    assert s2.current_player >= 0 or s2.is_terminal


def test_apply_action_does_not_mutate_caller() -> None:
    game = _game()
    state = game.new_initial_state()
    legal_before = state.legal_actions()
    state.apply_action(legal_before[0])
    # state itself unchanged (immutable view)
    assert state.legal_actions() == legal_before


def test_terminal_returns_dict_per_player() -> None:
    game = _game()
    state = game.new_initial_state()
    rng = random.Random(0)
    while not state.is_terminal:
        state = state.apply_action(rng.choice(state.legal_actions()))
    rs = state.returns()
    assert isinstance(rs, dict)
    assert set(rs.keys()) == {0, 1}
    assert all(isinstance(v, float) for v in rs.values())


def test_inner_exposes_underlying_python_state() -> None:
    """The adapter exposes the wrapped pyspiel state so renderers can read a
    game-specific public view. Reading a Python-defined attribute through
    `.inner` must work (the wrapped object is the Python State subclass)."""
    from table_peak.games.skyjo import SkyjoGameWrapper

    game = SkyjoGameWrapper(num_players=2, seed=7)
    state = game.new_initial_state()
    inner = state.inner
    # `_num_players` is a Python attribute on SkyjoState — proves we hold the
    # Python instance, not a bare C++ view.
    assert inner._num_players == 2
