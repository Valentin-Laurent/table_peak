"""SkyjoObserver — information state / observation encoding (string + tensor).

Implements pyspiel's observer duck-type: ``set_from(state, player)``,
``string_from(state, player)``, plus ``tensor`` (np.ndarray) and ``dict`` attributes.

Privacy model (Skyjo): a card's value is public iff it is face-up. No player — not
even the owner — sees a face-down card's value. The only private transient is the
freshly drawn deck card during a Branch-(b) sub-action, visible only to the player
who drew it.

KNOWN LIMITATION (perfect recall): this encoding is markovian — it captures only the
current board, not the action history. Distinct play histories reaching the same board
alias to the same information_state, which violates perfect recall. That is fine for
the engine's success criteria, but a history-aware (perfect-recall) info state will be
required before running CFR/NFSP on Skyjo. The tensor SHAPE is part of the public
surface, so extending it later is a breaking change for any saved checkpoints.

Tensor layout (float32):
  per player: 12 slots x 3 floats (is_face_up, value, is_eliminated) = 36
  globals (10): discard_top, draw_pile_normalized, drawn_card, drawn_visible,
                round_ender (-1 sentinel if none), phase one-hot (5)
  total = 36 * num_players + 10
"""

from __future__ import annotations

from typing import Any

import numpy as np

_NUM_SLOTS = 12
_FLOATS_PER_SLOT = 3  # is_face_up, value, is_eliminated
_PER_PLAYER = _NUM_SLOTS * _FLOATS_PER_SLOT  # 36
_NUM_GLOBALS = 10


def tensor_size(num_players: int) -> int:
    return _PER_PLAYER * num_players + _NUM_GLOBALS


class SkyjoObserver:
    def __init__(self, num_players: int):
        self._num_players = num_players
        self._size = tensor_size(num_players)
        self.tensor = np.zeros(self._size, dtype=np.float32)
        self.dict = {"observation": self.tensor}

    def set_from(self, state: Any, player: int) -> None:
        from table_peak.games.skyjo.state import Phase

        self.tensor.fill(0.0)
        grids = state._grids
        offset = 0
        for p in range(self._num_players):
            grid = grids[p] if grids is not None else None
            for slot in range(_NUM_SLOTS):
                if grid is None or slot >= grid.num_slots:
                    # Missing slot (pre-deal) or eliminated column.
                    self.tensor[offset + 2] = 1.0
                elif grid.is_face_up(slot):
                    self.tensor[offset + 0] = 1.0
                    self.tensor[offset + 1] = float(grid.value(slot))
                # face-down -> all zeros (value hidden from everyone, owner included)
                offset += _FLOATS_PER_SLOT
        if state._discard_pile:
            self.tensor[offset] = float(state._discard_pile[-1])
        offset += 1
        self.tensor[offset] = float(sum(state._remaining_deck_counts.values())) / 150.0
        offset += 1
        if (
            state._phase == Phase.BRANCH_B_SUBACTION
            and state._current_player_index == player
            and state._drawn_card is not None
        ):
            self.tensor[offset] = float(state._drawn_card)
            self.tensor[offset + 1] = 1.0
        offset += 2
        self.tensor[offset] = float(state._round_ender) if state._round_ender is not None else -1.0
        offset += 1
        phase_index = {
            Phase.SETUP_COMMIT: 0,
            Phase.MAIN_PLAY: 1,
            Phase.MAIN_PLAY_DRAW_CHANCE: 2,
            Phase.BRANCH_B_SUBACTION: 3,
            Phase.TERMINAL: 4,
        }.get(state._phase, 0)
        self.tensor[offset + phase_index] = 1.0

    def string_from(self, state: Any, player: int) -> str:
        from table_peak.games.skyjo.state import Phase

        lines = [f"phase={state._phase.value}", f"viewer={player}"]
        grids = state._grids
        for p in range(self._num_players):
            g = grids[p] if grids is not None else None
            if g is None:
                lines.append(f"player_{p}=<no grid>")
                continue
            cells = [
                str(g.value(slot)) if g.is_face_up(slot) else "?" for slot in range(g.num_slots)
            ]
            lines.append(f"player_{p}=[{','.join(cells)}]")
        lines.append(f"discard_top={state._discard_pile[-1] if state._discard_pile else '<empty>'}")
        lines.append(f"draw_pile_size={sum(state._remaining_deck_counts.values())}")
        if (
            state._phase == Phase.BRANCH_B_SUBACTION
            and state._current_player_index == player
            and state._drawn_card is not None
        ):
            lines.append(f"drawn={state._drawn_card}")
        else:
            lines.append("drawn=?")
        if state._round_ender is not None:
            lines.append(f"round_ender={state._round_ender}")
        return "\n".join(lines)
