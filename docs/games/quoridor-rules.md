# Quoridor — Technical Ruleset

Precise rules specification of Quoridor (Gigamic, 1997; designer Mirko Marchesi) for input to a reinforcement-learning framework. Cross-checked against Gigamic's official English rulebook, the BoardGameGeek Quoridor entry, and community tournament practice. Where the published rules are silent or contradictory, a single interpretation is **chosen** below and flagged with `[CHOSEN]` so the implementation has unambiguous guidance; the underlying ambiguity is preserved in the note.

This document covers the **2-player** game exclusively. The 4-player variant is noted where rules differ but is not the primary specification target.

---

## Overview

Quoridor is a 2-player abstract strategy game played on a 9×9 grid. Each player controls one pawn. On each turn a player either **moves their pawn** one step or **places one wall** from their hand. The first player to move their pawn to any cell on the opponent's starting row wins.

---

## Components

| Item | Quantity |
|------|----------|
| 9×9 game board | 1 |
| Pawns | 2 (one per player) |
| Walls (2-cell-span wooden planks) | 20 total — 10 per player |

Walls occupy the groove between two adjacent cells and span exactly **two grooves** (blocking passage across two cell boundaries at once). A wall is placed horizontally or vertically; it is never diagonal.

---

## Board geometry

The board is a 9×9 grid of cells. Cells are addressed by column (a–i, left to right from Player 1's perspective) and row (1–9, bottom to top). Player 1 starts at **e1**; Player 2 starts at **e9**.

Walls are placed in the interior grooves between cells. Horizontal grooves separate row N from row N+1; vertical grooves separate column X from column X+1. Each wall segment occupies two consecutive grooves on the same axis. Wall positions are addressed by the **top-left corner cell** of the 2×1 (horizontal) or 1×2 (vertical) pair of blocked transitions, plus an orientation letter:

- `e4h` = horizontal wall with its left endpoint between columns e/f at the row-4/row-5 boundary (blocks e4↔e5 and f4↔f5).
- `e4v` = vertical wall with its top endpoint between rows 4/5 at the column-e/column-f boundary (blocks e4↔f4 and e5↔f5).

This notation is consistent with popular community tools (e.g., the `quoridor-py` project). `[CHOSEN]` Gigamic publishes no official notation; chose the top-left-cell convention used by the BGG community and most open-source implementations.

---

## Setup

1. Place the board so each player faces their own baseline row.
2. Player 1 places their pawn on **e1** (center of row 1). Player 2 places their pawn on **e9** (center of row 9).
3. Each player takes **10 walls** from the supply.
4. **First move:** Player 1 moves first. `[CHOSEN]` Gigamic's rulebook grants first move to the youngest player; for implementation purposes Player 1 (index 0) always moves first, with colour/index assignment decided at match creation time.

---

## Turn structure

On each turn the active player performs **exactly one** of the following two actions:

### Action A — Move pawn

The pawn moves to an adjacent cell subject to the rules below (§ Pawn movement). The player's wall count is unchanged.

### Action B — Place wall

The player takes one wall from their hand and places it on the board at a legal position (§ Wall placement). The player's pawn does not move. The wall count decreases by 1.

A player with **zero walls remaining** may only choose Action A. `[CHOSEN]` A player with walls remaining is never forced to place; they may always choose to move instead.

---

## Pawn movement

### Orthogonal step (normal move)

The pawn moves to an **orthogonally adjacent** cell (north, south, east, or west), provided:
- The destination cell is within the board.
- There is no wall blocking the shared boundary between the current cell and the destination.

Diagonal moves are **not** permitted.

### Jump over an adjacent pawn (confrontation)

If the **opponent's pawn occupies a cell orthogonally adjacent** to the active player's pawn, the active player may jump in the **same direction** to the cell directly beyond the opponent, provided:
- That destination cell is within the board.
- No wall blocks the boundary between the opponent's cell and the destination.
- The opponent's pawn is the only pawn in that direction (there are only two pawns, so this is automatically satisfied in 2-player).

#### Lateral jump (blocked straight jump)

If the straight jump is blocked — meaning the destination of the straight jump is either **off the board** or **blocked by a wall** — then instead of jumping straight the active player may jump to **either of the two cells orthogonally adjacent to the opponent** that are perpendicular to the jump direction, provided each such lateral destination:
- Is within the board.
- Has no wall between the opponent's cell and that lateral destination.

The active player chooses which lateral cell to move to. If both lateral cells are legal, either may be chosen. If only one is legal, that is the only option. If neither is legal (both blocked by walls or board edge), the active player cannot jump at all in that direction and must choose a different move. `[CHOSEN]` The rulebook is ambiguous about whether the lateral jump is triggered by "board edge" alone or only by walls; chose that **both** walls and board edge trigger the lateral option, which is the consensus reading on BGG.

#### Summary of jump resolution

```
Opponent is adjacent in direction D?
  YES → Can the pawn land on the cell beyond the opponent (straight jump)?
          YES → Straight jump is legal.
          NO  → (Destination off-board or wall blocks it)
                Is lateral cell L1 (left of D from the jumper's frame) reachable?
                  YES → L1 is a legal destination.
                Is lateral cell L2 (right of D) reachable?
                  YES → L2 is a legal destination.
```

#### No chain-jumping

The active player may jump over **at most one pawn per turn**. After one jump the turn ends regardless of the resulting position. `[CHOSEN]` This is explicit in the 4-player variant; Gigamic's 2-player text implies it by enumerating single-jump cases without chaining. Chose to make no-chain-jump an explicit rule for both variants.

### At least one move must always be legal

A player must always have at least one legal pawn move. If through some extraordinary wall configuration no move exists, that state is treated as illegal (the wall placement that caused it would be rejected — see § Wall placement, path condition). This situation cannot arise from legal play.

---

## Wall placement

A wall placement is **legal** if and only if **all five** of the following conditions hold:

1. **Supply:** the active player has at least one wall remaining.
2. **On-board:** the wall fits entirely within the board's interior grooves (walls cannot span the outer boundary of the board). For a 9×9 board this means column positions a–h and row positions 1–8.
3. **No overlap:** neither of the two groove segments the wall would occupy is already occupied by an existing wall.
4. **No crossing:** a horizontal wall and a vertical wall cannot share their centre point. Concretely, `e4h` and `e4v` cannot both be on the board. `[CHOSEN]` This is the standard "no T-intersection" rule. Two walls of the **same** orientation are forbidden by condition 3 (they would share a groove segment); the crossing condition specifically forbids perpendicular walls whose centre points coincide.
5. **Path condition (connectivity):** after placing the wall, **every player** (both players in 2-player) must still have at least one path of legal pawn moves that can reach their respective goal row. Formally, a BFS/DFS from each player's current pawn cell must be able to reach at least one cell on that player's goal row, using only wall-unblocked orthogonal steps.

If any condition fails the placement is illegal. `[CHOSEN]` The rulebook states "you cannot wall off an opponent completely" but does not explicitly extend this to the active player themselves. Chose to enforce the path condition for **all** players, including the active player, consistent with competitive tournament practice.

---

## Win condition

A player wins immediately when **at the end of their turn** their pawn occupies any cell on their **goal row**:

- Player 1 wins by reaching any cell in row 9 (a9–i9).
- Player 2 wins by reaching any cell in row 1 (a1–i1).

The win is checked after the pawn move resolves. A wall placement cannot directly produce a win.

The game cannot end in a draw under legal play: the path condition guarantees both players always have a route to goal, and pawn movement is unrestricted by supply, so the game always terminates. `[CHOSEN]` No draw rule exists; chose to make this explicit.

---

## Edge cases & ambiguities

**Wall blocking one's own path.** A player is permitted to place a wall that lengthens their own path, provided the path condition is still satisfied (they still have _some_ path to goal). Self-blocking is legal.

**Pawn on goal row at start of opponent's turn.** A player already on their goal row still wins on their own turn only; they must have moved there to trigger the win. `[CHOSEN]` This case cannot arise in practice because the game ends the moment a player reaches the goal at the end of their move. Made explicit for engine completeness.

**Jump when no walls remain.** Jump legality is independent of wall supply; a player with zero walls may still jump over the opponent's pawn using the full jump rules.

**Lateral jump when opponent is at board edge.** If the opponent's pawn is on the board edge directly behind them (e.g., the straight jump would land off the board), the lateral jump is triggered. The lateral cells are the two neighbours of the opponent perpendicular to the jump direction; both must be individually checked against walls and board boundaries.

**Both lateral cells reachable.** The active player freely chooses either. This is a distinct legal move for each reachable lateral cell; the engine must enumerate both as separate actions.

**Zero walls and confrontation.** Even with zero walls in supply, the confrontation/jump rules apply unchanged — walls on the _board_ still restrict movement; having no walls _in hand_ is irrelevant to reading board walls.

**Placing a wall to prevent a 1-step loss.** A player may use their last wall to block the opponent if the placement is legal. There is no restriction on playing walls defensively.

---

## Information structure (for RL modelling)

**Public (common knowledge):** both players observe everything; Quoridor is a **perfect-information** game.

- Active player.
- Both pawn positions.
- All wall positions and orientations on the board.
- Number of walls remaining in each player's hand.
- Full action history.

**Hidden:** nothing. There is no hidden information in Quoridor.

---

## Action space outline

Let the board state be (`p1`, `p2`, `w_placed`, `walls_p1`, `walls_p2`) where `pN` is a cell, `w_placed` is the set of placed walls, and `wallsN` is the count of walls in each player's hand.

### Move actions

From pawn cell `c`, enumerate all cells reachable by the normal-step and jump rules given `p_opponent` and `w_placed`. In the worst case (no opponent adjacent, no walls) this is 4 actions. With confrontation, up to 5 reachable cells are possible (straight jump + two lateral cells + two non-jump orthogonal cells that don't involve the opponent). `[CHOSEN]` Chose the maximum to be 5: the opponent blocks one direct neighbor, the two remaining orthogonal neighbors are still individually reachable if unblocked, and the confrontation contributes up to 2 additional cells (straight + one lateral, or two laterals). Full enumeration is used; the action is `MovePawn(destination_cell)`.

### Wall actions

For each of the 8×8 = 64 horizontal positions and 64 vertical positions, filter by conditions 1–5 above. In an empty game with full supply each player has at most 128 candidate wall placements, but the path condition reduces this. Action is `PlaceWall(position, orientation)` where position is a top-left cell (a–h × 1–8) and orientation ∈ {H, V}.

### Total action space upper bound

128 wall placements + 5 pawn moves = **133 actions** per turn in the worst case. The factual branching factor is lower in most states.
