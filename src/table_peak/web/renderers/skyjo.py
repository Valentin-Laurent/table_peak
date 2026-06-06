"""Render a Skyjo state (PyspielStateAdapter) into a template-friendly view.

The human is the seat whose agent is None. Each human card/button carries the
engine action integer it posts:
  - main-play root : click a card -> TakeDiscardAndReplace(slot); plus a Draw button.
  - branch-b       : click a card -> ReplaceFromHand(slot); plus per-face-down-slot
                     DiscardAndFlip buttons (the disambiguation the spec calls out).
Opponent cards are never clickable. Hidden values render as "?".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from table_peak.agents.base import Agent
from table_peak.games._pyspiel_adapter import PyspielStateAdapter
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import actions as sk
from table_peak.games.skyjo.view import SkyjoPublicView, build_public_view

PARTIAL = "_skyjo_board.html"
TITLE = "Skyjo"


@dataclass(frozen=True, slots=True)
class SkyjoCard:
    label: str
    css: str
    clickable: bool
    action: int  # -1 when not clickable


@dataclass(frozen=True, slots=True)
class SkyjoPanel:
    seat: int
    label: str
    is_you: bool
    is_current: bool
    num_columns: int
    cards: tuple[SkyjoCard, ...]
    face_up_sum: int


@dataclass(frozen=True, slots=True)
class FlipButton:
    slot: int
    action: int


@dataclass(frozen=True, slots=True)
class SkyjoBoardView:
    partial: str
    title: str
    game_id: str
    status: str
    is_terminal: bool
    you: SkyjoPanel
    opponents: tuple[SkyjoPanel, ...]
    discard_top: int | None
    discard_css: str
    draw_pile_size: int
    can_draw: bool
    draw_action: int
    drawn_card: int | None
    drawn_css: str
    flip_buttons: tuple[FlipButton, ...]
    final_scores: tuple[tuple[str, int], ...]


def _css(value: int | None) -> str:
    if value is None:
        return "fd"
    if value < 0:
        return "neg"
    if value == 0:
        return "zero"
    if value <= 4:
        return "lo"
    if value <= 8:
        return "mid"
    return "hi"


def _human_seat(agents: dict[PlayerId, Agent | None]) -> int:
    for seat, agent in agents.items():
        if agent is None:
            return seat
    return 0


def _seat_label(seat: int, human_seat: int) -> str:
    return "YOU" if seat == human_seat else f"Bot {seat}"


def _panel(
    pv: SkyjoPublicView, seat: int, human_seat: int, cards: tuple[SkyjoCard, ...]
) -> SkyjoPanel:
    p = pv.players[seat]
    return SkyjoPanel(
        seat=seat,
        label=_seat_label(seat, human_seat),
        is_you=(seat == human_seat),
        is_current=(seat == pv.current_player),
        num_columns=p.num_columns,
        cards=cards,
        face_up_sum=p.face_up_sum,
    )


def _static_cards(pv: SkyjoPublicView, seat: int) -> tuple[SkyjoCard, ...]:
    return tuple(
        SkyjoCard(
            label="?" if c.value is None else str(c.value),
            css=_css(c.value),
            clickable=False,
            action=-1,
        )
        for c in pv.players[seat].cells
    )


def _human_cards(pv: SkyjoPublicView, seat: int, your_turn: bool) -> tuple[SkyjoCard, ...]:
    cards: list[SkyjoCard] = []
    for slot, c in enumerate(pv.players[seat].cells):
        if your_turn and pv.phase == "main_play":
            action = sk.encode_take_discard_and_replace(slot)
            clickable = True
        elif your_turn and pv.phase == "branch_b_subaction":
            action = sk.encode_replace_from_hand(slot)
            clickable = True
        else:
            action = -1
            clickable = False
        cards.append(
            SkyjoCard(
                label="?" if c.value is None else str(c.value),
                css=_css(c.value),
                clickable=clickable,
                action=action,
            )
        )
    return tuple(cards)


def _final_scores(pv: SkyjoPublicView, human_seat: int) -> tuple[tuple[str, int], ...]:
    assert pv.scores is not None
    ordered = sorted(pv.scores.items(), key=lambda kv: kv[1])
    return tuple((_seat_label(seat, human_seat), score) for seat, score in ordered)


def _status(pv: SkyjoPublicView, human_seat: int) -> str:
    if pv.is_terminal:
        assert pv.scores is not None
        your = pv.scores[human_seat]
        best = min(pv.scores.values())
        winners = [s for s, v in pv.scores.items() if v == best]
        if winners == [human_seat]:
            return f"Round over — you won with {your}."
        return f"Round over — you scored {your}; lowest score wins."
    if pv.phase == "main_play":
        return (
            f"Your turn — click a card to take the discard ({pv.discard_top}),"
            " or draw from the deck."
        )
    if pv.phase == "branch_b_subaction":
        return (
            f"You drew {pv.drawn_card} — click a card to keep it there,"
            " or discard & flip a hidden card."
        )
    return "Waiting…"


def render(
    state: Any,
    agents: dict[PlayerId, Agent | None],
    game_id: str,
) -> SkyjoBoardView:
    assert isinstance(state, PyspielStateAdapter)
    human_seat = _human_seat(agents)
    pv = build_public_view(state.inner, viewer=human_seat)
    your_turn = (not pv.is_terminal) and pv.current_player == human_seat

    you = _panel(pv, human_seat, human_seat, _human_cards(pv, human_seat, your_turn))
    opponents = tuple(
        _panel(pv, seat, human_seat, _static_cards(pv, seat))
        for seat in range(pv.num_players)
        if seat != human_seat
    )

    flip_buttons: tuple[FlipButton, ...] = ()
    if your_turn and pv.phase == "branch_b_subaction":
        flip_buttons = tuple(
            FlipButton(slot=slot, action=sk.encode_discard_and_flip(slot))
            for slot, c in enumerate(pv.players[human_seat].cells)
            if not c.face_up
        )

    return SkyjoBoardView(
        partial=PARTIAL,
        title=TITLE,
        game_id=game_id,
        status=_status(pv, human_seat),
        is_terminal=pv.is_terminal,
        you=you,
        opponents=opponents,
        discard_top=pv.discard_top,
        discard_css=_css(pv.discard_top),
        draw_pile_size=pv.draw_pile_size,
        can_draw=(your_turn and pv.phase == "main_play"),
        draw_action=sk.encode_draw_deck(),
        drawn_card=pv.drawn_card,
        drawn_css=_css(pv.drawn_card),
        flip_buttons=flip_buttons,
        final_scores=_final_scores(pv, human_seat) if pv.is_terminal else (),
    )
