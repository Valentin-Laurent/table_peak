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
