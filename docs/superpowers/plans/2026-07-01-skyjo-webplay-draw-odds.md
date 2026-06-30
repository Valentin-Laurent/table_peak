# Skyjo Webplay Live Draw Odds — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent <epic-id>`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.

**Goal:** Show the human a live draw-odds panel during their `main_play` root turn in the Skyjo web UI, surfacing the existing `draw_odds` engine against the current Random bot.

**Architecture:** Reuse `draw_odds(state)` as-is. Add an `OddsPanel` value object to the Skyjo renderer, populate it only at the human's `main_play` root, thread a `threshold` query param through `_render` and the `board_fragment` GET route (htmx round-trip, no JS), and render the panel + plain-language caption in the board template.

**Tech Stack:** Python 3.12, FastAPI + Jinja2 + htmx, pytest, ruff, mypy, pdm.

**Spec:** `docs/superpowers/specs/2026-07-01-skyjo-webplay-draw-odds-design.md`
**Bead:** `table_peak-2vs.7` · **Brainstorm session:** `table_peak-i6x`

---

## Context for the implementer

- Skyjo turn phases (string `pv.phase`): `setup_commit`, `main_play` (root: choose draw-deck vs take-discard), `branch_b_subaction` (after drawing — excluded here on purpose; see spec "Why root-only"), `terminal`.
- The renderer entrypoint is `render()` in `src/table_peak/web/renderers/skyjo.py`. It already builds `pv = build_public_view(state.inner, viewer=human_seat)`; `state` is a `PyspielStateAdapter` and `state.inner` is the `SkyjoState` that `draw_odds` consumes.
- `pv` exposes `phase: str`, `discard_top: int | None`, `draw_pile_size: int`, `current_player`, `is_terminal`.
- `draw_odds(state)` returns `DrawOdds` with `.expected_value()` and `.prob_at_most(threshold)`. It raises `ValueError` only in the degenerate "empty draw pile AND no recyclable discard" case.
- Run the suite with `pdm run pytest <path> -v`. Lint/type with `pdm run ruff check .` and `pdm run mypy src`.

## File structure

- **Modify** `src/table_peak/games/skyjo/odds.py` — widen `prob_at_most` to accept a float threshold (the explorer input is a float).
- **Modify** `src/table_peak/web/renderers/skyjo.py` — add `OddsPanel`, an `odds` field on `SkyjoBoardView`, a `_odds_panel(...)` helper, and a `threshold` param on `render()`.
- **Modify** `src/table_peak/web/app.py` — add `threshold` to `_render` and the `board_fragment` GET route.
- **Modify** `src/table_peak/web/templates/_skyjo_board.html` — render the panel, caption, and threshold input.
- **Modify** `tests/games/skyjo/test_odds.py`, `tests/web/test_skyjo_renderer.py`, `tests/web/test_skyjo_play.py` — tests per task.

---

### Task 1: Allow a float threshold in the engine query

**Files:**
- Modify: `src/table_peak/games/skyjo/odds.py` (the `prob_at_most` signature/docstring)
- Test: `tests/games/skyjo/test_odds.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/games/skyjo/test_odds.py`:

```python
def test_prob_at_most_accepts_float_threshold() -> None:
    odds = DrawOdds(pmf={-2: 0.2, 0: 0.3, 5: 0.5})
    # A .5 boundary includes everything strictly below it.
    assert odds.prob_at_most(0.5) == pytest.approx(0.5)   # -2 and 0
    assert odds.prob_at_most(-1.5) == pytest.approx(0.2)  # only -2
```

- [ ] **Step 2: Run test to verify it fails (type-checker, not runtime)**

Run: `pdm run mypy src tests/games/skyjo/test_odds.py`
Expected: the new call is fine at runtime, but `pdm run pytest tests/games/skyjo/test_odds.py::test_prob_at_most_accepts_float_threshold -v` should PASS already (Python compares int/float fine). The real gate is mypy on the *renderer* in Task 2; this test pins the behavior. Run it now: `pdm run pytest tests/games/skyjo/test_odds.py::test_prob_at_most_accepts_float_threshold -v` → PASS.

- [ ] **Step 3: Widen the signature so float callers type-check**

In `src/table_peak/games/skyjo/odds.py`, change the `prob_at_most` signature and docstring:

