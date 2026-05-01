"""Registry mapping the names exposed in the new-game form to Agent factories.

`Human` is intentionally absent: it's mapped to `None` by the route handler,
because humans don't go through the `Agent` Protocol in this design.
"""

from __future__ import annotations

from collections.abc import Callable

from table_peak.agents.base import Agent
from table_peak.agents.minimax import MinimaxAgent
from table_peak.agents.random import RandomAgent

AGENT_REGISTRY: dict[str, Callable[[], Agent]] = {
    "Random": lambda: RandomAgent(),
    "Minimax": lambda: MinimaxAgent(),
}
