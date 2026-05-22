# src/table_peak/games/skyjo/state.py
"""SkyjoState -- pyspiel.State subclass orchestrating setup, play, scoring."""

from __future__ import annotations

import random
from collections import Counter
from enum import Enum

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.skyjo import actions as skyjo_actions
from table_peak.games.skyjo.deck import DECK_COMPOSITION
from table_peak.games.skyjo.grid import INITIAL_NUM_SLOTS, Grid


class Phase(Enum):
    DEAL = "deal"
    SETUP_COMMIT = "setup_commit"
    MAIN_PLAY = "main_play"
    MAIN_PLAY_DRAW_CHANCE = "main_play_draw_chance"
    BRANCH_B_SUBACTION = "branch_b_subaction"
    ROUND_END = "round_end"
    TERMINAL = "terminal"


class SkyjoState(pyspiel.State):  # type: ignore[misc]
    """Skyjo single-round state. See spec for phase semantics."""

    def __init__(self, game: pyspiel.Game, num_players: int, seed: int):
        super().__init__(game)
        self._num_players: int = num_players
        self._seed: int = seed
        self._rng_tiebreak = random.Random(seed ^ 0xC0FFEE)
        self._phase: Phase = Phase.DEAL

        # Deal-phase state
        self._remaining_deck_counts: Counter[int] = Counter(DECK_COMPOSITION)
        self._deal_index: int = 0
        self._dealt_grids_values: list[list[int]] = [[] for _ in range(num_players)]
        self._discard_pile: list[int] = []
        self._draw_pile: list[int] = []
        self._pending_discard_top: bool = False

        # Setup phase state
        self._grids: list[Grid] | None = None
        self._setup_commits: dict[int, tuple[int, int]] = {}
        self._setup_committer: int = 0
        self._starting_player: int | None = None

        # Main-play state
        self._current_player_index: int = -1
        self._round_ender: int | None = None
        self._final_turns_remaining: dict[int, int] = {}
        self._drawn_card: int | None = None

        # Round-end / scoring
        self._round_scores_post_doubling: dict[int, int] | None = None

    # ---------- pyspiel.State surface ----------

    def current_player(self) -> int:
        if self._phase == Phase.DEAL or self._phase == Phase.MAIN_PLAY_DRAW_CHANCE:
            return int(pyspiel.PlayerId.CHANCE)
        if self._phase == Phase.SETUP_COMMIT:
            return self._setup_committer
        if self._phase == Phase.MAIN_PLAY or self._phase == Phase.BRANCH_B_SUBACTION:
            return self._current_player_index
        if self._phase == Phase.ROUND_END or self._phase == Phase.TERMINAL:
            return int(pyspiel.PlayerId.TERMINAL)
        raise RuntimeError(f"unknown phase {self._phase}")

    def is_terminal(self) -> bool:
        return self._phase == Phase.TERMINAL

    def is_chance_node(self) -> bool:
        return self._phase == Phase.DEAL or self._phase == Phase.MAIN_PLAY_DRAW_CHANCE

    def chance_outcomes(self) -> list[tuple[int, float]]:
        if self._phase == Phase.DEAL or self._phase == Phase.MAIN_PLAY_DRAW_CHANCE:
            total = sum(self._remaining_deck_counts.values())
            return [
                (self._chance_outcome_id(value), count / total)
                for value, count in sorted(self._remaining_deck_counts.items())
                if count > 0
            ]
        return []

    def _legal_actions(self, player: int = -1) -> list[int]:
        if self._phase == Phase.DEAL:
            return [aid for aid, _ in self.chance_outcomes()]
        if self._phase == Phase.SETUP_COMMIT:
            return [
                skyjo_actions.encode_reveal_initial(i, j)
                for i in range(INITIAL_NUM_SLOTS)
                for j in range(i + 1, INITIAL_NUM_SLOTS)
            ]
        if self._phase == Phase.MAIN_PLAY:
            assert self._grids is not None
            result = []
            grid = self._grids[self._current_player_index]
            for slot in range(grid.num_slots):
                result.append(skyjo_actions.encode_take_discard_and_replace(slot))
            result.append(skyjo_actions.encode_draw_deck())
            return sorted(result)
        if self._phase == Phase.BRANCH_B_SUBACTION:
            assert self._grids is not None
            result = []
            grid = self._grids[self._current_player_index]
            for slot in range(grid.num_slots):
                result.append(skyjo_actions.encode_replace_from_hand(slot))
            if grid.num_face_down >= 1:
                for slot in grid.face_down_slots():
                    result.append(skyjo_actions.encode_discard_and_flip(slot))
            return sorted(result)
        return []

    def _apply_action(self, action: int) -> None:
        if self._phase == Phase.DEAL:
            self._apply_deal(action)
            return
        if self._phase == Phase.SETUP_COMMIT:
            self._apply_setup_commit(action)
            return
        if self._phase == Phase.MAIN_PLAY:
            self._apply_main_play(action)
            return
        if self._phase == Phase.MAIN_PLAY_DRAW_CHANCE:
            self._apply_draw_chance(action)
            return
        if self._phase == Phase.BRANCH_B_SUBACTION:
            self._apply_branch_b_sub(action)
            return
        raise RuntimeError(f"_apply_action in unexpected phase {self._phase}")

    def _action_to_string(self, player: int, action: int) -> str:
        if player == int(pyspiel.PlayerId.CHANCE):
            label = "Deal" if self._phase == Phase.DEAL else "Draw"
            return f"{label}(value={self._chance_outcome_value(action)})"
        return skyjo_actions.to_string(action)

    def returns(self) -> list[float]:
        if not self.is_terminal():
            return [0.0] * self._num_players
        assert self._round_scores_post_doubling is not None
        return [float(-self._round_scores_post_doubling[p]) for p in range(self._num_players)]

    def round_scores(self) -> dict[int, int]:
        """Raw integer round scores (post-doubling). Defined only at terminal."""
        if not self.is_terminal():
            raise RuntimeError("round_scores() requires terminal state")
        assert self._round_scores_post_doubling is not None
        return dict(self._round_scores_post_doubling)

    def information_state_string(self, player: int = -1) -> str:
        from table_peak.games.skyjo.observer import SkyjoObserver

        if player < 0:
            player = self._current_player_index if self._current_player_index >= 0 else 0
        return SkyjoObserver(self._num_players).string_from(self, player)

    def information_state_tensor(self, player: int = -1) -> list[float]:
        from table_peak.games.skyjo.observer import SkyjoObserver

        if player < 0:
            player = self._current_player_index if self._current_player_index >= 0 else 0
        obs = SkyjoObserver(self._num_players)
        obs.set_from(self, player)
        return obs.tensor.tolist()

    def __str__(self) -> str:
        """Full god's-eye state string (pyspiel's State::ToString).

        Unlike information_state_string this is allowed to reveal hidden card values;
        it is used for debugging/serialization, not as a player's information set.
        Face-down slots are marked with a trailing '*'.
        """
        lines = [
            f"phase={self._phase.value}",
            f"current_player={self._current_player_index}",
        ]
        if self._grids is not None:
            for p, g in enumerate(self._grids):
                cells = [
                    f"{g.hidden_value(slot)}{'' if g.is_face_up(slot) else '*'}"
                    for slot in range(g.num_slots)
                ]
                lines.append(f"P{p}: [{', '.join(cells)}]")
        else:
            lines.append(f"dealing={self._deal_index}/{12 * self._num_players}")
        lines.append(f"discard_top={self._discard_pile[-1] if self._discard_pile else 'none'}")
        lines.append(f"draw_remaining={sum(self._remaining_deck_counts.values())}")
        if self._drawn_card is not None:
            lines.append(f"drawn={self._drawn_card}")
        if self._round_ender is not None:
            lines.append(f"round_ender={self._round_ender}")
        return "\n".join(lines)

    # ---------- helpers: chance outcome encoding ----------

    @staticmethod
    def _chance_outcome_id(value: int) -> int:
        """Encode a card value (-2..12) as a chance-outcome ID in [0, 15).

        pyspiel requires chance-outcome action IDs to lie in [0, max_chance_outcomes);
        they form a separate namespace from the 103 player actions (disambiguated by
        node context), so overlap with player action IDs is fine.
        """
        return value + 2  # -2 -> 0, ..., 12 -> 14  (range [0, 15))

    @staticmethod
    def _chance_outcome_value(action: int) -> int:
        return action - 2

    # ---------- deal phase ----------

    def _apply_deal(self, action: int) -> None:
        value = self._chance_outcome_value(action)
        if self._remaining_deck_counts[value] <= 0:
            raise ValueError(f"deal value {value} not available in remaining deck")
        self._remaining_deck_counts[value] -= 1
        if self._remaining_deck_counts[value] == 0:
            del self._remaining_deck_counts[value]

        if self._pending_discard_top:
            self._discard_pile = [value]
            self._grids = [Grid.from_dealt(values) for values in self._dealt_grids_values]
            self._draw_pile = []
            self._phase = Phase.SETUP_COMMIT
            self._setup_committer = 0
            return

        player = self._deal_index % self._num_players
        self._dealt_grids_values[player].append(value)
        self._deal_index += 1
        if self._deal_index == 12 * self._num_players:
            self._pending_discard_top = True

    # ---------- setup commit phase ----------

    def _apply_setup_commit(self, action: int) -> None:
        decoded = skyjo_actions.decode(action)
        if decoded.kind != skyjo_actions.ActionKind.REVEAL_INITIAL:
            raise ValueError(f"non-reveal action {action} in SETUP_COMMIT")
        self._setup_commits[self._setup_committer] = (decoded.slot_a, decoded.slot_b)
        self._setup_committer += 1
        if self._setup_committer == self._num_players:
            self._do_synchronous_reveal_and_pick_starter()

    def _do_synchronous_reveal_and_pick_starter(self) -> None:
        assert self._grids is not None
        new_grids: list[Grid] = []
        sums: dict[int, int] = {}
        for p in range(self._num_players):
            i, j = self._setup_commits[p]
            g = self._grids[p].reveal(i).reveal(j)
            new_grids.append(g)
            sums[p] = g.value(i) + g.value(j)
        self._grids = new_grids
        max_sum = max(sums.values())
        tied = [p for p, s in sums.items() if s == max_sum]
        while len(tied) > 1:
            draws: dict[int, int] = {}
            for p in tied:
                card = self._draw_tiebreak_card()
                self._discard_pile.append(card)
                draws[p] = card
            max_draw = max(draws.values())
            tied = [p for p, v in draws.items() if v == max_draw]
        self._starting_player = tied[0]
        self._current_player_index = self._starting_player
        self._phase = Phase.MAIN_PLAY

    def _draw_tiebreak_card(self) -> int:
        """Sample one card from _remaining_deck_counts using _rng_tiebreak."""
        total = sum(self._remaining_deck_counts.values())
        if total == 0:
            self._recycle_discard_into_deck()
            total = sum(self._remaining_deck_counts.values())
            if total == 0:
                raise RuntimeError("deck exhausted with no discard to recycle for tiebreak")
        values = sorted(self._remaining_deck_counts.keys())
        weights = [self._remaining_deck_counts[v] for v in values]
        chosen = self._rng_tiebreak.choices(values, weights=weights, k=1)[0]
        self._remaining_deck_counts[chosen] -= 1
        if self._remaining_deck_counts[chosen] == 0:
            del self._remaining_deck_counts[chosen]
        return chosen

    def _recycle_discard_into_deck(self) -> None:
        """Move discard pile (except top card) back into _remaining_deck_counts."""
        if len(self._discard_pile) <= 1:
            return
        top = self._discard_pile[-1]
        for card in self._discard_pile[:-1]:
            self._remaining_deck_counts[card] += 1
        self._discard_pile = [top]

    # ---------- main play phase ----------

    def _apply_main_play(self, action: int) -> None:
        decoded = skyjo_actions.decode(action)
        p = self._current_player_index
        assert self._grids is not None
        grid = self._grids[p]
        if decoded.kind == skyjo_actions.ActionKind.TAKE_DISCARD_AND_REPLACE:
            new_card = self._discard_pile[-1]
            self._discard_pile.pop()
            new_grid, old_value = grid.replace(decoded.slot, new_card)
            self._discard_pile.append(old_value)
            self._grids[p] = new_grid
            self._post_turn_resolve()
            return
        if decoded.kind == skyjo_actions.ActionKind.DRAW_DECK:
            # Replenish before entering the draw-chance node, so chance_outcomes()
            # (a pure query) is never empty. Cards are conserved across grids +
            # discard + draw pile, so the discard always holds enough to recycle.
            if sum(self._remaining_deck_counts.values()) == 0:
                self._recycle_discard_into_deck()
            self._phase = Phase.MAIN_PLAY_DRAW_CHANCE
            return
        raise ValueError(f"action {action} not legal in MAIN_PLAY")

    def _apply_draw_chance(self, action: int) -> None:
        value = self._chance_outcome_value(action)
        if self._remaining_deck_counts.get(value, 0) <= 0:
            self._recycle_discard_into_deck()
        if self._remaining_deck_counts.get(value, 0) <= 0:
            raise ValueError(f"draw value {value} unavailable after recycle")
        self._remaining_deck_counts[value] -= 1
        if self._remaining_deck_counts[value] == 0:
            del self._remaining_deck_counts[value]
        self._drawn_card = value
        self._phase = Phase.BRANCH_B_SUBACTION

    def _apply_branch_b_sub(self, action: int) -> None:
        decoded = skyjo_actions.decode(action)
        p = self._current_player_index
        assert self._grids is not None
        grid = self._grids[p]
        drawn = self._drawn_card
        assert drawn is not None
        if decoded.kind == skyjo_actions.ActionKind.REPLACE_FROM_HAND:
            new_grid, old_value = grid.replace(decoded.slot, drawn)
            self._discard_pile.append(old_value)
            self._grids[p] = new_grid
            self._drawn_card = None
            self._post_turn_resolve()
            return
        if decoded.kind == skyjo_actions.ActionKind.DISCARD_AND_FLIP:
            if grid.num_face_down < 1:
                raise ValueError("DiscardAndFlip illegal: no face-down slots remain")
            self._discard_pile.append(drawn)
            self._grids[p] = grid.reveal(decoded.slot)
            self._drawn_card = None
            self._post_turn_resolve()
            return
        raise ValueError(f"action {action} not legal in BRANCH_B_SUBACTION")

    def _post_turn_resolve(self) -> None:
        """Column-elimination + round-end trigger + advance turn."""
        p = self._current_player_index
        assert self._grids is not None
        new_grid, eliminated = self._grids[p].try_eliminate_columns()
        self._grids[p] = new_grid
        for _col, value in eliminated:
            self._discard_pile.extend([value, value, value])

        if self._round_ender is None and new_grid.num_face_down == 0:
            # Trigger round-end: every other player gets exactly one final turn.
            self._round_ender = p
            self._final_turns_remaining = {
                other: 1 for other in range(self._num_players) if other != p
            }

        if self._round_ender is not None:
            # Decrement the just-finished player's counter if they are a non-ender.
            if p != self._round_ender:
                self._final_turns_remaining[p] = max(0, self._final_turns_remaining[p] - 1)
            # Have all non-enders taken their final turn?
            if all(v == 0 for v in self._final_turns_remaining.values()):
                self._do_round_end_scoring()
                return

        # Advance to next player (normal play or still in final turns).
        self._current_player_index = (self._current_player_index + 1) % self._num_players
        self._phase = Phase.MAIN_PLAY

    def _do_round_end_scoring(self) -> None:
        """At round-end: flip all remaining face-down cards, sum face-up values per player,
        apply round-ender doubling, store as terminal returns."""
        assert self._round_ender is not None
        assert self._grids is not None
        final_grids: list[Grid] = []
        raw: dict[int, int] = {}
        for p in range(self._num_players):
            g = self._grids[p]
            # Flip all face-down slots face-up. (Eliminated columns already removed.)
            for slot in range(g.num_slots):
                if not g.is_face_up(slot):
                    g = g.reveal(slot)
            # Re-check column elimination after the global flip.
            g, _ = g.try_eliminate_columns()
            final_grids.append(g)
            raw[p] = sum(g.face_up_values().values())
        self._grids = final_grids
        from table_peak.games.skyjo.scoring import compute_round_scores

        self._round_scores_post_doubling = compute_round_scores(raw, round_ender=self._round_ender)
        self._phase = Phase.TERMINAL

    # ---------- placeholders for later tasks ----------

    def clone(self) -> SkyjoState:
        """Deep copy for pyspiel tree expansion.

        copy.deepcopy does NOT work for pybind11-trampoline pyspiel states: the
        C++->Python link is lost, so a later apply_action on the copy mutates a
        throwaway instance rather than the clone (reads look fine, writes vanish).
        Instead we rebuild by replaying the action history through the normal apply
        path, which preserves the trampoline linkage. This is deterministic: the
        deal/draw chance actions are in the history, and the seeded tiebreak RNG is
        re-seeded identically in __init__, so internal draws replay identically.
        """
        fresh: SkyjoState = self.get_game().new_initial_state()
        for action in self.history():
            fresh.apply_action(action)
        return fresh
