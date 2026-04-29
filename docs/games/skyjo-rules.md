# Skyjo — Technical Ruleset

Precise rules specification of Skyjo (Magilano, 2015) for input to a reinforcement-learning framework. Cross-checked against Magilano's official English rulebook and the BoardGameGeek Skyjo entry. Where the published rules are silent or contradictory, a single interpretation is **chosen** below and flagged with `[CHOSEN]` so the implementation has unambiguous guidance; the underlying ambiguity is preserved in the note.

## Overview

Skyjo is a 2–8 player draft-and-replace card game over multiple rounds. Each player maintains a personal 4×3 grid of 12 cards, partially face-down. On each turn a player either takes the top discard or draws from the deck, and either replaces a grid card or flips a face-down one. The first player to fully reveal their grid triggers round-end; remaining players take one final turn. Round scores accumulate; once any player reaches 100 cumulative points the game ends, and the **lowest** cumulative score wins.

## Components

The deck contains **150 cards**:

| Card value | Copies |
| ---------- | ------ |
| -2         | 5      |
| -1         | 10     |
| 0          | 15     |
| 1          | 10     |
| 2          | 10     |
| 3          | 10     |
| 4          | 10     |
| 5          | 10     |
| 6          | 10     |
| 7          | 10     |
| 8          | 10     |
| 9          | 10     |
| 10         | 10     |
| 11         | 10     |
| 12         | 10     |
| **Total**  | **150** |

0 is most common (15); -2 is rarest (5). All other values have 10 copies. No jokers or wildcards.

## Setup

1. Shuffle all 150 cards into one face-down deck.
2. Deal **12 cards face-down** to each player, arranged in a **4-column × 3-row** grid. Players may not look at them.
3. Place the rest of the deck face-down as the **draw pile**; flip its top card to start the **discard pile**.
4. Each player chooses **exactly 2** of their 12 grid cards (free position) and flips them face-up simultaneously.
5. **Starting player:** highest sum of the two revealed cards; ties broken by a fixed-RNG draw among the tied players. `[CHOSEN]` Magilano specifies the highest sum but not a deterministic tiebreaker — chose RNG-among-tied-players for fairness and reproducibility (a single seed gives deterministic test outcomes).
6. Play proceeds clockwise.

## Turn structure

On their turn, the active player picks exactly one of two mutually exclusive branches.

**Branch (a) — Take the top of the discard pile.**
1. Pick up the top discard (value already public).
2. **Mandatory:** swap it with exactly one card in the player's grid (face-up or face-down). The replaced grid card goes face-up to the discard. The new grid card is face-up.
3. The player **may not** discard the taken card without using it.

**Branch (b) — Draw the top of the deck.**
1. Draw the top card and look at it (value is private to the active player at this instant).
2. Choose one sub-action:
   - **(b1) Replace:** swap the drawn card with exactly one grid card (face-up or face-down). New card goes face-up into the slot; replaced card goes face-up to the discard.
   - **(b2) Discard-and-flip:** place the drawn card face-up on the discard, then flip exactly one **face-down** grid card face-up. **Legal only if the player has ≥1 face-down card.** `[CHOSEN]` Magilano does not explicitly forbid (b2) with no face-down cards remaining, but the action description requires a flip — chose the standard reading: (b2) is illegal when `F = 0` (the player must use (b1) instead).
3. After resolution, the drawn card is public regardless of branch.

Then check column elimination (next section) and play passes clockwise.

## Column elimination rule

When all three cards in any column are simultaneously face-up **and have identical value**, the entire column (3 cards) is removed and placed on the discard, with the just-completed (most recently flipped or placed) card on top. `[CHOSEN]` Magilano does not specify ordering — chose "most-recently-revealed on top" because it preserves a sensible causal chain in the discard history.

**Timing:**
- Check at the **end** of the active player's turn, after the action fully resolves, before passing.
- If multiple columns simultaneously qualify, eliminate all of them.
- Elimination shrinks the grid to 9, 6, or 3 cards (3, 2, or 1 column × 3 rows).
- **Removed cards count as not-face-down for the round-end trigger.** The trigger fires when the player has zero face-down cards left, regardless of grid size.

## End-of-round trigger

The round ends when **any player has zero face-down cards remaining** (the **round-ender**).

- The round-ender's turn ends normally (after column elimination).
- Every other player, in clockwise order from the round-ender's left, takes **exactly one more turn**.
- After the last final turn (and any column elimination on it), the round ends and scoring is performed.

## Scoring

At round end, all face-down cards (if any remain after elimination) are flipped face-up and counted. Per Magilano, **all cards are revealed and summed**.

