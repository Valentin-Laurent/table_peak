"""Game and match runner. Imperative shell over the functional core."""

from __future__ import annotations

import random as _random
from collections.abc import Mapping
from dataclasses import dataclass

from table_peak.agents.base import Agent
from table_peak.games.base import Action, Game, PlayerId, State


@dataclass(frozen=True, slots=True)
class Outcome:
    """Result of a single game."""

    returns: dict[PlayerId, float]
    trajectory: list[tuple[State, Action]]
    num_moves: int


def play_game(game: Game, agents: Mapping[PlayerId, Agent]) -> Outcome:
    """Run one game to completion and return its outcome."""
    if set(agents.keys()) != set(range(game.num_players)):
        raise ValueError(
            f"agents keys {sorted(agents.keys())} must equal "
            f"{list(range(game.num_players))} (game.num_players={game.num_players})"
        )

    state = game.new_initial_state()
    history: list[tuple[State, Action]] = []
    while not state.is_terminal:
        player = state.current_player
        action = agents[player].act(state)
        history.append((state, action))
        state = state.apply_action(action)
    return Outcome(returns=state.returns(), trajectory=history, num_moves=len(history))


@dataclass(frozen=True, slots=True)
class MatchStats:
    """Aggregate statistics over a series of games.

    Keys in `wins` and `mean_returns` are AGENT INDICES, not literal player
    seats: 0 = agent_a, 1 = agent_b. This matters when `swap_sides=True`,
    where each agent plays both P0 and P1 across games. Reading "did agent_a
    beat agent_b" is the common case, so we key by agent identity.
    """

    n_games: int
    wins: dict[PlayerId, int]
    draws: int
    mean_returns: dict[PlayerId, float]


def play_matches(
    game: Game,
    agent_a: Agent,
    agent_b: Agent,
    n: int,
    swap_sides: bool = True,
    seed: int | None = None,
) -> MatchStats:
    """Play `n` games between two agents and aggregate outcomes.

    With swap_sides=True, half the games place agent_a at P0 and half at P1, so
    the reported stats are not biased by first-mover advantage (with odd `n`,
    one direction gets one extra game). Stats are keyed by agent index, not
    literal seat — see `MatchStats` for details.
    """
    if game.num_players != 2:
        raise ValueError("play_matches currently supports only 2-player games")

    rng = _random.Random(seed)

    wins: dict[PlayerId, int] = {0: 0, 1: 0}
    draws = 0
    sum_returns: dict[PlayerId, float] = {0: 0.0, 1: 0.0}

    for i in range(n):
        a_is_p0 = (i % 2 == 0) if swap_sides else True
        if a_is_p0:
            agents: dict[PlayerId, Agent] = {0: agent_a, 1: agent_b}
            agent_seat: dict[int, PlayerId] = {0: 0, 1: 1}
        else:
            agents = {0: agent_b, 1: agent_a}
            agent_seat = {0: 1, 1: 0}

        # Threaded RNG: reserved for future stochastic environments. Touching
        # it now keeps the seed -> outcome mapping stable when chance nodes are
        # added later, so existing seeded tests don't all need re-baselining.
        _ = rng.random()

        outcome = play_game(game, agents)

        a_return = outcome.returns[agent_seat[0]]
        b_return = outcome.returns[agent_seat[1]]
        sum_returns[0] += a_return
        sum_returns[1] += b_return

        if a_return > b_return:
            wins[0] += 1
        elif b_return > a_return:
            wins[1] += 1
        else:
            draws += 1

    mean_returns = {idx: sum_returns[idx] / n for idx in (0, 1)}
    return MatchStats(n_games=n, wins=wins, draws=draws, mean_returns=mean_returns)
