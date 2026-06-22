"""Quoridor engine -- registers `quoridor` with open_spiel on import."""

from __future__ import annotations

import pyspiel  # type: ignore[import-not-found]

from table_peak.games._pyspiel_adapter import PyspielGameAdapter
from table_peak.games.quoridor import game as _game  # noqa: F401


def QuoridorGameWrapper(seed: int = 0) -> PyspielGameAdapter:
    inner = pyspiel.load_game("quoridor", {"seed": seed})
    return PyspielGameAdapter(inner, seed=seed)
