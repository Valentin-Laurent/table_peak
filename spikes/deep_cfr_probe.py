"""Time-boxed feasibility probe for Deep CFR on Skyjo (run in a subprocess)."""

from __future__ import annotations

import subprocess
import sys
import time

# Child program: builds the solver and attempts ONE traversal/iteration.
# Imports table_peak.games.skyjo first so the 'skyjo' game is registered.
_CHILD = (
    "import table_peak.games.skyjo;"
    "import pyspiel;"
    "from open_spiel.python.pytorch import deep_cfr;"
    "g=pyspiel.load_game('skyjo', {'num_players':2});"
    "s=deep_cfr.DeepCFRSolver(g, num_iterations=1, num_traversals=1,"
    " print_nash_convs=False);"
    "s.solve();"
    "print('DEEPCFR_OK')"
)


def probe(timeout_s: float = 120.0) -> dict[str, object]:
    """Returns a verdict dict: completed/timed_out/errored + wall-clock seconds."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, "-c", _CHILD],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "verdict": "timed_out",
            "seconds": timeout_s,
            "detail": f"no single traversal completed within {timeout_s}s",
        }
    elapsed = time.monotonic() - start
    if result.returncode == 0 and "DEEPCFR_OK" in result.stdout:
        return {"verdict": "completed", "seconds": elapsed, "detail": "one iteration ran"}
    return {
        "verdict": "errored",
        "seconds": elapsed,
        "detail": (result.stderr or result.stdout)[-500:],
    }
