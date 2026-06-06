# Skyjo Web Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a human play one full round of Skyjo in the browser against Random bots, reusing the existing FastAPI web stack that today plays Tic-Tac-Toe.

**Architecture:** Generalize the TTT web core the minimal amount — `GameSession` carries a game key and a `State`-Protocol state; a per-game renderer registry dispatches rendering; moves post a raw `action: int`. Add a viewer-aware `build_public_view` to the Skyjo package (reusing the observer's privacy rules) and an `.inner` accessor on the pyspiel adapter so the Skyjo renderer can read a properly-hidden board. Setup (deal + flip-2) is auto-resolved with random reveals at game creation; the human is dropped into main play and plays to round-end. Each human gesture is one engine action = one HTTP move (same control flow as TTT's `submit_move` + `advance_bots`).

**Tech Stack:** Python 3.12, FastAPI, Jinja2, htmx (already vendored via CDN in templates), open_spiel/pyspiel (Skyjo engine), pytest + FastAPI `TestClient`, mypy --strict, ruff. Test/lint commands use `pdm run …`.

> **Environment note:** This repo has a known quirk where `pdm` and `git commit` may need to run outside the command sandbox (see project memory). If a `pdm`/`git` step fails with a sandbox/permission error, re-run that one command with the sandbox disabled.

---

## File Structure

**New files:**
- `src/table_peak/games/skyjo/view.py` — viewer-aware public projection of a `SkyjoState` (dataclasses + `build_public_view`).
- `src/table_peak/web/renderers/skyjo.py` — `SkyjoBoardView` (+ panel/card sub-views) and `render(state, agents, game_id)`.
- `src/table_peak/web/skyjo_play.py` — `new_skyjo_session(num_players, seed)` (build state + seat→agent map + auto-resolve setup).
- `src/table_peak/web/templates/_skyjo_board.html` — Skyjo board partial (self-contained styles).
- `tests/games/skyjo/test_view.py` — `build_public_view` projection + hiding tests.
- `tests/web/test_skyjo_renderer.py` — Skyjo renderer view tests.
- `tests/web/test_skyjo_play.py` — app-level start + full-round playthrough via `TestClient`.

**Modified files:**
- `src/table_peak/games/_pyspiel_adapter.py` — add read-only `.inner`.
- `src/table_peak/web/sessions.py` — `GameSession.state: State`, add `game: str = "tic_tac_toe"`.
- `src/table_peak/web/renderers/__init__.py` — `RENDERERS` registry.
- `src/table_peak/web/renderers/tic_tac_toe.py` — add `partial` + `title` fields to `BoardView`.
- `src/table_peak/web/app.py` — game branch in `create_game`, `cell`→`action`, registry dispatch.
- `src/table_peak/web/templates/new_game.html` — add a Skyjo new-game form.
- `src/table_peak/web/templates/game.html` — generic shell (title + include `view.partial`).
- `src/table_peak/web/templates/_board.html` — `name="cell"`→`name="action"`, self-contained styles.

**Constants reused (no engine change):** action encoders/decoder in `src/table_peak/games/skyjo/actions.py` (`encode_draw_deck`, `encode_take_discard_and_replace`, `encode_replace_from_hand`, `encode_discard_and_flip`, `decode`, `ActionKind`). Setup is detected as "every legal action decodes to `ActionKind.REVEAL_INITIAL`".

---

## Task 1: Expose the wrapped pyspiel state via `.inner`

**Files:**
- Modify: `src/table_peak/games/_pyspiel_adapter.py`
- Test: `tests/games/test_pyspiel_adapter.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/games/test_pyspiel_adapter.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/games/test_pyspiel_adapter.py::test_inner_exposes_underlying_python_state -v`
Expected: FAIL — `AttributeError: 'PyspielStateAdapter' object has no attribute 'inner'`.

- [ ] **Step 3: Add the `.inner` property**

In `src/table_peak/games/_pyspiel_adapter.py`, add `from typing import Any` to the imports, and add this property to `PyspielStateAdapter` (e.g. right after `__init__`):

```python
    @property
    def inner(self) -> Any:
        """The wrapped pyspiel.State (a game-specific Python State subclass).

        Game-agnostic consumers use the State Protocol surface; game-specific
        renderers read richer structure (e.g. Skyjo's grids) through here.
        """
        return self._inner
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/games/test_pyspiel_adapter.py::test_inner_exposes_underlying_python_state -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/_pyspiel_adapter.py tests/games/test_pyspiel_adapter.py
git commit -m "$(cat <<'EOF'
feat(adapter): expose wrapped pyspiel state via .inner

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Viewer-aware `build_public_view` for Skyjo

**Files:**
- Create: `src/table_peak/games/skyjo/view.py`
- Test: `tests/games/skyjo/test_view.py`

The privacy model matches the observer (`src/table_peak/games/skyjo/observer.py`): a card value is public iff face-up (hidden from everyone, owner included); the drawn deck card is visible only to the player who drew it during a Branch-(b) sub-action.

- [ ] **Step 1: Write the view module**

Create `src/table_peak/games/skyjo/view.py`:

```python
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

    return SkyjoPublicView(
        num_players=int(state._num_players),
        viewer=viewer,
        phase=phase.value,
        current_player=int(state._current_player_index),
        players=tuple(players),
        discard_top=state._discard_pile[-1] if state._discard_pile else None,
        draw_pile_size=int(sum(state._remaining_deck_counts.values())),
        drawn_card=drawn,
        round_ender=state._round_ender,
        is_terminal=is_terminal,
        scores=scores,
    )
