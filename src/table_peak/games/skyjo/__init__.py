"""Skyjo engine -- registers `skyjo` with open_spiel on import.

Public surface:
  - SkyjoGameWrapper(num_players, seed): a PyspielGameAdapter ready for runner.play_game.
"""

from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

from table_peak.games._pyspiel_adapter import PyspielGameAdapter
from table_peak.games.skyjo import game as _game  # noqa: F401  registration side-effect


def SkyjoGameWrapper(num_players: int = 2, seed: int = 0) -> PyspielGameAdapter:
    """Load the registered `skyjo` game and wrap it as our State Protocol adapter."""
    inner = pyspiel.load_game("skyjo", {"num_players": num_players, "seed": seed})
    return PyspielGameAdapter(inner, seed=seed)
