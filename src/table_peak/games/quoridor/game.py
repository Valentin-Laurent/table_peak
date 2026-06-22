from __future__ import annotations

from typing import Any

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.quoridor.actions import NUM_DISTINCT_ACTIONS
from table_peak.games.quoridor.state import QuoridorState

_GAME_TYPE = pyspiel.GameType(
    short_name="quoridor",
    long_name="Quoridor (Gigamic, 1997)",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=2,
    min_num_players=2,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=False,
    provides_observation_tensor=False,
    parameter_specification={"seed": 0},
)


class QuoridorGame(pyspiel.Game):  # type: ignore[misc]
    def __init__(self, params: dict[str, Any] | None = None):
        params = dict(params or {})
        seed = int(params.get("seed", 0))
        info = pyspiel.GameInfo(
            num_distinct_actions=NUM_DISTINCT_ACTIONS,
            max_chance_outcomes=0,
            num_players=2,
            min_utility=-1.0,
            max_utility=1.0,
            # Nominal cap only: pyspiel treats max_game_length as advisory
            # metadata and does NOT force-terminate. The state terminates solely
            # on a win, so a long game can exceed this. Downstream code that
            # sizes buffers/tensors by max_game_length must treat it as a hint.
            max_game_length=200,
        )
        super().__init__(_GAME_TYPE, info, params)
        self._seed = seed

    def new_initial_state(self) -> QuoridorState:
        return QuoridorState(self, seed=self._seed)


# NOTE: pyspiel ships a builtin "quoridor" game. register_game silently
# OVERWRITES it, so importing this module shadows the builtin. Two consequences:
#   - You MUST import this package before pyspiel.load_game("quoridor", ...);
#     otherwise you hit the builtin (different action space, and {"seed": ...}
#     raises since the builtin's params are board_size/wall_count/etc.).
#   - The wrapper in __init__.py imports-then-loads, so it is always safe.
# test_registration_overrides_pyspiel_builtin guards that the override wins.
pyspiel.register_game(_GAME_TYPE, QuoridorGame)
