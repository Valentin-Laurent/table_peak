# src/table_peak/games/skyjo/game.py
"""SkyjoGame -- pyspiel.Game subclass + GameType + GameInfo + registration."""

from __future__ import annotations

from typing import Any

import pyspiel  # type: ignore[import-not-found]

from table_peak.games.skyjo.actions import NUM_DISTINCT_ACTIONS
from table_peak.games.skyjo.state import SkyjoState

_GAME_TYPE = pyspiel.GameType(
    short_name="skyjo",
    long_name="Skyjo (Magilano, 2015)",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=8,
    min_num_players=2,
    provides_information_state_string=True,
    provides_information_state_tensor=True,
    provides_observation_string=True,
    provides_observation_tensor=True,
    parameter_specification={
        "num_players": 2,
        "seed": 0,
    },
)


class SkyjoGame(pyspiel.Game):  # type: ignore[misc]
    def __init__(self, params: dict[str, Any] | None = None):
        params = dict(params or {})
        num_players = int(params.get("num_players", 2))
        seed = int(params.get("seed", 0))
        if not 2 <= num_players <= 8:
            raise ValueError(f"num_players={num_players} out of [2, 8]")
        # Theoretical bounds for round score after doubling. Worst case: all 12s, doubled.
        max_score = 12 * 12 * 2  # very loose upper bound, fine for pyspiel utility bounds
        min_score = -2 * 12 * 2
        info = pyspiel.GameInfo(
            num_distinct_actions=NUM_DISTINCT_ACTIONS,
            max_chance_outcomes=15,  # 15 distinct card values in the deck
            num_players=num_players,
            min_utility=-float(max_score),
            max_utility=-float(min_score),
            max_game_length=2000,
        )
        super().__init__(_GAME_TYPE, info, params)
        self._num_players = num_players
        self._seed = seed

    def new_initial_state(self) -> SkyjoState:
        return SkyjoState(self, num_players=self._num_players, seed=self._seed)

    def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> Any:
        from table_peak.games.skyjo.observer import SkyjoObserver

        return SkyjoObserver(num_players=self._num_players)

    def information_state_tensor_shape(self) -> list[int]:
        from table_peak.games.skyjo.observer import tensor_size

        return [tensor_size(self._num_players)]

    def observation_tensor_shape(self) -> list[int]:
        from table_peak.games.skyjo.observer import tensor_size

        return [tensor_size(self._num_players)]


pyspiel.register_game(_GAME_TYPE, SkyjoGame)