```

- [ ] **Step 2: Write the failing tests**

Create `tests/games/skyjo/test_view.py`:

```python
"""Tests for build_public_view: structure + the Skyjo privacy model."""

from __future__ import annotations

import random
from typing import Any

from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.games.skyjo.view import build_public_view


def _in_setup(state: Any) -> bool:
    legal = list(state.legal_actions())
    return bool(legal) and all(
        sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal
    )


def _play_to_main(num_players: int, seed: int) -> Any:
    """Create a game and apply random reveals until setup is over."""
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def test_after_setup_each_player_has_two_face_up_and_hidden_values_are_none() -> None:
    state = _play_to_main(num_players=3, seed=11)
    pv = build_public_view(state.inner, viewer=0)
    assert pv.phase == "main_play"
    assert pv.num_players == 3
    for player in pv.players:
        face_up = [c for c in player.cells if c.face_up]
        face_down = [c for c in player.cells if not c.face_up]
        assert len(face_up) == 2
        assert all(c.value is not None for c in face_up)
        # Hidden cards never carry a value — for any seat, owner included.
        assert all(c.value is None for c in face_down)
    assert pv.discard_top is not None
    assert pv.draw_pile_size > 0


def test_drawn_card_visible_only_to_the_drawer() -> None:
    state = _play_to_main(num_players=2, seed=5)
    # Advance to a turn owned by seat 0, then draw from the deck.
    rng = random.Random(5)
    while not state.is_terminal and build_public_view(state.inner, 0).current_player != 0:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    state = state.apply_action(sk.encode_draw_deck())
    drawer_view = build_public_view(state.inner, viewer=0)
    other_view = build_public_view(state.inner, viewer=1)
    assert drawer_view.phase == "branch_b_subaction"
    assert drawer_view.drawn_card is not None
    assert other_view.drawn_card is None


def test_terminal_view_reveals_all_and_matches_round_scores() -> None:
    rng = random.Random(99)
    state = SkyjoGameWrapper(num_players=2, seed=99).new_initial_state()
    while not state.is_terminal:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    pv = build_public_view(state.inner, viewer=0)
    assert pv.is_terminal is True
    assert pv.scores == state.inner.round_scores()
    for player in pv.players:
        assert all(c.face_up for c in player.cells)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pdm run pytest tests/games/skyjo/test_view.py -v`
Expected: PASS (3 tests). (The module from Step 1 already implements the behavior.)

- [ ] **Step 4: Commit**

```bash
git add src/table_peak/games/skyjo/view.py tests/games/skyjo/test_view.py
git commit -m "$(cat <<'EOF'
feat(skyjo): viewer-aware build_public_view for UI rendering

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Skyjo board renderer

**Files:**
- Create: `src/table_peak/web/renderers/skyjo.py`
- Test: `tests/web/test_skyjo_renderer.py`

- [ ] **Step 1: Write the renderer**

Create `src/table_peak/web/renderers/skyjo.py`:

```python
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


def _panel(pv: SkyjoPublicView, seat: int, human_seat: int, cards: tuple[SkyjoCard, ...]) -> SkyjoPanel:
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
        return f"Your turn — click a card to take the discard ({pv.discard_top}), or draw from the deck."
    if pv.phase == "branch_b_subaction":
        return f"You drew {pv.drawn_card} — click a card to keep it there, or discard & flip a hidden card."
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
```

- [ ] **Step 2: Write the failing tests**

Create `tests/web/test_skyjo_renderer.py`:

