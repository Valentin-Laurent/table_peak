# table_peak

Game-playing agents for tabletop games.

This project is vibe-researched and vibe-coded, mostly using Claude
Code and the [superpowers](https://github.com/obra/superpowers) plugin. It
draws on patterns from open RL / game-AI work; I've tried to follow license
rules for anything reused — please open an issue if you spot an attribution
gap.

Project goals:
 - explore strategies for the games included
 - surface balance suggestions for game designers
 - refine my agentic coding setup for greenfield projects

## Roadmap

In progress: see [`docs/superpowers/in-flight.md`](docs/superpowers/in-flight.md)

Next: who knows?

**Suggest a game** — game designers and creators, please open an issue with
the rules and player count; I'd love to add more games.

## Quickstart

Requires Python ≥3.12 and [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest -m "not slow"
uv run uvicorn table_peak.web.app:app --reload
```

Open <http://localhost:8000/> to play TicTacToe against a trained agent. The
training entry point is `table_peak.training.loop.train`.

## Development

Tooling: `uv`, `ruff`, `mypy --strict`, `pytest`, `pre-commit` — config in
[`pyproject.toml`](pyproject.toml) and
[`.pre-commit-config.yaml`](.pre-commit-config.yaml). Work follows the
superpowers workflow (brainstorm → spec → plan → implement) under
[`docs/superpowers/`](docs/superpowers/).

## License

MIT — see [`LICENSE`](LICENSE). The `Game` / `State` shape is conceptually
modelled on [open_spiel](https://github.com/google-deepmind/open_spiel)
(noted in `src/table_peak/games/base.py`). Open an issue for any attribution
gap.
