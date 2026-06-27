"""Tests for the Quoridor board renderer (state -> QuoridorBoardView)."""

from __future__ import annotations

import json
from typing import Any

from table_peak.agents.base import Agent
from table_peak.agents.random import RandomAgent
from table_peak.games.base import PlayerId
from table_peak.games.quoridor import QuoridorGameWrapper
from table_peak.games.quoridor import actions as q
from table_peak.games.quoridor.geometry import Cell, Orientation, WallAnchor
from table_peak.web.renderers.quoridor import QuoridorBoardView, render


def _initial() -> Any:
    return QuoridorGameWrapper(seed=0).new_initial_state()


def _human_vs_human() -> dict[PlayerId, Agent | None]:
    return {0: None, 1: None}


def _human_vs_bot() -> dict[PlayerId, Agent | None]:
    return {0: None, 1: RandomAgent()}


def _cell(view: QuoridorBoardView, col: int, row: int) -> Any:
    return next(c for c in view.cells if c.col == col and c.row == row)


def test_initial_view_metadata_and_pawns() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    assert view.partial == "_quoridor_board.html"
    assert view.title == "Quoridor"
    assert view.game_id == "g1"
    assert view.is_terminal is False
    assert len(view.cells) == 81
    # P0 starts at (4,0), P1 at (4,8).
    assert _cell(view, 4, 0).pawn == 0
    assert _cell(view, 4, 8).pawn == 1
    # No other cell is occupied.
    assert sum(1 for c in view.cells if c.pawn is not None) == 2
    # Both players start with 10 walls.
    assert view.walls_p0 == 10
    assert view.walls_p1 == 10


def test_initial_view_status_and_clickable_when_human_to_move() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    # advance_bots guarantees the rendered current player is human; P0 moves first.
    assert view.cells_clickable is True
    assert "Player 1" in view.status


def test_not_clickable_when_current_seat_is_a_bot() -> None:
    # P0 is a bot: render() is pure and must reflect that cells aren't clickable.
    agents: dict[PlayerId, Agent | None] = {0: RandomAgent(), 1: None}
    view = render(_initial(), agents, "g1")
    assert view.cells_clickable is False


def test_terminal_status_reports_winner() -> None:
    # Drive P0 straight up the board to its goal row (8) for a deterministic win.
    # Between P0's moves, P1 idles on row 8 (zigzag col 3↔4) so it never reaches row 0.
    state = _initial()
    for row in range(1, 9):
        state = state.apply_action(q.encode_move(Cell(col=4, row=row)))
        if not state.is_terminal:
            p1_col = 3 if row % 2 == 1 else 4
            state = state.apply_action(q.encode_move(Cell(col=p1_col, row=8)))
    view = render(state, _human_vs_human(), "g1")
    assert view.is_terminal is True
    assert "Player 1" in view.status and "won" in view.status
    assert view.cells_clickable is False


def _parse_walls(view: QuoridorBoardView) -> list[dict[str, Any]]:
    return json.loads(view.legal_walls_json)


def test_initial_legal_walls_payload_decomposes_into_segments() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    walls = _parse_walls(view)
    # A horizontal wall at anchor (0,0) is legal on an empty board.
    h00 = q.encode_wall(WallAnchor(col=0, row=0), Orientation.HORIZONTAL)
    entry = next(w for w in walls if w["action"] == h00)
    assert entry["orientation"] == "h"
    assert {entry["seg_a"], entry["seg_b"]} == {"h-0-0", "h-1-0"}
    # A vertical wall at anchor (0,0) decomposes into stacked v-segments.
    v00 = q.encode_wall(WallAnchor(col=0, row=0), Orientation.VERTICAL)
    ventry = next(w for w in walls if w["action"] == v00)
    assert ventry["orientation"] == "v"
    assert {ventry["seg_a"], ventry["seg_b"]} == {"v-0-0", "v-0-1"}


def test_candidate_segs_are_the_union_of_legal_wall_segments() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    # Both segments of the legal h-wall at anchor (0,0) are clickable candidates.
    assert "h-0-0" in view.candidate_segs
    assert "h-1-0" in view.candidate_segs
    # And both stacked segments of the legal v-wall at anchor (0,0).
    assert "v-0-0" in view.candidate_segs
    assert "v-0-1" in view.candidate_segs


def test_placed_wall_marks_its_segments_and_gap() -> None:
    # P0 places a horizontal wall at anchor (2,3), then read the view.
    state = _initial()
    action = q.encode_wall(WallAnchor(col=2, row=3), Orientation.HORIZONTAL)
    assert action in state.legal_actions()
    state = state.apply_action(action)
    view = render(state, _human_vs_human(), "g1")
    assert view.placed_segs == {"h-2-3", "h-3-3"}
    assert "g-2-3" in view.placed_gaps


def test_no_candidate_walls_when_not_human_turn() -> None:
    agents: dict[PlayerId, Agent | None] = {0: RandomAgent(), 1: None}
    view = render(_initial(), agents, "g1")
    assert view.candidate_segs == frozenset()
    assert _parse_walls(view) == []


def _render_partial(view: QuoridorBoardView) -> str:
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    templates_dir = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "table_peak"
        / "web"
        / "templates"
    )
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    return env.get_template("_quoridor_board.html").render(view=view)


def test_template_renders_board_pawns_and_status() -> None:
    view = render(_initial(), _human_vs_bot(), "g1")
    html = _render_partial(view)
    assert 'id="board"' in html
    assert "Player 1" in html  # status text
    # Pawn disks for both seats appear.
    assert "pawn p0" in html
    assert "pawn p1" in html
    # A legal pawn-move target posts its action via an htmx form. P0 can step to (4,1).
    target = next(c for c in view.cells if c.col == 4 and c.row == 1)
    assert target.is_move_target is True
    assert f'value="{target.move_action}"' in html


def test_template_renders_placed_wall_segments() -> None:
    state = _initial()
    state = state.apply_action(
        q.encode_wall(WallAnchor(col=2, row=3), Orientation.HORIZONTAL)
    )
    view = render(state, _human_vs_human(), "g1")
    html = _render_partial(view)
    # A placed wall renders its segments with the "placed" class. Assert on the
    # rendered class attribute (class="seg placed") rather than the bare substring
    # "placed", which the inline <style> block (.seg.placed { ... }) always emits.
    assert 'class="seg placed"' in html