```python
"""Tests for the Skyjo board renderer (state -> SkyjoBoardView)."""

from __future__ import annotations

import random
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.web.renderers.skyjo import render


def _in_setup(state: Any) -> bool:
    legal = list(state.legal_actions())
    return bool(legal) and all(
        sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal
    )


def _to_human_turn(num_players: int, seed: int) -> Any:
    """State at a main-play root turn owned by seat 0."""
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    while not state.is_terminal and state.current_player != 0:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def _agents(num_players: int) -> dict[PlayerId, Agent | None]:
    a: dict[PlayerId, Agent | None] = {0: None}
    for p in range(1, num_players):
        a[p] = RandomAgent(random.Random(p))
    return a


def test_root_turn_cards_post_take_discard_and_draw_button_present() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1")
    assert view.partial == "_skyjo_board.html"
    assert view.title == "Skyjo"
    assert view.can_draw is True
    assert view.draw_action == sk.encode_draw_deck()
    # Every one of the human's cards is clickable and posts a take-discard action.
    assert view.you.is_you is True
    assert all(card.clickable for card in view.you.cards)
    for slot, card in enumerate(view.you.cards):
        assert card.action == sk.encode_take_discard_and_replace(slot)
    # Opponent cards are never clickable, and hidden cards show "?".
    for opp in view.opponents:
        assert all(not card.clickable for card in opp.cards)
    assert any(card.label == "?" for card in view.opponents[0].cards)


def test_branch_b_offers_replace_cards_and_flip_buttons() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    state = state.apply_action(sk.encode_draw_deck())
    view = render(state, _agents(2), "g1")
    assert view.can_draw is False
    assert view.drawn_card is not None
    # Cards post replace-from-hand.
    for slot, card in enumerate(view.you.cards):
        assert card.clickable is True
        assert card.action == sk.encode_replace_from_hand(slot)
    # There is one flip button per face-down slot, posting discard-and-flip.
    flip_slots = {fb.slot for fb in view.flip_buttons}
    assert len(view.flip_buttons) >= 1
    for fb in view.flip_buttons:
        assert fb.action == sk.encode_discard_and_flip(fb.slot)
    # Flip buttons target only currently-hidden slots.
    for slot, card in enumerate(view.you.cards):
        if card.label != "?":
            assert slot not in flip_slots


def test_terminal_shows_sorted_scores_and_no_clickable_cards() -> None:
    rng = random.Random(42)
    state = SkyjoGameWrapper(num_players=2, seed=42).new_initial_state()
    while not state.is_terminal:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    view = render(state, _agents(2), "g1")
    assert view.is_terminal is True
    assert view.can_draw is False
    assert all(not card.clickable for card in view.you.cards)
    scores = [score for _label, score in view.final_scores]
    assert scores == sorted(scores)  # ascending; lowest wins
    assert "Round over" in view.status
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pdm run pytest tests/web/test_skyjo_renderer.py -v`
Expected: PASS (3 tests).

- [ ] **Step 4: Commit**

```bash
git add src/table_peak/web/renderers/skyjo.py tests/web/test_skyjo_renderer.py
git commit -m "$(cat <<'EOF'
feat(web): Skyjo board renderer (state -> SkyjoBoardView)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Skyjo session factory with auto-resolved setup

**Files:**
- Create: `src/table_peak/web/skyjo_play.py`
- Test: `tests/web/test_skyjo_play.py` (the non-HTTP part; HTTP tests come in Task 7)

This task depends on `GameSession` gaining a `game` field, which lands in Task 5. To keep this task self-contained and green, it constructs `GameSession` with `game="skyjo"` — so do Task 5 first if executing strictly in order, OR (recommended) implement Task 5's `sessions.py` change as Step 1 here. The plan keeps them separate for clarity; the executor may fold Task 5 Step "GameSession field" in first.

> **Execution note:** run Task 5's `sessions.py` edit (add `game: str = "tic_tac_toe"`) before this task's tests, otherwise `GameSession(game=...)` raises `TypeError`.

- [ ] **Step 1: Write the factory**

Create `src/table_peak/web/skyjo_play.py`:

```python
"""Build a web GameSession for Skyjo: human at seat 0, Random bots elsewhere.

Setup (deal + the blind flip-2) is auto-resolved with random reveals for every
seat, including the human, so the human is handed their first main-play turn.
"""

from __future__ import annotations

import random
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.games.skyjo import actions as sk
from table_peak.web.sessions import GameSession

HUMAN_SEAT = 0


def _in_setup(state: Any) -> bool:
    legal = list(state.legal_actions())
    return bool(legal) and all(
        sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal
    )


def _auto_resolve_setup(state: Any, rng: random.Random) -> Any:
    while not state.is_terminal and _in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def new_skyjo_session(num_players: int, seed: int = 0) -> GameSession:
    if not 2 <= num_players <= 8:
        raise ValueError(f"num_players must be in [2, 8], got {num_players}")
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()
    state = _auto_resolve_setup(state, rng)
    agents: dict[PlayerId, Agent | None] = {HUMAN_SEAT: None}
    for p in range(num_players):
        if p != HUMAN_SEAT:
            agents[p] = RandomAgent(random.Random(seed + 1 + p))
    return GameSession(game="skyjo", state=state, agents=agents)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/web/test_skyjo_play.py` (HTTP tests are added in Task 7):

```python
"""Tests for the Skyjo web session factory + (Task 7) the app routes."""

from __future__ import annotations

from table_peak.web.renderers.skyjo import render
from table_peak.web.skyjo_play import HUMAN_SEAT, new_skyjo_session


def test_new_session_drops_human_into_main_play_with_two_face_up() -> None:
    session = new_skyjo_session(num_players=4, seed=1)
    assert session.game == "skyjo"
    assert session.agents[HUMAN_SEAT] is None
    assert len(session.agents) == 4
    view = render(session.state, session.agents, "g")
    # Setup is over: the human can either take-discard or draw.
    assert view.is_terminal is False
    assert view.can_draw is True
    your_face_up = [c for c in view.you.cards if c.label != "?"]
    assert len(your_face_up) == 2


