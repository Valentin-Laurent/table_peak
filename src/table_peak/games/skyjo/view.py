"""Viewer-aware public projection of a SkyjoState, for UI rendering.

Privacy model (identical to SkyjoObserver): a card's value is public iff it is
face-up; no one (owner included) sees a face-down value. The freshly drawn deck
card is visible only to the player who drew it, during a Branch-(b) sub-action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CardView:
    face_up: bool
    value: int | None  # None when face-down (value withheld)


@dataclass(frozen=True, slots=True)
class PlayerView:
    seat: int
    num_columns: int
    cells: tuple[CardView, ...]  # length num_slots, row-major
    face_up_sum: int


@dataclass(frozen=True, slots=True)
class SkyjoPublicView:
    num_players: int
    viewer: int
    phase: str
    current_player: int
    players: tuple[PlayerView, ...]
    discard_top: int | None
    draw_pile_size: int
    drawn_card: int | None  # set only when viewer is the player mid-Branch-(b)
    round_ender: int | None
    is_terminal: bool
    scores: dict[int, int] | None  # round_scores() at terminal, else None


def build_public_view(state: Any, viewer: int) -> SkyjoPublicView:
    """Project `state` (a SkyjoState) into a viewer-aware public view."""
    from table_peak.games.skyjo.state import Phase

    phase = state._phase
    grids = state._grids
    players: list[PlayerView] = []
    for p in range(state._num_players):
        g = grids[p] if grids is not None else None
        if g is None:
            players.append(PlayerView(seat=p, num_columns=0, cells=(), face_up_sum=0))
            continue
        cells = tuple(
            CardView(face_up=True, value=g.value(s))
            if g.is_face_up(s)
            else CardView(face_up=False, value=None)
            for s in range(g.num_slots)
        )
        face_up_sum = sum(g.value(s) for s in range(g.num_slots) if g.is_face_up(s))
        players.append(
            PlayerView(seat=p, num_columns=g.num_columns, cells=cells, face_up_sum=face_up_sum)
        )

    drawn: int | None = None
    if (
        phase == Phase.BRANCH_B_SUBACTION
        and state._current_player_index == viewer
        and state._drawn_card is not None
    ):
        drawn = int(state._drawn_card)

    is_terminal = phase == Phase.TERMINAL
    scores: dict[int, int] | None = state.round_scores() if is_terminal else None

    # During SETUP_COMMIT the active seat is the committer, not _current_player_index
    # (which is still -1 until main play). current_player() returns the committer there;
    # at chance/terminal it returns a negative sentinel, so fall back to the index.
    cp_raw = int(state.current_player())
    current_player = cp_raw if cp_raw >= 0 else int(state._current_player_index)

    return SkyjoPublicView(
        num_players=int(state._num_players),
        viewer=viewer,
        phase=phase.value,
        current_player=current_player,
        players=tuple(players),
        discard_top=state._discard_pile[-1] if state._discard_pile else None,
        draw_pile_size=int(sum(state._remaining_deck_counts.values())),
        drawn_card=drawn,
        round_ender=state._round_ender,
        is_terminal=is_terminal,
        scores=scores,
    )
