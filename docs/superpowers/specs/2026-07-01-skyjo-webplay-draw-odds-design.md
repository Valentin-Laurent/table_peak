# Skyjo Webplay — Live Draw Odds Display (Design)

**Bead:** `table_peak-2vs.7` · **Brainstorm session:** `table_peak-i6x`
**Date:** 2026-07-01

## Goal

Let a human *feel* the draw-probability engine while playing Skyjo in the web UI
against the current Random bot. Surface the existing `draw_odds(state)` engine as
an on-board panel during the human's turn — no heuristic agent needed (that is the
separate, still-blocked `2vs.3`).

## Scope

Reuse the engine as-is (`src/table_peak/games/skyjo/odds.py`). No new engine work.
The change is a renderer + route + template addition that shows an **odds panel**
near the draw/discard piles, visible only when it is the human's turn at the
`main_play` **root** (before any card is drawn).

**Why root-only (not branch-b):** once you draw from the deck you enter
`branch_b_subaction`, where the engine is out of contract — `draw_odds` is
defined as "the next deck draw," which no longer happens that turn, and its
`_unseen_pool` still counts the card now in your hand (it subtracts face-up grid
and discard, but not `_drawn_card`), so the numbers would be off by one. The root
is the only place the draw-vs-take-discard decision lives and the pool math is
exact. The branch-b "what a flip reveals" case is a genuinely different
distribution, deferred to `2vs.8`.

The panel shows three things:

1. **Expected next unseen card** — `odds.expected_value()`. Framed as
   *"Avg unseen card: 5.1"*.
2. **Deck beats discard** — when a discard top is present:
   `odds.prob_at_most(discard_top - 1)`, framed as
   *"Chance a deck draw beats taking the {top}: 62%"*.
3. **Threshold explorer** — a number input (float allowed). On change it
   htmx-GETs the board with `?threshold=t`; the server renders
   `odds.prob_at_most(t)` as *"P(next card ≤ t): …%"*. The input is pre-filled
   with `discard_top` so it starts on a meaningful value.

A plain-language caption sits under the panel (see Caption below).

### Out of scope (filed as follow-ups)

- **`table_peak-2vs.9` (P1)** — `prob_equal(value)` for column-clearing (its own
  engine method + UI). Depends on this panel.
- **`table_peak-2vs.8` (P3)** — distinguishing deck-draw odds from
  face-down-reveal odds at the recycle boundary (super-human agent concern).

## Why the panel maps to one real decision

In normal play (draw pile non-empty) the engine builds one unseen multiset
`M = draw pile ∪ all face-down grid cells` and returns the uniform distribution
over it. By exchangeability every unseen card shares that marginal — the top of
the deck and any face-down cell alike. So `expected_value()` is the mean of *any*
single unseen card (a deck draw **or** a face-down flip), and the panel's numbers
inform the one real choice at the root: **draw blind from the deck vs. take the
known discard top.**

## Architecture & data flow

No new modules. Three touch points:

- **`web/renderers/skyjo.py`** — `render()` already holds `state`. Add a
  `threshold: float | None = None` parameter. When the panel is active, call
  `draw_odds(state.inner)` once and populate a new frozen `OddsPanel` dataclass:
  `expected_value: float`, `beats_discard: float | None`,
  `threshold: float | None`, `prob_at_most: float | None`,
  `recycled: bool`. Add an `odds: OddsPanel | None` field to `SkyjoBoardView`
  (None unless it is the human's `main_play` root turn). The view dataclass stays the
  single source the template reads; the caption text is composed in the template
  (or a helper) from these fields.
- **`web/app.py`** — add `threshold: float | None = None` to `_render` (line 46)
  and to the `board_fragment` GET route (line 176); pass straight through to the
  renderer. Parallel to the existing `armed` / `reveal_first` params. The POST
  `/move` and `/next` paths do not pass `threshold`, so it naturally resets after
  any real action — the explorer is ephemeral per view.
- **`templates/_skyjo_board.html`** — render `view.odds` (when not None) as a
  panel beside the `.piles` block, reusing the existing card/tag CSS. The
  threshold input is a tiny form: `hx-get="/games/{id}/board?threshold=…"`,
  `hx-target="#board"`, `hx-swap="outerHTML"`, `hx-trigger="change"`.

## Threshold explorer mechanics

The input re-renders the whole `#board` on `change` via htmx — **no custom JS**,
no JS reimplementation of `prob_at_most` (avoids engine drift). The slightly
clunky full re-render is accepted. The server recomputes `draw_odds` (cheap,
pure) and formats the probability. The threshold persists only for that render;
the next move clears it.

## Edge cases & framing

- **Recycle boundary (draw pile empty):** the engine already returns the
  recycled-discard distribution. The panel still shows correct *deck-draw*
  numbers; we do not claim they equal a face-down reveal. The caption switches to
  an explicit note (see below). The deeper deck/reveal split is deferred to
  `2vs.8`.
- **branch-b / setup / bot turn / terminal:** no panel (`odds = None`). branch-b
  is excluded on purpose — see "Why root-only" above.
- **No discard top** (empty discard, rare): "beats discard" line omitted; EV +
  explorer still show.

## Caption (the plain-language note)

Always shown:

> These odds come from the cards nobody has seen yet — the deck plus everyone's
> face-down cards. **Avg unseen card** is what you'd expect by drawing blind.
> **Beats discard** is how often a blind draw comes out lower than the card on the
> discard pile (in Skyjo, lower is better).

Appended **only after reshuffle** (draw pile empty, `recycled = True`):

> Now showing only deck-draw odds (card-reveal odds not implemented yet).

## Testing (black-box, against the view)

Extend `tests/web/test_skyjo_renderer.py`:

- Human at `main_play` root → `view.odds` present; `expected_value` and
  `beats_discard` match `draw_odds(state).expected_value()` /
  `prob_at_most(top - 1)` (assert against the engine, not hard-coded numbers).
- `threshold=t` passed → `view.odds.prob_at_most == draw_odds(state).prob_at_most(t)`.
- Bot turn / setup / branch-b / terminal → `view.odds is None`.
- Recycle boundary (driven to empty draw pile) → `view.odds.recycled is True`.

Route-level (in `tests/web/test_skyjo_play.py` or the app test): GET
`/board?threshold=3` renders without error and the probability text appears.