def test_new_session_is_reproducible_for_a_fixed_seed() -> None:
    a = new_skyjo_session(num_players=3, seed=7)
    b = new_skyjo_session(num_players=3, seed=7)
    va = render(a.state, a.agents, "g")
    vb = render(b.state, b.agents, "g")
    assert [c.label for c in va.you.cards] == [c.label for c in vb.you.cards]
    assert va.discard_top == vb.discard_top


def test_invalid_player_count_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        new_skyjo_session(num_players=1)
    with pytest.raises(ValueError):
        new_skyjo_session(num_players=9)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pdm run pytest tests/web/test_skyjo_play.py -v`
Expected: PASS (3 tests). Requires Task 5's `GameSession.game` field (see execution note).

- [ ] **Step 4: Commit**

```bash
git add src/table_peak/web/skyjo_play.py tests/web/test_skyjo_play.py
git commit -m "$(cat <<'EOF'
feat(web): Skyjo session factory with auto-resolved setup

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Generalize the session + renderer registry

**Files:**
- Modify: `src/table_peak/web/sessions.py`
- Modify: `src/table_peak/web/renderers/tic_tac_toe.py`
- Modify: `src/table_peak/web/renderers/__init__.py`
- Test: `tests/web/test_sessions.py`, `tests/web/test_renderer.py` (must still pass unchanged)

- [ ] **Step 1: Generalize `GameSession`**

In `src/table_peak/web/sessions.py`:
- Change the import `from table_peak.games.tic_tac_toe import TicTacToeState` to `from table_peak.games.base import State` (keep `PlayerId` import).
- Change the `GameSession` dataclass to:

```python
@dataclass
class GameSession:
    """One in-progress (or finished) game.

    `agents[seat] is None` means a human plays that seat. The web adapter
    applies human actions to `state` directly; bots are called via `Agent.act`.

    `game` selects the renderer (and is the key into the renderer registry).
    Mutable by design: `advance_bots` and the web layer replace `state` after
    each bot move; `agents` and `game` are unchanged after construction.
    """

    state: State
    agents: dict[PlayerId, Agent | None]
    game: str = "tic_tac_toe"
```

(`advance_bots` and `InMemorySessionStore` are unchanged — they already use only Protocol methods. Remove the now-unused `TicTacToeState` import.)

- [ ] **Step 2: Verify session + adapter tests still pass**

Run: `pdm run pytest tests/web/test_sessions.py -v`
Expected: PASS unchanged (TTT sessions default `game="tic_tac_toe"`; `.board` access still works on the concrete `TicTacToeState` instance).

- [ ] **Step 3: Add `partial` + `title` to the TTT `BoardView`**

In `src/table_peak/web/renderers/tic_tac_toe.py`, add two fields with defaults to `BoardView` (so existing construction and tests are unaffected):

```python
@dataclass(frozen=True, slots=True)
class BoardView:
    """Everything `_board.html` and `game.html` need to render a TTT board."""

    cells: tuple[str, ...]  # length 9, each "" / "X" / "O"
    is_terminal: bool
    status: str
    cells_clickable: bool
    game_id: str
    partial: str = "_board.html"
    title: str = "Tic-Tac-Toe"
```

- [ ] **Step 4: Create the renderer registry**

Replace the contents of `src/table_peak/web/renderers/__init__.py` with:

```python
"""Per-game renderer registry. Maps a session's game key to a render function.

Each render function takes (state, agents, game_id) and returns a view object
exposing at least `.partial` (the Jinja partial template) and `.title`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from table_peak.agents.base import Agent
from table_peak.games.base import PlayerId
from table_peak.web.renderers import skyjo, tic_tac_toe

RenderFn = Callable[[Any, dict[PlayerId, Agent | None], str], Any]

RENDERERS: dict[str, RenderFn] = {
    "tic_tac_toe": tic_tac_toe.render,
    "skyjo": skyjo.render,
}
```

- [ ] **Step 5: Verify renderer tests still pass and the registry imports**

Run: `pdm run pytest tests/web/test_renderer.py tests/web/test_skyjo_renderer.py -v`
Expected: PASS. Also run `pdm run python -c "from table_peak.web.renderers import RENDERERS; print(sorted(RENDERERS))"` → prints `['skyjo', 'tic_tac_toe']`.

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/web/sessions.py src/table_peak/web/renderers/__init__.py src/table_peak/web/renderers/tic_tac_toe.py
git commit -m "$(cat <<'EOF'
refactor(web): generalize GameSession + add renderer registry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Generalize templates + app routes (TTT regression + Skyjo start)

**Files:**
- Modify: `src/table_peak/web/templates/game.html`
- Modify: `src/table_peak/web/templates/_board.html`
- Modify: `src/table_peak/web/templates/new_game.html`
- Modify: `src/table_peak/web/app.py`
- Test: `tests/web/test_app.py` (must pass after the `cell`→`action` rename), `tests/web/test_skyjo_play.py` (add HTTP start test)

- [ ] **Step 1: Make `game.html` a generic shell**

