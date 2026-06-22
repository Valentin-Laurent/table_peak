from __future__ import annotations

import random

import pyspiel  # type: ignore[import-not-found]

import table_peak.games.quoridor  # noqa: F401  (registers the game)
from table_peak.agents.random import RandomAgent
from table_peak.games.quoridor import QuoridorGameWrapper
from table_peak.games.quoridor.actions import NUM_DISTINCT_ACTIONS, encode_move, encode_wall
from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor
from table_peak.runner.play import play_game, play_matches


def test_clone_is_independent_of_original() -> None:
    # Regression guard: the adapter calls inner.clone() on every apply_action,
    # and deepcopy silently breaks pyspiel trampoline states. A move on the clone
    # must not leak back into the original.
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    clone = state.clone()
    clone.apply_action(encode_move(Cell(col=4, row=1)))
    assert state.current_player() == 0
    assert encode_move(Cell(col=4, row=1)) in set(state.legal_actions())


def test_play_game_drives_the_wrapped_game_through_the_runner() -> None:
    # Integration smoke: the registered engine plugs into the real runner +
    # random agents through the Game/State protocol and yields well-formed
    # output. max_moves caps the (otherwise long) random playout -- reaching a
    # natural terminal is covered by test_state's straight-race test, not here.
    game = QuoridorGameWrapper(seed=0)
    agents = {0: RandomAgent(rng=random.Random(0)), 1: RandomAgent(rng=random.Random(1))}
    outcome = play_game(game, agents, max_moves=40)
    assert outcome.num_moves > 0
    assert set(outcome.returns.keys()) == {0, 1}


def test_play_matches_is_reproducible_with_seeded_agents() -> None:
    # Reproducibility of the seeded play path: same seeds -> identical stats.
    # Bounded by max_moves; determinism does not depend on games terminating.
    def run() -> object:
        return play_matches(
            QuoridorGameWrapper(seed=0),
            agent_a=RandomAgent(rng=random.Random(10)),
            agent_b=RandomAgent(rng=random.Random(20)),
            n=2,
            swap_sides=True,
            seed=99,
            max_moves=15,
        )

    assert run() == run()


def test_registration_overrides_pyspiel_builtin() -> None:
    # pyspiel ships a builtin "quoridor"; our register_game must shadow it.
    # If a future pyspiel changes registration semantics so the builtin wins,
    # this fails loudly instead of silently loading a different game.
    game = pyspiel.load_game("quoridor", {"seed": 0})
    assert game.num_distinct_actions() == NUM_DISTINCT_ACTIONS


def test_is_legal_matches_full_enumeration() -> None:
    # Locks the load-bearing optimization: _apply_action validates via the
    # single-action _is_legal(), which must agree with membership in the full
    # _legal_actions() set for EVERY action id -- moves and walls alike.
    game = pyspiel.load_game("quoridor", {"seed": 0})
    state = game.new_initial_state()
    # Reach a non-trivial state: one pawn move, then place a wall (exercises
    # both the move and wall branches of _is_legal at the checked states).
    for action in (
        encode_move(Cell(col=4, row=1)),
        encode_wall(WallAnchor(col=0, row=0), Orientation.HORIZONTAL),
        encode_move(Cell(col=4, row=2)),
    ):
        legal = set(state.legal_actions())
        for candidate in range(NUM_DISTINCT_ACTIONS):
            assert state._is_legal(candidate) == (candidate in legal)
        state.apply_action(action)
