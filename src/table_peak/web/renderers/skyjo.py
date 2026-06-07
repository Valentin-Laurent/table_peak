"""Render a Skyjo state (PyspielStateAdapter) into a template-friendly view.

The human is the seat whose agent is None. Interaction model (Skyjo-only):
  - setup          : click a card to pick the first of two to reveal (GET arm via
                     reveal_first), then click a second -> RevealInitial(i, j).
  - main-play root : click the *draw pile* -> DrawDeck, or click the *discard
                     pile* to "arm" place-mode; armed, each card click posts
                     TakeDiscardAndReplace(slot).
  - branch-b       : click a *face-down card* -> DiscardAndFlip(slot) (discard the
                     drawn card, reveal that one), or click the *drawn card* to
                     "arm" it; armed, each card click posts ReplaceFromHand(slot).
  - bot turn       : no human controls; a "Next" button steps one bot turn.
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
    clickable: bool  # True iff it posts a /move action
    action: int  # -1 when it posts no /move action
    arm_to: int = -1  # >=0: clicking arms this slot as the setup first-reveal (GET)
    selected: bool = False  # the already-picked first-reveal slot, highlighted


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
class TurnSlot:
    label: str
    is_current: bool


@dataclass(frozen=True, slots=True)
class SkyjoBoardView:
    partial: str
    title: str
    game_id: str
    status: str
    is_terminal: bool
    is_my_turn: bool
    awaiting_bot: bool
    last_event: str | None
    turn_order: tuple[TurnSlot, ...]
    you: SkyjoPanel
    opponents: tuple[SkyjoPanel, ...]
    discard_top: int | None
    discard_css: str
    discard_clickable: bool
    draw_pile_size: int
    draw_pile_clickable: bool
    draw_action: int
    armed: bool
    drawn_card: int | None
    drawn_css: str
    drawn_clickable: bool
    reveal_pending: bool  # setup: a first card is picked, awaiting the second
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


def _human_cards(
    pv: SkyjoPublicView, seat: int, your_turn: bool, armed: bool, reveal_first: int | None
) -> tuple[SkyjoCard, ...]:
    cards: list[SkyjoCard] = []
    for slot, c in enumerate(pv.players[seat].cells):
        action, arm_to, selected = -1, -1, False
        if your_turn and pv.phase == "setup_commit":
            if reveal_first is None:
                arm_to = slot  # first pick: clicking arms this slot (GET)
            elif slot == reveal_first:
                selected = True  # already chosen first card
            else:
                action = sk.encode_reveal_initial(reveal_first, slot)  # second pick (POST)
        elif your_turn and pv.phase == "main_play" and armed:
            action = sk.encode_take_discard_and_replace(slot)
        elif your_turn and pv.phase == "branch_b_subaction" and armed:
            # Drawn card armed: every slot is a place target for the drawn card.
            action = sk.encode_replace_from_hand(slot)
        elif your_turn and pv.phase == "branch_b_subaction" and not c.face_up:
            # Unarmed: clicking a face-down card discards the drawn card to reveal it.
            action = sk.encode_discard_and_flip(slot)
        cards.append(
            SkyjoCard(
                label="?" if c.value is None else str(c.value),
                css=_css(c.value),
                clickable=action >= 0,
                action=action,
                arm_to=arm_to,
                selected=selected,
            )
        )
    return tuple(cards)


def _final_scores(pv: SkyjoPublicView, human_seat: int) -> tuple[tuple[str, int], ...]:
    assert pv.scores is not None
    ordered = sorted(pv.scores.items(), key=lambda kv: kv[1])
    return tuple((_seat_label(seat, human_seat), score) for seat, score in ordered)


def _status(
    pv: SkyjoPublicView, human_seat: int, your_turn: bool, armed: bool, reveal_first: int | None
) -> str:
    if pv.is_terminal:
        assert pv.scores is not None
        your = pv.scores[human_seat]
        best = min(pv.scores.values())
        winners = [s for s, v in pv.scores.items() if v == best]
        if winners == [human_seat]:
            return f"Round over — you won with {your}."
        return f"Round over — you scored {your}; lowest score wins."
    if not your_turn:
        return f"Bot {pv.current_player}'s turn — click Next to play it out."
    if pv.phase == "setup_commit":
        if reveal_first is None:
            return "Round start — pick the first of two cards to reveal."
        return "Pick the second card to reveal, or cancel."
    if pv.phase == "branch_b_subaction":
        if armed:
            return f"Click any of your cards to place the drawn {pv.drawn_card} there, or cancel."
        return (
            f"You drew {pv.drawn_card} — click a face-down card to discard it and reveal that"
            " card, or click the drawn card to keep it."
        )
    if armed:
        return f"Click one of your cards to swap it for the discard ({pv.discard_top}), or cancel."
    return "Your turn — click the draw pile to draw, or the discard pile to take its top card."


def render(
    state: Any,
    agents: dict[PlayerId, Agent | None],
    game_id: str,
    *,
    armed: bool = False,
    reveal_first: int | None = None,
    last_event: str | None = None,
) -> SkyjoBoardView:
    assert isinstance(state, PyspielStateAdapter)
    human_seat = _human_seat(agents)
    pv = build_public_view(state.inner, viewer=human_seat)
    your_turn = (not pv.is_terminal) and pv.current_player == human_seat
    awaiting_bot = (not pv.is_terminal) and not your_turn
    # "armed" = place-mode: take-discard at the root, place-drawn in branch-b.
    armed = armed and your_turn and pv.phase in ("main_play", "branch_b_subaction")
    # "reveal_first" only applies on the human's own setup turn, and must be a real slot.
    num_slots = len(pv.players[human_seat].cells)
    if not (
        your_turn
        and pv.phase == "setup_commit"
        and reveal_first is not None
        and 0 <= reveal_first < num_slots
    ):
        reveal_first = None

    you = _panel(
        pv, human_seat, human_seat, _human_cards(pv, human_seat, your_turn, armed, reveal_first)
    )
    opponents = tuple(
        _panel(pv, seat, human_seat, _static_cards(pv, seat))
        for seat in range(pv.num_players)
        if seat != human_seat
    )

    turn_order = tuple(
        TurnSlot(
            label=_seat_label(seat, human_seat),
            is_current=(not pv.is_terminal) and seat == pv.current_player,
        )
        for seat in range(pv.num_players)
    )

    in_root = your_turn and pv.phase == "main_play"
    in_branch_b = your_turn and pv.phase == "branch_b_subaction"
    return SkyjoBoardView(
        partial=PARTIAL,
        title=TITLE,
        game_id=game_id,
        status=_status(pv, human_seat, your_turn, armed, reveal_first),
        is_terminal=pv.is_terminal,
        is_my_turn=your_turn,
        awaiting_bot=awaiting_bot,
        last_event=last_event,
        turn_order=turn_order,
        you=you,
        opponents=opponents,
        discard_top=pv.discard_top,
        discard_css=_css(pv.discard_top),
        discard_clickable=in_root and not armed and pv.discard_top is not None,
        draw_pile_size=pv.draw_pile_size,
        draw_pile_clickable=in_root and not armed,
        draw_action=sk.encode_draw_deck(),
        armed=armed,
        drawn_card=pv.drawn_card,
        drawn_css=_css(pv.drawn_card),
        drawn_clickable=in_branch_b and not armed,
        reveal_pending=reveal_first is not None,
        final_scores=_final_scores(pv, human_seat) if pv.is_terminal else (),
    )