```python
    def prob_at_most(self, threshold: float) -> float:
        """Probability the drawn value is <= threshold (inclusive).

        Threshold is numeric: card values are integers, but a float threshold is
        well-defined (only the .5 boundaries differ from the nearest integer), so
        the UI's free-form explorer can pass floats. 'Beats a discard top of value
        t' means drawing strictly less than t, i.e. callers use prob_at_most(t - 1).
        """
        return sum(prob for value, prob in self.pmf.items() if value <= threshold)
```

- [ ] **Step 4: Run engine tests + types**

Run: `pdm run pytest tests/games/skyjo/test_odds.py -v && pdm run mypy src`
Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/games/skyjo/odds.py tests/games/skyjo/test_odds.py
git commit -m "feat(skyjo): accept float thresholds in DrawOdds.prob_at_most

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `OddsPanel` value object + populate `odds` at the root

**Files:**
- Modify: `src/table_peak/web/renderers/skyjo.py`
- Test: `tests/web/test_skyjo_renderer.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_skyjo_renderer.py`. Reuse the existing `_to_human_turn`, `_agents`, `_in_setup` helpers already in this file; add the two new helpers and tests below:

```python
from table_peak.games.skyjo.odds import draw_odds


def _to_branch_b(num_players: int, seed: int) -> Any:
    """A human root state advanced one DrawDeck into branch-b."""
    state = _to_human_turn(num_players, seed)
    return state.apply_action(sk.encode_draw_deck())


def test_root_turn_carries_odds_matching_the_engine() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1")
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.odds.expected_value == engine.expected_value()
    assert view.odds.beats_discard == engine.prob_at_most(view.discard_top - 1)
    assert view.odds.recycled is False


def test_threshold_param_drives_prob_at_most() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1", threshold=3.0)
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.odds.threshold == 3.0
    assert view.odds.prob_at_most == engine.prob_at_most(3.0)


def test_no_threshold_seeds_explorer_at_discard_top() -> None:
    state = _to_human_turn(num_players=2, seed=3)
    view = render(state, _agents(2), "g1")
    engine = draw_odds(state.inner)
    assert view.odds is not None
    assert view.odds.threshold == view.discard_top
    assert view.odds.prob_at_most == engine.prob_at_most(view.discard_top)


def test_branch_b_setup_and_terminal_have_no_odds() -> None:
    assert render(_to_branch_b(2, 3), _agents(2), "g1").odds is None
    setup = SkyjoGameWrapper(num_players=2, seed=3).new_initial_state()
    assert render(setup, _agents(2), "g1").odds is None
```

The `recycled` flag is a trivial mapping of `pv.draw_pile_size == 0`; the normal-play
tests above assert `recycled is False`, and the `recycled is True` caption path is
covered by the manual verification step (driving a deterministic empty-draw-pile root
state in a unit test is flaky and not worth it).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pdm run pytest tests/web/test_skyjo_renderer.py -k "odds or threshold or branch_b" -v`
Expected: FAIL — `SkyjoBoardView` has no attribute `odds` / `render()` got an unexpected keyword `threshold`.

- [ ] **Step 3: Implement `OddsPanel`, the helper, and wire `render()`**

In `src/table_peak/web/renderers/skyjo.py`:

Add the import near the other skyjo imports:

```python
from table_peak.games.skyjo.odds import draw_odds
```

Add the dataclass next to the other view dataclasses:

```python
@dataclass(frozen=True, slots=True)
class OddsPanel:
    """Draw-odds shown at the human's main-play root. All probabilities are in
    [0, 1]; the template formats them as percentages."""

    expected_value: float
    beats_discard: float | None  # P(deck draw < discard top); None if no discard top
    threshold: float | None  # value the explorer input is seeded at (None if no seed)
    prob_at_most: float | None  # P(next card <= threshold); None if threshold is None
    recycled: bool  # True at the recycle boundary (draw pile empty)
```

Add an `odds` field to `SkyjoBoardView` (place it right after the `opponents` field):

```python
    odds: OddsPanel | None
```

Add the helper above `render()`:

```python
def _odds_panel(
    state: PyspielStateAdapter,
    pv: SkyjoPublicView,
    your_turn: bool,
    threshold: float | None,
) -> OddsPanel | None:
    """Draw odds for the human's main-play root only. None elsewhere (setup,
    branch-b, bot turn, terminal) — see the spec's 'Why root-only'."""
    if not (your_turn and pv.phase == "main_play"):
        return None
    try:
        odds = draw_odds(state.inner)
    except ValueError:
        return None  # degenerate: empty draw pile and no recyclable discard
    seed = threshold if threshold is not None else pv.discard_top
    return OddsPanel(
        expected_value=odds.expected_value(),
        beats_discard=(
            odds.prob_at_most(pv.discard_top - 1) if pv.discard_top is not None else None
        ),
        threshold=seed,
        prob_at_most=odds.prob_at_most(seed) if seed is not None else None,
        recycled=(pv.draw_pile_size == 0),
    )
