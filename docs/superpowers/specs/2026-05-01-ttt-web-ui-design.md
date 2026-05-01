# Tic-Tac-Toe Web UI — Design

**Date:** 2026-05-01
**Status:** Draft, awaiting user review

## Goal

Add a locally-run web UI that lets a human play tic-tac-toe in a browser against any registered agent (Random, Minimax) — and watch agent-vs-agent. This is the first driving adapter for `table_peak` and validates the pattern that will scale to Skyjo and the other partial-information card games on the long-arc target.

## Non-goals

- No persistence across restarts (sessions live in process memory).
- No authentication or multi-user isolation beyond opaque game ids.
- No WebSocket / SSE / spectator live updates (request/response only).
- No multi-tab partial-information gating (TTT is full info).
- No renderer for any other game; pattern is set up to accept them, not implementing them.
- No visualization of agent internals (minimax tree, action probabilities).
- No public-deployment hardening (CSRF, rate limits, TLS).
- No new agents or game changes — purely additive driving adapter.

## Context

`table_peak` v1 ships a functional core / imperative shell architecture: `Game` / `State` / `Agent` Protocols (PEP 544), a `TicTacToe` implementation, two agents (`RandomAgent`, `MinimaxAgent`), and a sync `play_game` / `play_matches` runner. Today, pytest is the only driver. This work adds the first **web** driving adapter without changing the domain or the existing runner.

The codebase is already hexagonal in spirit:

| Hex layer | Existing location |
|---|---|
| Domain | `games/tic_tac_toe.py`, `games/base.py` |
| Application (use case) | `runner/play.py` |
| Driven port | `agents/base.py` (`Agent` Protocol) |
| Driven adapters | `agents/random.py`, `agents/minimax.py` |
| Driving adapters | (none — pytest implicit) |

This work adds a driving adapter only. No rename or restructure of existing modules.

## Architecture

### Driver model — Option Y: web drives the loop

The web layer keeps `dict[GameId, GameSession]` in process memory. Each HTTP request that advances state runs a small step loop directly:

```python
def advance_bots(session: GameSession) -> None:
    while not session.state.is_terminal:
        seat = session.state.current_player
        agent = session.agents[seat]
        if agent is None:        # human seat — stop, wait for HTTP
            return
        action = agent.act(session.state)
        session.state = session.state.apply_action(action)
```

There is **no `HumanAgent` class**. Humans don't go through the `Agent` Protocol; the web adapter applies human actions directly via `state.apply_action(cell)`. Bots remain `Agent` implementations and are called normally.

`runner/play.py` is untouched. Bot-vs-bot self-play and any future training continue to use it.

**Why Option Y over a blocking `HumanAgent` in a worker thread:** keeping `play_game` shape forced threads + queues + per-session lifecycle (cleanup on tab-close, leaked workers, debugging across thread boundaries). Y is plain request/response: state is a value in a dict, every HTTP call is self-contained, and persistence/replay/branching become trivial later. The "duplication" of a small step loop is worth it.

### Stack

| Layer | Choice | Why |
|---|---|---|
| HTTP server | FastAPI + Uvicorn | mypy-strict friendly, built-in TestClient, free OpenAPI for the larger Skyjo API later |
| Templating | Jinja2 (FastAPI default) | server-rendered HTML, no JS framework to maintain |
| Frontend | HTMX from CDN | declarative attributes on HTML; click → POST → server returns fragment → HTMX swaps it. Zero JS to write or test. |
| Test client | FastAPI `TestClient` (via `httpx`) | sync, in-process, exercises the full FastAPI stack without a real server |

New deps:
- runtime: `fastapi`, `uvicorn[standard]`, `jinja2`
- dev: `httpx`

HTMX is loaded from a CDN `<script>` tag — no Python dep, no bundling.

### File layout

```
src/table_peak/web/
├── __init__.py
├── app.py              # FastAPI app + route handlers
├── sessions.py         # GameSession dataclass + InMemorySessionStore + advance_bots
├── agents.py           # AGENT_REGISTRY: name → Agent factory
├── renderers/
│   ├── __init__.py
│   └── tic_tac_toe.py  # state → BoardView (cells, status, cells_clickable, game_id)
└── templates/
    ├── new_game.html
    ├── game.html
    └── _board.html

tests/web/
├── __init__.py
├── test_sessions.py    # GameSession + store + advance_bots (8 tests)
├── test_agents.py      # AGENT_REGISTRY (4 tests)
├── test_renderer.py    # render() (7 tests)
└── test_app.py         # routes via FastAPI TestClient (12 tests)
```

