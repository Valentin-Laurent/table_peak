"""Run the Skyjo open_spiel training feasibility spike and write FINDINGS.md."""

from __future__ import annotations

import pathlib

import table_peak.games.skyjo  # noqa: F401  -- registers the 'skyjo' game
import pyspiel

from spikes.deep_cfr_probe import probe
from spikes.evaluation import measure_episode_lengths
from spikes.payoff import PayoffMode
from spikes.rl_cells import run_dqn_cell, run_nfsp_cell

_CELLS = [
    ("NFSP", PayoffMode.WIN_LOSS, run_nfsp_cell),
    ("NFSP", PayoffMode.SCORE_MARGIN, run_nfsp_cell),
    ("DQN", PayoffMode.WIN_LOSS, run_dqn_cell),
    ("DQN", PayoffMode.SCORE_MARGIN, run_dqn_cell),
]


def main() -> None:
    game = pyspiel.load_game("skyjo", {"num_players": 2})
    lines = ["# Skyjo open_spiel training spike — findings", ""]

    lengths = measure_episode_lengths(game, n_games=200)
    lines.append(
        f"Episode length (random vs random): median {lengths['median']:.0f}, "
        f"max {lengths['max']:.0f} (cap 2000).\n"
    )

    lines.append("## RL cells (signal gate: win-rate > 0.55 vs random)\n")
    lines.append("| Algorithm | Payoff | Win-rate | Mean margin |")
    lines.append("| --- | --- | --- | --- |")
    for name, mode, runner in _CELLS:
        summary = runner(game, mode)
        passed = "PASS" if summary["win_rate"] > 0.55 else "fail"
        lines.append(
            f"| {name} | {mode.value} | {summary['win_rate']:.3f} "
            f"({passed}) | {summary['mean_margin']:+.1f} |"
        )

    verdict = probe(timeout_s=120.0)
    lines.append(
        f"\n## Deep CFR feasibility\n\nVerdict: **{verdict['verdict']}** "
        f"after {verdict['seconds']:.0f}s — {verdict['detail']}\n"
    )

    out = pathlib.Path(__file__).parent / "FINDINGS.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
