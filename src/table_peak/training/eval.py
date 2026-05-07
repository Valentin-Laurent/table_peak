"""Pairwise cross-table evaluation across named agents."""

from __future__ import annotations

from collections.abc import Sequence

from table_peak.agents.base import Agent
from table_peak.games.base import Game
from table_peak.runner.play import MatchStats, play_matches

type EvalTable = dict[tuple[str, str], MatchStats]


def cross_table(
    agents: Sequence[tuple[str, Agent]],
    *,
    game: Game,
    n_per_pair: int,
    seed: int,
) -> EvalTable:
    """For every i < j pair (a_i, a_j), call play_matches with side-swapping.

    Each entry's MatchStats keys are: 0 = a_i, 1 = a_j (per play_matches'
    agent-index convention).
    """
    table: EvalTable = {}
    for i in range(len(agents)):
        name_i, agent_i = agents[i]
        for j in range(i + 1, len(agents)):
            name_j, agent_j = agents[j]
            table[(name_i, name_j)] = play_matches(
                game=game,
                agent_a=agent_i,
                agent_b=agent_j,
                n=n_per_pair,
                swap_sides=True,
                seed=seed + i * 1000 + j,
            )
    return table