Replace `src/table_peak/web/templates/game.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>table_peak — {{ view.title }}</title>
    <script src="https://unpkg.com/htmx.org@2.0.3"></script>
</head>
<body>
    <h1>{{ view.title }}</h1>
    {% include view.partial %}
    <p><a href="/">New game</a></p>
</body>
</html>
```

- [ ] **Step 2: Update `_board.html` (TTT) — self-contained styles + `action` field**

Replace `src/table_peak/web/templates/_board.html` with:

```html
<div id="board">
    <style>
        .grid { display: grid; grid-template-columns: repeat(3, 64px); gap: 4px; margin: 1rem 0; }
        .cell { width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; }
        .cell button { width: 100%; height: 100%; font-size: 2rem; cursor: pointer; }
        .cell.mark, .cell.empty { font-size: 2rem; border: 1px solid #ccc; }
        .status { font-size: 1.25rem; }
    </style>
    <p class="status">{{ view.status }}</p>
    <div class="grid">
        {% for cell in view.cells %}
            {% set idx = loop.index0 %}
            {% if cell %}
                <span class="cell mark">{{ cell }}</span>
            {% elif view.cells_clickable %}
                <form hx-post="/games/{{ view.game_id }}/move"
                      hx-target="#board" hx-swap="outerHTML"
                      class="cell">
                    <button type="submit" name="action" value="{{ idx }}">·</button>
                </form>
            {% else %}
                <span class="cell empty">·</span>
            {% endif %}
        {% endfor %}
    </div>
</div>
```

- [ ] **Step 3: Add a Skyjo form to `new_game.html`**

Replace `src/table_peak/web/templates/new_game.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>table_peak — New Game</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 480px; margin: 2rem auto; padding: 0 1rem; }
        label { display: block; margin: 0.5rem 0; }
        select, button { font-size: 1rem; padding: 0.25rem 0.5rem; }
        fieldset { margin: 1rem 0; }
    </style>
</head>
<body>
    <h1>New Game</h1>

    <form action="/games" method="post">
        <fieldset>
            <legend>Tic-Tac-Toe</legend>
            <input type="hidden" name="game" value="tic_tac_toe">
            <label>
                X (first to move):
                <select name="x_agent">
                    <option value="Human" selected>Human</option>
                    <option value="Random">Random</option>
                    <option value="Minimax">Minimax</option>
                </select>
            </label>
            <label>
                O:
                <select name="o_agent">
                    <option value="Human">Human</option>
                    <option value="Random">Random</option>
                    <option value="Minimax" selected>Minimax</option>
                </select>
            </label>
            <button type="submit">Start Tic-Tac-Toe</button>
        </fieldset>
    </form>

    <form action="/games" method="post">
        <fieldset>
            <legend>Skyjo (you vs Random bots)</legend>
            <input type="hidden" name="game" value="skyjo">
            <label>
                Players:
                <select name="num_players">
                    <option value="2" selected>2</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                    <option value="5">5</option>
                    <option value="6">6</option>
                    <option value="7">7</option>
                    <option value="8">8</option>
                </select>
            </label>
            <button type="submit">Start Skyjo</button>
        </fieldset>
    </form>
</body>
</html>
```

- [ ] **Step 4: Generalize `app.py`**

Rewrite `src/table_peak/web/app.py` to branch on the `game` form field, dispatch rendering via the registry, and rename `cell`→`action`:

```python
"""FastAPI app — driving adapter for the table_peak web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from table_peak.agents.base import Agent
from table_peak.games.base import PlayerId
from table_peak.games.tic_tac_toe import TicTacToe
from table_peak.web.agents import AGENT_REGISTRY
from table_peak.web.renderers import RENDERERS
from table_peak.web.sessions import GameSession, InMemorySessionStore, advance_bots
from table_peak.web.skyjo_play import new_skyjo_session

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_store = InMemorySessionStore()


def get_store() -> InMemorySessionStore:
    """FastAPI dependency. Tests override via app.dependency_overrides."""
    return _store


app = FastAPI(title="table_peak — Web UI")


def _build_agent(name: str) -> Agent | None:
    if name == "Human":
        return None
    factory = AGENT_REGISTRY.get(name)
    if factory is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {name}")
    return factory()


def _render(session: GameSession, game_id: str) -> object:
    render_fn = RENDERERS.get(session.game)
    if render_fn is None:
        raise HTTPException(status_code=500, detail=f"No renderer for game: {session.game}")
    return render_fn(session.state, session.agents, game_id)


@app.get("/", response_class=HTMLResponse)
def new_game_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "new_game.html")


@app.post("/games")
def create_game(
    store: Annotated[InMemorySessionStore, Depends(get_store)],
    game: Annotated[str, Form()] = "tic_tac_toe",
    x_agent: Annotated[str, Form()] = "Human",
    o_agent: Annotated[str, Form()] = "Random",
    num_players: Annotated[int, Form()] = 2,
) -> RedirectResponse:
    if game == "skyjo":
        if not 2 <= num_players <= 8:
            raise HTTPException(status_code=400, detail="num_players must be in [2, 8]")
        session = new_skyjo_session(num_players=num_players)
    elif game == "tic_tac_toe":
        agents: dict[PlayerId, Agent | None] = {
            0: _build_agent(x_agent),
            1: _build_agent(o_agent),
        }
        session = GameSession(
            game="tic_tac_toe",
            state=TicTacToe().new_initial_state(),
            agents=agents,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown game: {game}")
    game_id = store.create(session)
    return RedirectResponse(url=f"/games/{game_id}", status_code=303)


@app.get("/games/{game_id}", response_class=HTMLResponse)
def game_page(
    game_id: str,
    request: Request,
    store: Annotated[InMemorySessionStore, Depends(get_store)],
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    advance_bots(session)
    store.save(game_id, session)
    view = _render(session, game_id)
    return templates.TemplateResponse(request, "game.html", {"view": view})


@app.post("/games/{game_id}/move", response_class=HTMLResponse)
def submit_move(
    game_id: str,
    request: Request,
    action: Annotated[int, Form()],
    store: Annotated[InMemorySessionStore, Depends(get_store)],
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    if session.state.is_terminal:
        raise HTTPException(status_code=409, detail="Game is over")
    if session.agents[session.state.current_player] is not None:
        raise HTTPException(status_code=409, detail="Not your turn")
    if action not in session.state.legal_actions():
        raise HTTPException(status_code=400, detail=f"Illegal action: {action}")
    session.state = session.state.apply_action(action)
    advance_bots(session)
    store.save(game_id, session)
    view = _render(session, game_id)
    partial = getattr(view, "partial")
    return templates.TemplateResponse(request, partial, {"view": view})
```

