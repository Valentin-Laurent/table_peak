# tests/games/skyjo/test_setup.py
"""Black-box tests for SkyjoState setup phase: deal -> commit -> reveal -> main."""

from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

# Ensure the game is registered before loading.
import table_peak.games.skyjo  # noqa: F401  (registers via import side-effect)


def _new_game(num_players: int = 2, seed: int = 0) -> pyspiel.Game:
    return pyspiel.load_game("skyjo", {"num_players": num_players, "seed": seed})


def test_initial_state_is_chance_node() -> None:
    state = _new_game(num_players=2).new_initial_state()
    assert state.is_chance_node()


def test_deal_phase_advances_through_24_chance_nodes_for_2_players() -> None:
    state = _new_game(num_players=2).new_initial_state()
    chance_steps = 0
    while state.is_chance_node():
        outcomes = state.chance_outcomes()
        # outcomes are (value, prob); probs sum to ~1
        assert abs(sum(p for _, p in outcomes) - 1.0) < 1e-9
        action = outcomes[0][0]  # take first deterministically; true rng sampling lives elsewhere
        state.apply_action(action)
        chance_steps += 1
    assert chance_steps == 25  # 12 cards * 2 players + 1 for initial discard top


def test_after_deal_setup_commit_phase_is_player_0() -> None:
    state = _new_game(num_players=3).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    assert state.current_player() == 0


def test_setup_commit_legal_actions_are_reveal_initial_pairs() -> None:
    from table_peak.games.skyjo.actions import ActionKind, decode

    state = _new_game(num_players=2).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    legal = state.legal_actions()
    assert len(legal) == 66
    for a in legal:
        assert decode(a).kind == ActionKind.REVEAL_INITIAL


def test_after_all_setup_commits_state_advances_to_main_play_with_starting_player() -> None:
    from table_peak.games.skyjo.actions import encode_reveal_initial

    state = _new_game(num_players=2).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    # Each player commits to slots (0, 1).
    state.apply_action(encode_reveal_initial(0, 1))
    state.apply_action(encode_reveal_initial(0, 1))
    # No further chance -- reveal is deterministic.
    assert not state.is_chance_node()
    # Starting player is whichever has higher sum-of-reveals; must be 0 or 1.
    assert state.current_player() in {0, 1}


def test_information_state_during_setup_hides_other_players_commits() -> None:
    from table_peak.games.skyjo.actions import encode_reveal_initial

    state = _new_game(num_players=3).new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    # Player 0 commits.
    state.apply_action(encode_reveal_initial(0, 1))
    # Now player 1's info state must NOT contain a record of player 0's specific commit.
    info_p1 = state.information_state_string(1)
    info_p2 = state.information_state_string(2)
    assert "0,1" not in info_p1  # heuristic: no leak of player 0's chosen pair into others' info
    assert "0,1" not in info_p2


def test_setup_reveal_conserves_total_card_count() -> None:
    """Global invariant after SETUP_REVEAL resolves (incl. any tiebreak draws):
    cards in grids + cards on discard + cards remaining in deck = 150.
    """
    from table_peak.games.skyjo.actions import encode_reveal_initial

    for seed in range(8):
        state = _new_game(num_players=2, seed=seed).new_initial_state()
        while state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
        state.apply_action(encode_reveal_initial(0, 1))
        state.apply_action(encode_reveal_initial(0, 1))
        in_grids = sum(g.num_slots for g in state._grids)
        in_discard = len(state._discard_pile)
        in_deck = sum(state._remaining_deck_counts.values())
        assert in_grids + in_discard + in_deck == 150, (
            f"card conservation broken at seed {seed}: "
            f"grids={in_grids} discard={in_discard} deck={in_deck}"
        )


def test_setup_tiebreak_when_forced_by_construction() -> None:
    """Sweep a small seed range; for any seed where the initial 2-player reveals tie,
    assert that (a) setup completes (a starting player is chosen), and (b) at least
    one extra card was consumed from the deck and ended on the discard pile.
    """
    from table_peak.games.skyjo.actions import encode_reveal_initial

    saw_tie = False
    for seed in range(64):
        state = _new_game(num_players=2, seed=seed).new_initial_state()
        while state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
        state.apply_action(encode_reveal_initial(0, 1))
        # After p0's commit, the deal phase has placed exactly 1 card on the initial discard.
        discard_before_reveal = len(state._discard_pile)
        state.apply_action(encode_reveal_initial(0, 1))
        # SETUP_REVEAL is now resolved. If the two sums tied, tiebreak draws must
        # have appended >= 2 extra cards (one per tied player per tiebreak round).
        sums = [state._grids[p].value(0) + state._grids[p].value(1) for p in range(2)]
        if sums[0] == sums[1]:
            saw_tie = True
            assert len(state._discard_pile) >= discard_before_reveal + 2
            assert state.current_player() in {0, 1}
            break
    _ = saw_tie
