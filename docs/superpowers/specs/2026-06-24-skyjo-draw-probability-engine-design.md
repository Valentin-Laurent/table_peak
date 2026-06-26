# Skyjo Draw-Probability Engine — Design

**Bead:** table_peak-2vs.1 (A. Skyjo draw-probability engine)
**Parent:** table_peak-2vs (Skyjo: heuristic opponent + first learning agent)
**Date:** 2026-06-24

## Goal

A pure function in the Skyjo engine that returns the probability distribution
over the value of the **next card drawn from the deck**, computed only from
information legitimately available to players. Consumed by the heuristic agent
(B, table_peak-2vs.2) and the live odds display in the web UI (C,
table_peak-2vs.3).

## Key decisions

### Draw odds are common knowledge — no `viewer` parameter

In this engine no one sees any face-down value, not even the owner (privacy
model in `view.py` / `observer.py`). The unseen pool is therefore identical for
every player, so the next-draw distribution is common knowledge. The function
takes the state only; there is no per-player variant.

Per-player information (your own revealed cards) matters for the *agent's
decision* in B — which slot to replace — not for the odds themselves. That logic
lives in B, not here.

### Support is the whole unseen pool (exchangeability)

The next card physically comes from the hidden draw pile, but a player cannot
distinguish a draw-pile card from a face-down grid card. By exchangeability the
marginal next-draw is uniform over the entire unseen pool = draw pile + all
face-down grid cells. Buried discards are excluded — they are not drawable until
a recycle, and they fall out automatically by subtracting the full discard pile.

### Input is `SkyjoState`, not `SkyjoPublicView`

The rigorous pool requires the *full* discard pile (perfect recall). `SkyjoState`
exposes `_discard_pile`; `SkyjoPublicView` only carries `discard_top`. Both
consumers have the state server-side (the web layer builds the view *from* the
state), so taking the state costs nothing and keeps the model exact.

## Components

### `draw_odds(state: SkyjoState) -> DrawOdds`

Core, state-dependent, the only place the pool is derived.

```
pool = Counter(DECK_COMPOSITION)            # 150 cards
pool -= every face-up card across all grids
pool -= every card in state._discard_pile   # full pile, not just the top
DrawOdds.pmf[v] = pool[v] / sum(pool.values())
```

- Reads only public fields (face-up values, discard pile). Never reads a
  face-down hidden value — it cannot cheat.
- Invariant (assert in tests): `sum(pool) == draw_pile_size + total_face_down_cells`.
- pmf keys: only values with non-zero probability (−2..12 subset).

### `DrawOdds` value object

Frozen dataclass wrapping the pmf. Every method is a pure function of the pmf and
never sees `state`, so derived stats cannot drift from the distribution.

- `.pmf: Mapping[int, float]` — distribution over the present values.
- `.expected_value() -> float` — Σ v·p(v). Agent compares to the discard top.
- `.prob_at_most(threshold: int) -> float` — Σ_{v ≤ threshold} p(v). The UI and
  agent get "odds the draw beats the discard top" from this.

Convention to pin in implementation: "beats the discard top of value `t`" means
drawing a value strictly less than `t`, i.e. `prob_at_most(t - 1)`. State this in
the docstring so both consumers use it consistently.

Anything beyond these three the agent owns in B.

### Recycle-boundary handling

The formula assumes the next draw comes from the draw pile. When
`draw_pile_size == 0`, the engine instead recycles the discard (minus top) into
the draw pile and draws from that — a different, and actually *known*, support.

**Decision:** at `draw_pile_size == 0`, compute the pmf over the post-recycle
pool — i.e. treat the discard-minus-top as the draw source, matching what
`_recycle_discard_into_deck` followed by a draw physically produces. This is rare
and transient but keeps the odds exact instead of normalizing over a near-empty
pool.

## Placement

New module `src/table_peak/games/skyjo/odds.py`, mirroring `scoring.py` and
`deck.py`. `DrawOdds` and `draw_odds` both live there.

## Testing (black-box)

- Known-pool fixtures → exact expected pmf.
- Invariant `sum(pool) == draw_pile_size + total_face_down_cells` holds across
  representative states.
- `expected_value()` and `prob_at_most()` against hand-computed values.
- Fresh post-deal state: pool = 150 − (2 face-ups × num_players) − 1 discard top.
- Recycle boundary: `draw_pile_size == 0` yields the discard-minus-top
  distribution, not a division over an empty/near-empty pool.

## Out of scope

- Per-player / viewer-relative odds (odds are common knowledge).
- Agent decision logic, slot selection, expectimax (B, table_peak-2vs.2).
- UI rendering of the odds (C, table_peak-2vs.3).