- Each player's round score = **sum of values of all cards still in their grid**. Eliminated columns contribute 0.
- **Round-ender penalty:** if the round-ender's score is **not strictly the lowest**, their round score is **doubled**.
  - Strictly lower than every other player → no penalty.
  - Any other player ≤ round-ender → doubled.
- A round-ender with a zero or negative score is **still doubled** if not strictly lowest. Doubling a negative makes it more negative (better for the round-ender). `[CHOSEN]` Some house rules cap doubling at zero; the published rule does not — chose literal doubling (matches the published rule).
- **Tie at lowest:** a tie at lowest **does** trigger doubling. `[CHOSEN]` The rulebook says the round-ender must "alone" have the lowest and BGG threads diverge — chose the strict literal reading (doubling triggers on tie).

Round scores add to each player's cumulative total.

## End-of-game

- The game ends at the conclusion of the round in which **at least one player's cumulative score reaches or exceeds 100**.
- Lowest cumulative score wins.
- **Tie at game end:** **shared win** (no tiebreaker round). `[CHOSEN]` Magilano does not specify — chose shared win because it matches the published "lowest cumulative score wins" rule directly with no extra mechanics; the framework can model multi-winner outcomes via the per-player returns dict.
- Reaching exactly 100 ends the game (threshold is "≥ 100").

## Edge cases & ambiguities

- **Deck exhaustion mid-round.** Keep the current discard top aside, shuffle the rest of the discard, place it face-down as the new draw pile, then return the kept top to the discard. `[CHOSEN]` Magilano specifies a reshuffle but not the exact procedure — chose the standard BGG reading because it preserves the public-information property of the discard top across reshuffle boundaries.
- **Column elimination triggering round-end.** If a flip/replacement completes a column of three identical face-up cards, the column is eliminated; if this leaves the player with zero face-down cards, round-end triggers. Trigger is checked **after** elimination resolves.
- **Multiple players reaching 0 face-down on the same turn.** Only the active player acts per turn, so this cannot happen on a single action. During the final-turns phase, a non-ender may also reach 0 face-down via their action; this does **not** retrigger or extend round-end. The round ends after each non-ender has taken exactly one final turn.
- **Multi-way ties at round end.** The round-ender's penalty applies if any non-ender ties them at lowest score. Ties among non-enders do not affect anyone's penalty.
- **Tie at exactly 100 ending the game.** If multiple players cross 100 in the same round, the game still ends after that round; ranking is by cumulative score (with tiebreaker policy above).
- **Replacing a face-up card with an identical value.** Legal. Replaced card goes to discard; new card occupies the slot face-up. Column elimination is re-checked.
- **All face-up at start of own turn.** Impossible — would have triggered round-end on the previous turn.

## Information structure (for RL modelling)

**Public (common knowledge):**
- Current player and turn phase.
- Each player's grid layout (which slots remain after eliminations), face-up/face-down status of each remaining card.
- Values of all face-up cards across all grids.
- Top card of the discard pile.
- Size of the draw pile (values hidden).
- Cumulative scores from prior rounds.
- Public action history.

**Private (active player only, transiently):** during Branch (b), between `DrawDeck` and the chosen sub-action, the drawn card's value is known only to the active player. After the sub-action it is public.

**Hidden from everyone (including the card's owner):**
- Order and contents of the draw pile.
- Values of all face-down grid cards — **including a player's own face-down cards**. Skyjo's defining information property is that a player does **not** know the values of their own unflipped cards until they flip them.
- Order of cards in the discard pile below the top.

Skyjo is therefore a multi-player imperfect-information game with **symmetric** ignorance about one's own unflipped grid cards, plus a transient asymmetric information window during Branch (b).

## Action space outline

Let `i` index the player's currently occupied grid slots (eliminated columns excluded), with `N` = current number of slots and `F` = current number of face-down slots.

- `TakeDiscardAndReplace(i)` — Branch (a), atomic. `N` legal variants.
- `DrawDeck` — Branch (b) root. The active player observes the drawn card value and then must take one of:
  - `ReplaceFromHand(i)` — sub-action (b1). `N` legal variants.
  - `DiscardAndFlip(i)` — sub-action (b2). `i` must be a face-down slot. `F` legal variants; legal only if `F ≥ 1`.

A turn is therefore either a single `TakeDiscardAndReplace(i)`, or `DrawDeck` followed by `ReplaceFromHand(i)` or `DiscardAndFlip(i)`.

For setup, `RevealInitial(i, j)` with `i ≠ j` over the 12 starting slots is each player's simultaneous initial action.

The framework should model the inter-step state in Branch (b) as a separate decision node with the drawn card value in the active player's private information set, so policy networks can condition on it.