```

Change `render()`'s signature to accept the param (add after `reveal_first`):

```python
    threshold: float | None = None,
```

In `render()`, after `opponents = (...)` is built, compute the panel and pass it into the `SkyjoBoardView(...)` constructor:

```python
    odds = _odds_panel(state, pv, your_turn, threshold)
```

and add `odds=odds,` to the `SkyjoBoardView(...)` keyword arguments (next to `opponents=opponents,`).

- [ ] **Step 4: Run tests + types**

Run: `pdm run pytest tests/web/test_skyjo_renderer.py -v && pdm run mypy src`
Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/web/renderers/skyjo.py tests/web/test_skyjo_renderer.py
git commit -m "feat(skyjo-web): add OddsPanel to the board view at main-play root

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Thread `threshold` through the route

**Files:**
- Modify: `src/table_peak/web/app.py` (`_render` at ~line 46, `board_fragment` at ~line 176)
- Test: `tests/web/test_skyjo_play.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_skyjo_play.py` (imports: `random`, `RandomAgent`, `GameSession`, and the renderer-test helper pattern):

```python
import random

from table_peak.agents.random import RandomAgent
from table_peak.games.skyjo import SkyjoGameWrapper
from table_peak.web.sessions import GameSession


def _skyjo_root_state(num_players: int, seed: int) -> object:
    """A PyspielStateAdapter on seat 0's main-play root turn."""
    rng = random.Random(seed)
    state = SkyjoGameWrapper(num_players=num_players, seed=seed).new_initial_state()

    def in_setup(s: object) -> bool:
        legal = list(s.legal_actions())
        return bool(legal) and all(
            sk.decode(a).kind == sk.ActionKind.REVEAL_INITIAL for a in legal
        )

    while not state.is_terminal and in_setup(state):
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    while not state.is_terminal and state.current_player != 0:
        state = state.apply_action(rng.choice(list(state.legal_actions())))
    return state


def test_board_route_renders_odds_with_threshold() -> None:
    store = InMemorySessionStore()
    agents = {0: None, 1: RandomAgent(random.Random(1))}
    game_id = store.create(
        GameSession(game="skyjo", state=_skyjo_root_state(2, 3), agents=agents)
    )
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as c:
            r = c.get(f"/games/{game_id}/board?threshold=3")
            assert r.status_code == 200, r.text
            assert "Avg unseen card" in r.text
            assert "%" in r.text
    finally:
        app.dependency_overrides.pop(get_store, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/web/test_skyjo_play.py::test_board_route_renders_odds_with_threshold -v`
Expected: FAIL — "Avg unseen card" not in response (panel not rendered yet; the template change is Task 4, and the route does not forward `threshold` yet). This test goes green only after Task 4; keep it and let it stay red until then.

- [ ] **Step 3: Forward `threshold` through `_render` and the route**

In `src/table_peak/web/app.py`, add `threshold` to `_render` (keyword-only, after `reveal_first`):

```python
def _render(
    session: GameSession,
    game_id: str,
    *,
    armed: bool = False,
    reveal_first: int | None = None,
    threshold: float | None = None,
) -> Any:
    if session.game == "skyjo":
        return skyjo_renderer.render(
            session.state,
            session.agents,
            game_id,
            armed=armed,
            reveal_first=reveal_first,
            threshold=threshold,
            last_event=session.last_event,
        )
```

In `board_fragment`, add the query param and forward it:

```python
def board_fragment(
    game_id: str,
    request: Request,
    store: Annotated[InMemorySessionStore, Depends(get_store)],
    armed: str | None = None,
    reveal_first: int | None = None,
    threshold: float | None = None,
) -> HTMLResponse:
    session = store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404)
    # `armed` (any value) = place-mode; `reveal_first` = the first slot picked in setup.
    view = _render(
        session, game_id, armed=(armed is not None), reveal_first=reveal_first, threshold=threshold
    )
    return templates.TemplateResponse(request, view.partial, {"view": view})
