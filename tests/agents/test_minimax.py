"""Behavioural tests for MinimaxAgent on TicTacToe."""

from __future__ import annotations

from table_peak.agents.minimax import MinimaxAgent
from table_peak.games.tic_tac_toe import TicTacToe, TicTacToeState


def _state_from_moves(moves: list[int]) -> TicTacToeState:
    state = TicTacToe().new_initial_state()
    for m in moves:
        state = state.apply_action(m)
    return state


def test_acts_within_legal_actions_from_initial_state() -> None:
    agent = MinimaxAgent()
    state = TicTacToe().new_initial_state()
    action = agent.act(state)
    assert action in state.legal_actions()


def test_takes_winning_move_when_one_step_from_win() -> None:
    # P0 has cells 0, 1; cell 2 wins immediately. P0 to move.
    # Moves: P0:0, P1:3, P0:1, P1:4 -> P0 to move, plays 2 to win.
    agent = MinimaxAgent()
    state = _state_from_moves([0, 3, 1, 4])
    assert state.current_player == 0
    assert agent.act(state) == 2


def test_blocks_opponents_imminent_win() -> None:
    # P1 threatens to win on cell 2. P0 must block with 2.
    # Moves: P0:4, P1:0, P0:8, P1:1 -> P0 to move, must play 2.
    agent = MinimaxAgent()
    state = _state_from_moves([4, 0, 8, 1])
    assert state.current_player == 0
    assert agent.act(state) == 2


def test_caches_across_calls() -> None:
    """The agent's cache is populated; a second act() on same state hits the cache."""
    agent = MinimaxAgent()
    state = TicTacToe().new_initial_state()
    agent.act(state)
    cache_size_after_first = len(agent._cache)
    agent.act(state)
    cache_size_after_second = len(agent._cache)
    assert cache_size_after_first > 0
    assert cache_size_after_second == cache_size_after_first