`renderers/` is a dispatch point for future games. For v1 it has only `tic_tac_toe.py`. When Skyjo arrives, it gets a sibling module; no changes required to `app.py` beyond mounting another route group.

CSS is inlined in `new_game.html` and `game.html` for v1 — no `static/` mount, no `StaticFiles` dependency. If styling grows beyond a handful of selectors, extract to `static/style.css` and mount via `StaticFiles`.

## Data flow

### Routes

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/` | Render `new_game.html` with X-agent and O-agent dropdowns. Options: `Human`, `Random`, `Minimax`. |
| `POST` | `/games` | Form fields `x_agent`, `o_agent`. Create `GameSession`, store under random `game_id`, redirect (303) to `GET /games/{id}`. **Seat mapping:** X = `PlayerId 0` (moves first, matching `TicTacToeState`'s default `_current_player=0`), O = `PlayerId 1`. |
| `GET` | `/games/{id}` | Load session (404 if unknown). If not terminal and current seat is a bot, run `advance_bots(session)`. Save. Render `game.html`. |
| `POST` | `/games/{id}/move` | Form field `cell` (int 0..8). Load session (404). If terminal → 409. If current seat is not human → 409. If `cell` not in `state.legal_actions()` → 400. Apply, then `advance_bots`. Save. Return `_board.html` fragment (HTMX target). |

Game ids are `secrets.token_urlsafe(8)`. Sufficient to share a URL on the same machine; not for public deployment.

### `GameSession`

```python
@dataclass
class GameSession:
    state: TicTacToeState
    agents: dict[PlayerId, Agent | None]  # None = human seat
```

Mutable: each route handler mutates `session.state` in place (since `TicTacToeState` itself is frozen, mutation is via reassignment). Concurrency is single-threaded per Uvicorn worker; we run one worker for v1 and rely on FastAPI's per-request handler isolation. No locking.

### `InMemorySessionStore`

Thin wrapper over `dict[str, GameSession]` with `create() -> game_id`, `get(game_id) -> GameSession | None`, `save(game_id, session)`. Keeps the dict access pattern testable and lets us swap to a persistent store later without changing route handlers.

### Agent registry

```python
AGENT_REGISTRY: dict[str, Callable[[], Agent]] = {
    "Random": lambda: RandomAgent(rng=random.Random()),
    "Minimax": lambda: MinimaxAgent(),
}
```

The form posts a string; we look up the factory; we call it once per game. `Human` is not in the registry — the form handler maps `"Human"` to `None` in `session.agents`.

## Templates

### `new_game.html`

Two `<select>` elements (X agent, O agent), values `Human`, `Random`, `Minimax`. Default: X = `Human`, O = `Minimax`. Submit POSTs to `/games`.

### `game.html`

Wraps `_board.html` plus a status line and a "New game" link. Because every render runs `advance_bots` first, the only non-terminal page a user ever sees has the human as `current_player`. So the status line is one of: `Your turn (X)` / `Your turn (O)` / `Game over — X won` / `Game over — O won` / `Game over — draw`.

The status text is intentionally neutral (no "you won" / "you lost") because Human-vs-Human hot-seat games are allowed and the bot-vs-bot spectator mode has no "you" — saying "X won" works for all three modes.

### `_board.html`

3×3 grid of cells. Each empty cell on the human's turn is a clickable form:

```html
<form hx-post="/games/{{ game_id }}/move"
      hx-target="#board" hx-swap="outerHTML">
  <button name="cell" value="{{ idx }}">·</button>
</form>
```

Non-empty cells render as `X` or `O` (no form, plain text). On a terminal state, all empty cells also render as plain disabled markers. The whole fragment is wrapped in `<div id="board">…</div>` so HTMX `outerHTML` swap targeting `#board` keeps the wrapper intact.

## Error handling

| Condition | Response |
|---|---|
| Unknown game id | 404 |
| Move when game is terminal | 409 |
| Move when current seat is a bot (e.g. bot vs bot) | 409 |
| `cell` not in `state.legal_actions()` (illegal or occupied) | 400 |
| Malformed form body (non-int `cell`, missing field) | 422 (FastAPI default) |

No retry logic, no error pages — plain JSON or text bodies. The browser only ever sees `_board.html` for valid moves; HTMX surfaces other status codes via `hx-on::response-error` (out of scope to style; default is "no swap"). For v1 we do not handle the error UX beyond not breaking the page.