- [ ] **Step 5: Update the TTT app tests for the `cell`→`action` field name**

In `tests/web/test_app.py`, replace every `data={"cell": "<n>"}` with `data={"action": "<n>"}` (the field was renamed; the values and assertions are otherwise unchanged). There are occurrences in: `test_human_vs_bot_first_move_advances_bot_reply`, `test_invalid_move_rejected`, `test_move_when_terminal_rejected`, `test_move_when_not_humans_turn_rejected`, `test_move_on_unknown_game_returns_404`, `test_out_of_range_cell_rejected`.

- [ ] **Step 6: Run the TTT app suite to verify the regression holds**

Run: `pdm run pytest tests/web/test_app.py -v`
Expected: PASS (all existing TTT app tests, now posting `action`).

- [ ] **Step 7: Add an HTTP start test for Skyjo**

Append to `tests/web/test_skyjo_play.py`:

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from table_peak.web.app import app, get_store
from table_peak.web.sessions import InMemorySessionStore


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = InMemorySessionStore()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_store, None)


def test_new_game_page_offers_skyjo(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="num_players"' in r.text
    assert 'value="skyjo"' in r.text


def test_create_skyjo_game_renders_board(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"game": "skyjo", "num_players": "3"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert r.text.count("Skyjo") >= 1
    assert 'id="board"' in r.text
    # The human is on a main-play turn: the Draw button is present.
    assert "Draw from deck" in r.text


def test_create_skyjo_game_rejects_bad_player_count(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"game": "skyjo", "num_players": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 400
```

- [ ] **Step 8: Run the Skyjo app tests**

Run: `pdm run pytest tests/web/test_skyjo_play.py -v`
Expected: the factory tests PASS and the two `test_create_skyjo_game_renders_board` / `…offers_skyjo` / `…rejects_bad_player_count` PASS, **except** `test_create_skyjo_game_renders_board` will FAIL on the missing `_skyjo_board.html` template (`jinja2.exceptions.TemplateNotFound`). That template is Task 7. The start-validation and page tests that don't render the board pass now.

> If you prefer all-green commits, defer running `test_create_skyjo_game_renders_board` until Task 7; the other tests in this file pass here.

- [ ] **Step 9: Commit**

```bash
git add src/table_peak/web/app.py src/table_peak/web/templates/game.html src/table_peak/web/templates/_board.html src/table_peak/web/templates/new_game.html tests/web/test_app.py tests/web/test_skyjo_play.py
git commit -m "$(cat <<'EOF'
feat(web): generalize routes/templates for multi-game; add Skyjo start

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Skyjo board template + full-round playthrough

**Files:**
- Create: `src/table_peak/web/templates/_skyjo_board.html`
- Test: `tests/web/test_skyjo_play.py` (add the full-round playthrough)

- [ ] **Step 1: Write the Skyjo board partial**

Create `src/table_peak/web/templates/_skyjo_board.html`:

```html
<div id="board">
    <style>
        .skyjo { font-family: system-ui, sans-serif; }
        .opps { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-bottom: 12px; }
        .panel { border: 1px solid #39414f; border-radius: 8px; padding: 8px; }
        .panel.you { border-color: #4f9d5b; }
        .panel .tag { font-size: 11px; opacity: .8; margin-bottom: 4px; }
        .sgrid { display: grid; gap: 3px; }
        .card { width: 40px; height: 52px; border-radius: 5px; display: flex; align-items: center;
                justify-content: center; font-weight: 700; color: #fff; border: none; font-size: 14px; }
        .card.mini { width: 26px; height: 34px; font-size: 10px; }
        button.card { cursor: pointer; }
        .fd { background: #5b6472; color: #aeb6c2; } .neg { background: #3b6fb0; }
        .zero { background: #8a93a2; } .lo { background: #4f9d5b; }
        .mid { background: #d9a23b; } .hi { background: #c0504d; }
        .piles { display: flex; gap: 16px; justify-content: center; align-items: center; margin: 10px 0; }
        .controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 8px; }
        .status { font-size: 1.1rem; margin: 8px 0; }
        table.scores { margin: 8px 0; border-collapse: collapse; }
        table.scores td { border: 1px solid #ccc; padding: 2px 10px; }
    </style>

    <div class="skyjo">
        <p class="status">{{ view.status }}</p>

        <div class="opps">
            {% for opp in view.opponents %}
            <div class="panel">
                <div class="tag">{{ opp.label }} · sum {{ opp.face_up_sum }}{% if opp.is_current %} · ▶{% endif %}</div>
                <div class="sgrid" style="grid-template-columns: repeat({{ opp.num_columns }}, 1fr);">
                    {% for card in opp.cards %}
                    <span class="card mini {{ card.css }}">{{ card.label }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="piles">
            <div style="text-align:center;">
                <span class="card fd">{{ view.draw_pile_size }}</span>
                <div class="tag">draw</div>
            </div>
            <div style="text-align:center;">
                {% if view.discard_top is not none %}
                <span class="card {{ view.discard_css }}">{{ view.discard_top }}</span>
                {% else %}
                <span class="card fd">—</span>
                {% endif %}
                <div class="tag">discard</div>
            </div>
            {% if view.drawn_card is not none %}
            <div style="text-align:center;">
                <span class="card {{ view.drawn_css }}">{{ view.drawn_card }}</span>
                <div class="tag">drawn</div>
            </div>
            {% endif %}
        </div>

        <div class="panel you">
            <div class="tag">{{ view.you.label }} · sum {{ view.you.face_up_sum }}{% if view.you.is_current %} · ▶{% endif %}</div>
            <div class="sgrid" style="grid-template-columns: repeat({{ view.you.num_columns }}, 1fr);">
                {% for card in view.you.cards %}
                    {% if card.clickable %}
                    <form hx-post="/games/{{ view.game_id }}/move" hx-target="#board" hx-swap="outerHTML"
                          style="display:contents;">
                        <button type="submit" class="card {{ card.css }}" name="action" value="{{ card.action }}">{{ card.label }}</button>
                    </form>
                    {% else %}
                    <span class="card {{ card.css }}">{{ card.label }}</span>
                    {% endif %}
                {% endfor %}
            </div>
        </div>

        {% if not view.is_terminal %}
        <div class="controls">
            {% if view.can_draw %}
            <form hx-post="/games/{{ view.game_id }}/move" hx-target="#board" hx-swap="outerHTML">
                <button type="submit" name="action" value="{{ view.draw_action }}">Draw from deck</button>
            </form>
            {% endif %}
            {% if view.flip_buttons %}
            <span>Discard {{ view.drawn_card }} &amp; flip:</span>
            {% for fb in view.flip_buttons %}
            <form hx-post="/games/{{ view.game_id }}/move" hx-target="#board" hx-swap="outerHTML">
                <button type="submit" name="action" value="{{ fb.action }}">slot {{ fb.slot }}</button>
            </form>
            {% endfor %}
            {% endif %}
        </div>
        {% endif %}

        {% if view.is_terminal %}
        <table class="scores">
            {% for label, score in view.final_scores %}
            <tr><td>{{ label }}</td><td>{{ score }}</td></tr>
            {% endfor %}
        </table>
        {% endif %}
    </div>
</div>
```

- [ ] **Step 2: Run the board-rendering app test to verify it passes**

Run: `pdm run pytest tests/web/test_skyjo_play.py::test_create_skyjo_game_renders_board -v`
Expected: PASS (template now resolves; "Draw from deck" present).

- [ ] **Step 3: Write the failing full-round playthrough test**

Append to `tests/web/test_skyjo_play.py`:

```python
def _post_first_legal_human_action(client: TestClient, game_id: str, html: str) -> str:
    """Parse the board fragment, post the first legal human action, return new html.

    The renderer puts each legal action in `name="action" value="N"`. We pick the
    first one (any legal move keeps the round progressing toward terminal)."""
    import re

    matches = re.findall(r'name="action" value="(\d+)"', html)
    assert matches, f"no clickable action in board:\n{html[:500]}"
    action = matches[0]
    r = client.post(f"/games/{game_id}/move", data={"action": action})
    assert r.status_code == 200, r.text
    return r.text


def test_full_round_playthrough_reaches_terminal_with_scores(client: TestClient) -> None:
    r = client.post(
        "/games",
        data={"game": "skyjo", "num_players": "2"},
        follow_redirects=False,
    )
    game_id = str(r.headers["location"]).rsplit("/", 1)[-1]
    html = client.get(f"/games/{game_id}").text

    # Drive the human by always taking the first offered legal action. The round
    # is finite, so this terminates. Cap iterations as a safety net.
    for _ in range(500):
        if "Round over" in html:
            break
        html = _post_first_legal_human_action(client, game_id, html)
    assert "Round over" in html
    # The score table is present (one row per player => at least two <td> score cells).
    assert html.count("</td>") >= 4
```

- [ ] **Step 4: Run the full-round test**

Run: `pdm run pytest tests/web/test_skyjo_play.py::test_full_round_playthrough_reaches_terminal_with_scores -v`
Expected: PASS (reaches "Round over" and shows a score table).

- [ ] **Step 5: Run the entire web + skyjo suite**

Run: `pdm run pytest tests/web tests/games/skyjo tests/games/test_pyspiel_adapter.py -v`
Expected: PASS (TTT regression + all new Skyjo tests).

- [ ] **Step 6: Commit**

```bash
git add src/table_peak/web/templates/_skyjo_board.html tests/web/test_skyjo_play.py
git commit -m "$(cat <<'EOF'
feat(web): Skyjo board template + full-round playthrough test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Static checks + full suite

**Files:** none (verification only)

- [ ] **Step 1: Run mypy --strict**

Run: `pdm run mypy`
Expected: `Success: no issues found`. If pyspiel-attribute access on `Any` surfaces an error, confirm the relevant `state` parameters are annotated `Any` (as in `view.py` / `skyjo.py`).

- [ ] **Step 2: Run ruff**

Run: `pdm run ruff check`
Expected: no errors. Fix any import-ordering / unused-import findings (e.g. removed `TicTacToeState` import in `sessions.py`).

- [ ] **Step 3: Run the full test suite**

Run: `pdm run pytest`
Expected: all tests pass (whole repo).

- [ ] **Step 4: Manual smoke (optional but recommended)**

Run: `pdm run uvicorn table_peak.web.app:app --reload` (outside the sandbox, since it binds a port), open `http://127.0.0.1:8000/`, start a Skyjo game, and play a turn. Confirm the board renders and a move re-renders the fragment.

- [ ] **Step 5: Final commit (if any lint/type fixes were made)**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore(web): satisfy mypy --strict and ruff for skyjo web play

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- Front-end = web UI reusing TTT stack → Tasks 5–7. ✓
- One human + N Random bots, 2–8, seat 0 human → Task 4 (`new_skyjo_session`), Task 6 (`num_players` form + validation). ✓
- One round only → engine is single-round; no multi-round code added. ✓
- Drop in after randomized setup, no fast-forward → Task 4 `_auto_resolve_setup`. ✓
- Layout A (opponents top, you bottom) → Task 7 template (`.opps` row above `.panel.you`). ✓
- Take-discard (no toggle) / draw → replace-or-flip (explicit flip buttons) → Task 3 renderer + Task 7 template. ✓
- Generalize web core minimally (State-typed session, renderer registry, raw `action` int) → Tasks 5–6. ✓
- `public_view(viewer)` on the engine + `.inner` on adapter → Tasks 1–2 (implemented as `build_public_view` free function + `.inner`; the spec's "method" is realized as a package-level builder to avoid relying on pyspiel virtual dispatch — an implementation refinement). ✓
- Information hiding (no face-down/opponent-drawn leak) → Task 2 + Task 3 tests assert hidden→`None`/`"?"`. ✓
- Success criteria 1–6 → start (Task 6), full round + scores (Task 7), TTT regression (Tasks 5–6), no leak (Tasks 2–3), illegal-move 4xx (Task 6 reuses TTT validation, covered by existing `test_out_of_range_cell_rejected` analog), mypy/ruff (Task 8). ✓

**Placeholder scan:** No TBD/TODO; every code step contains complete code; every test step contains real assertions. The only conditional is Task 6 Step 8's documented expected partial-failure (the board-render test depends on Task 7's template) — this is an ordering note, not a placeholder.

**Type consistency:** `build_public_view(state, viewer)` returns `SkyjoPublicView` (Task 2) consumed in Task 3; field names (`players`, `cells`, `face_up`, `value`, `phase`, `current_player`, `drawn_card`, `scores`) match between producer and consumer. `SkyjoBoardView` fields (`partial`, `title`, `you`, `opponents`, `can_draw`, `draw_action`, `flip_buttons`, `final_scores`, `drawn_card`, `discard_top`, `discard_css`, `drawn_css`) match the `_skyjo_board.html` template references. `GameSession(game=, state=, agents=)` constructor (Task 5) matches usage in Tasks 4 and 6. `RENDERERS` registry keys (`"tic_tac_toe"`, `"skyjo"`) match `GameSession.game` values. Action encoders referenced (`encode_take_discard_and_replace`, `encode_replace_from_hand`, `encode_discard_and_flip`, `encode_draw_deck`, `decode`, `ActionKind.REVEAL_INITIAL`) all exist in `actions.py`.