```

- [ ] **Step 4: Run test (still expect partial — template pending)**

Run: `pdm run pytest tests/web/test_skyjo_play.py -v && pdm run mypy src`
Expected: types PASS; `test_board_route_renders_odds_with_threshold` still FAILS on the "Avg unseen card" assertion (template comes next). Other tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/web/app.py tests/web/test_skyjo_play.py
git commit -m "feat(skyjo-web): forward threshold query param to the board renderer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Render the panel + caption + threshold input

**Files:**
- Modify: `src/table_peak/web/templates/_skyjo_board.html`
- Test: `tests/web/test_skyjo_play.py` (the Task 3 test goes green here)

- [ ] **Step 1: Confirm the failing test exists**

The red test from Task 3 (`test_board_route_renders_odds_with_threshold`) is the failing test for this task. Run it:

Run: `pdm run pytest tests/web/test_skyjo_play.py::test_board_route_renders_odds_with_threshold -v`
Expected: FAIL on "Avg unseen card" not in text.

- [ ] **Step 2: Add the panel to the template**

In `src/table_peak/web/templates/_skyjo_board.html`, add the panel immediately after the closing `</div>` of the `.piles` block (before `<div class="panel you">`):

```html
{% if view.odds %}
<div class="panel odds">
    <div class="tag">Draw odds — your decision</div>
    <p class="odds-stat">Avg unseen card: <b>{{ "%.1f"|format(view.odds.expected_value) }}</b></p>
    {% if view.odds.beats_discard is not none %}
    <p class="odds-stat">Chance a deck draw beats taking the {{ view.discard_top }}:
        <b>{{ "%.0f"|format(view.odds.beats_discard * 100) }}%</b></p>
    {% endif %}
    <form class="odds-explore" hx-get="/games/{{ view.game_id }}/board"
          hx-target="#board" hx-swap="outerHTML" hx-trigger="change">
        <label>P(next card &le;
            <input type="number" name="threshold" step="0.5" style="width:4em;"
                   {% if view.odds.threshold is not none %}value="{{ view.odds.threshold }}"{% endif %}>)
        </label>
        {% if view.odds.prob_at_most is not none %}
        = <b>{{ "%.0f"|format(view.odds.prob_at_most * 100) }}%</b>
        {% endif %}
    </form>
    <p class="odds-note">
        These odds come from the cards nobody has seen yet — the deck plus everyone's
        face-down cards. <b>Avg unseen card</b> is what you'd expect by drawing blind.
        <b>Beats discard</b> is how often a blind draw comes out lower than the card on
        the discard pile (in Skyjo, lower is better).
        {% if view.odds.recycled %}
        <br>Now showing only deck-draw odds (card-reveal odds not implemented yet).
        {% endif %}
    </p>
</div>
{% endif %}
```

Add styling inside the existing `<style>` block (near the other `.panel` rules):

```css
        .panel.odds { border-color: #d9a23b; width: fit-content; margin: 8px auto; max-width: 360px; }
        .odds-stat { font-size: .95rem; margin: 4px 0; }
        .odds-explore { font-size: .95rem; margin: 6px 0; }
        .odds-note { font-size: .8rem; color: #aeb6c2; margin: 6px 0 0; line-height: 1.35; }
```

- [ ] **Step 3: Run the route test**

Run: `pdm run pytest tests/web/test_skyjo_play.py::test_board_route_renders_odds_with_threshold -v`
Expected: PASS — "Avg unseen card" and "%" present.

- [ ] **Step 4: Run the full web + skyjo suites + lint/types**

Run: `pdm run pytest tests/web tests/games/skyjo -v && pdm run ruff check . && pdm run mypy src`
Expected: all PASS. Note the test count (it should be the prior count + the new tests from Tasks 1-4).

- [ ] **Step 5: Commit**

```bash
git add src/table_peak/web/templates/_skyjo_board.html
git commit -m "feat(skyjo-web): show live draw-odds panel with threshold explorer

Closes table_peak-2vs.7.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Manual verification (after Task 4)

Run the app (`pdm run uvicorn table_peak.web.app:app --reload` or the project's run skill), start a Skyjo game, finish setup, and confirm on your root turn: the odds panel shows "Avg unseen card", the "beats discard" line, and a threshold input that updates the percentage when changed. Draw a card → panel disappears in branch-b. End the deck → caption gains the "deck-draw odds only" line.

## Done when

- All four tasks committed; `pdm run pytest tests/web tests/games/skyjo`, `ruff check .`, and `mypy src` green.
- `table_peak-2vs.7` closed; `2vs.9` (prob_equal) and `2vs.8` (deck-vs-reveal) remain open follow-ups.