No auth. We assume single-user localhost.

## Testing

Test type: **macro-fake**. FastAPI `TestClient` is the fake (in-process, no real socket); the real `TicTacToe`, `RandomAgent`, `MinimaxAgent` are used unchanged. Tests are black-box (input → response) and follow Arrange / Act / Assert.

| Test | Scenario | Expected |
|---|---|---|
| `test_new_game_page_renders` | `GET /` | 200 + has X-agent/O-agent selects |
| `test_create_game_redirects_to_game_page` | `POST /games` with Human-vs-Minimax | 303 → `/games/{id}`; follow redirect renders `game.html` |
| `test_bot_vs_bot_auto_completes` | `POST /games` Random-vs-Random; follow redirect | terminal state visible in board (no empty cells, or winning line) |
| `test_human_vs_bot_first_move_advances_bot_reply` | Human X vs Random O; `POST /games/{id}/move cell=4` | response is `_board.html` with cell 4 = X and at least one O somewhere |
| `test_bot_x_human_o_bot_moves_before_render` | Random X vs Human O; `GET /games/{id}` | board has exactly one X already placed |
| `test_invalid_move_rejected` | move on occupied cell | 400 |
| `test_move_when_terminal_rejected` | force terminal state, then `POST /move` | 409 |
| `test_move_when_not_humans_turn_rejected` | Random vs Random, then `POST /move` | 409 |
| `test_unknown_game_id_returns_404` | `GET /games/nonexistent` | 404 |

Tests in `test_app.py` rely on substring assertions ("Game over", "Your turn (X)") that hold regardless of which legal move `RandomAgent` picks; explicit RNG seeding is unnecessary. `MinimaxAgent` is deterministic by design.

The route-level tests are complemented by direct black-box tests on the supporting modules — `test_sessions.py` for the `advance_bots` invariants (no-op when terminal, no-op when human to move, runs to terminal when no humans), `test_agents.py` for the registry contract, and `test_renderer.py` for the `state → BoardView` mapping. These are still macro-fake (real domain types, no mocks) and cover contracts that the TestClient layer would only exercise indirectly.

## Mypy & ruff

Existing strict mypy config covers `src/` and `tests/`. New code must pass with no exceptions. Add `fastapi`, `uvicorn`, `jinja2`, `httpx` as dependencies; their stubs ship with the packages. No `# type: ignore` without an explanatory comment justifying it.

Existing ruff config (line-length 100, rules `E F W I B UP SIM RUF`) is unchanged.

## Running locally

```bash
uv run uvicorn table_peak.web.app:app --reload
```

Open `http://localhost:8000/`. Browser support: any modern browser that runs HTMX (Chromium, Firefox, Safari recent versions).

## Deferred / explicit YAGNI

- **Persistence**: sessions reset on server restart. When wanted, swap `InMemorySessionStore` for a SQLite-backed one.
- **Spectator mode** / live updates: requires SSE or WebSocket; deferred until a partial-info game where polling is too coarse.
- **Player auth / multi-user**: not needed for localhost dev.
- **Per-player view filtering**: TTT is full info; the filter pattern (`state.public_view(player_id)`) will be designed when Skyjo arrives.
- **Renderers for other games**: pattern accepts them; not implementing.
- **Pretty error pages, CSRF, rate limiting**: not for localhost.
- **Configurable `Random` seed in the UI**: not needed; default `random.Random()` is fine.
- **OpenAPI polish**: FastAPI generates one for free; we don't curate it for v1.

## Risks

- **HTMX learning curve for the user**: tiny — three attributes (`hx-post`, `hx-target`, `hx-swap`). Documented inline.
- **Mypy strict + FastAPI**: known to need careful typing of dependencies and response models. Mitigated by keeping handlers minimal and returning `HTMLResponse` directly.
- **Session leak**: in-memory store grows unbounded. Acceptable for localhost dev; if it bites, add a max-size LRU eviction. Out of scope for v1.

## Future hooks (not built now, but enabled)

- Replace `InMemorySessionStore` with a SQLite-backed one — same interface.
- Add `renderers/skyjo.py` and route group `/skyjo/...` once the Skyjo `Game` lands.
- Add a `state.public_view(player_id)` method to `State` Protocol when partial info arrives; renderers consume it.
- Add an SSE endpoint `/games/{id}/events` for spectator mode.
