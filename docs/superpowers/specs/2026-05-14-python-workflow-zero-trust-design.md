# Python workflow under zero-trust — Design

**Date:** 2026-05-14
**Status:** Draft, awaiting user review
**Slug:** `python-workflow-zero-trust`

## Goal

Make the day-to-day Python workflow in `table_peak` survive the user's zero-trust Claude Code sandbox without manual permission edits per command. Keep `uv` as the package/project manager (it remains best-in-class); flatten the *permission surface* via a Makefile wrapper layer and broader Bash matchers, and close any residual filesystem/network gaps that `uv sync` actually trips on.

## Non-goals (explicit YAGNI)

- **No tool replacement.** `uv` stays. No `pip` / `poetry` / `pdm` / `pixi` migration.
- **No CI overhaul.** Whatever GitHub Actions or pre-commit hooks exist (if any) are out of scope.
- **No Python-version manager change.** `.python-version` (if present) is left alone.
- **No dependency changes.** `pyproject.toml` is touched only if the wrapper layer needs a script entry; no `add` / `remove` of deps as part of this work.
- **No project-local settings file.** Per user decision, permissions live in user-global `~/.claude/settings.json` so the same shape works across all the user's projects (sequoia, MAPIE, claude_home, table_peak). No `.claude/settings.json` is created in this repo.
- **No replacement of `rtk`.** The existing `rtk hook claude` PreToolUse hook stays.
- **No automated edit of `settings.json` by Claude.** The sandbox lists both `~/.claude/settings.json` and `<project>/.claude/settings.json` in `denyWithinAllow`; Claude cannot write either. The execution plan surfaces the exact diff for the user to apply manually (or via the `update-config` skill).

## Success criteria (binary, machine-checkable)

1. From a fresh sandboxed Claude Code session in this repo, the following commands all run without any permission prompt and exit 0 (assuming the working tree is healthy):
   - `make sync`
   - `make lint`
   - `make format-check`
   - `make typecheck`
   - `make test`
2. `make help` lists all available targets with a one-line description each.
3. Running `uv sync` directly (via `Bash(uv …)`) succeeds end-to-end without any permission prompt and without any sandbox-denied filesystem/network errors.
4. The user-global `~/.claude/settings.json` contains the new permission shape, with the three now-redundant per-`uv`-subcommand rules removed (`Bash(uv run ruff check*)`, `Bash(uv run mypy*)`, `Bash(uv sync*)`).
5. `mypy --strict` and `ruff check` clean on any new Python files (expected: zero — this is a tooling change).

## Architectural decisions

### Wrapper layer = Makefile, not a `scripts/` directory

Make is ubiquitous, has dependency tracking (only re-runs `sync` if `uv.lock` changed, etc.), and supports `make help` via a self-documenting convention. A `scripts/` directory would need its own permission rule per script or a permissive `Bash(./scripts/*)`. Make wins on uniformity: **one** matcher (`Bash(make:*)`) covers the full dev workflow.

### Targets in v1

Minimal, opinionated set. Each target wraps a single `uv` invocation (or short composition):

- `sync` → `uv sync`
- `lint` → `uv run ruff check`
- `format` → `uv run ruff format`
- `format-check` → `uv run ruff format --check`
- `typecheck` → `uv run mypy`
- `test` → `uv run pytest`
- `check` → `lint + format-check + typecheck + test` (aggregate; CI-like)
- `clean` → remove `.mypy_cache`, `.ruff_cache`, `.pytest_cache` via `trash` (per user preference)
- `help` → print target list

Run-targets for application entry points (`train`, `viz`, `play`, etc.) are **out of scope for v1** — they belong to whichever sibling owns the entry point. Both in-flight features (`training-progress-viewer`, `skyjo-engine`) can append their targets to the Makefile in their own worktrees; the wrapper is designed to grow, not be exhaustive at v1.

### Permission shape — user-global `~/.claude/settings.json`

Per user decision, the rules live in user-global settings so they cover every project the user works in. The shape:

- **Remove** the three now-redundant per-uv-subcommand rules: `Bash(uv run ruff check*)`, `Bash(uv run mypy*)`, `Bash(uv sync*)`.
- **Add** two broader rules:
  - `Bash(make:*)` — primary dev workflow surface. Covers `make sync`, `make lint`, `make test`, `make check`, etc., across every project.
  - `Bash(uv:*)` — ad-hoc `uv` for diagnosis, one-off installs, lockfile checks. Kept deliberately broad: the threat model here is "Claude does something weird with uv," and any uv subcommand can already mutate the lockfile or environment, so subcommand-level granularity is theater.
- **Add** common read-only diagnostic helpers used in pipes: `Bash(tail:*)`, `Bash(head:*)`, `Bash(grep:*)`, `Bash(wc:*)`, `Bash(sort:*)`, `Bash(uniq:*)`. These are the segments that get denied today when the user runs `uv sync 2>&1 | tail -20`.
- **Add** filesystem `allowWrite` paths if `uv sync` actually trips on something outside the current list (TBD until success criterion 3 is exercised; candidates: `~/.local/state/uv`, `~/.cache/pip` if uv falls back to pip resolution; the project's `.venv` is already covered by the per-project allowWrite).
- **Do not** add `Bash(*)` or any catch-all. Zero-trust posture is preserved at the file/network layer; what we're loosening is the *dev-tool surface*, not the *destructive-action surface*.

### Application mechanism: surfaced diff, not direct edit

Both `~/.claude/settings.json` and `<project>/.claude/settings.json` are in the sandbox's `denyWithinAllow` list. Claude cannot write either. The execution plan therefore produces:

1. The exact additions/removals as a JSON diff (or before/after snippet).
2. Instructions to apply via either (a) manual edit by the user, or (b) the `update-config` skill if `Skill` is allowlisted at that point.

The Makefile *can* be created by Claude (project filesystem is writable). The settings change *cannot* — that step is the user's hand on the keyboard, on purpose, because settings.json is a high-trust file.

### Cross-project effect

These rules will apply to sequoia, MAPIE, and claude_home as well. Implications:

- `Bash(make:*)` user-wide means any Makefile in any of those projects runs without prompt. Acceptable: those are all user-owned projects, and the user already has `additionalDirectories` for each.
- `Bash(uv:*)` user-wide same logic.
- The diagnostic-pipe helpers are inherently read-only on input, so user-wide is harmless.
- If any of those other projects has a Makefile target that does something destructive, the user is the one who wrote it; this is consistent with the trust model.

### Diagnostic-first ordering

Before settling on which extra filesystem/network paths to allow, the first work step in execution is: run `uv sync` from inside the new permission shape and see what (if anything) still fails. The spec lists *candidate* additions but commits to **only** what's actually needed. This keeps the allowlist honest.

### Coordination with sibling features

- `pyproject.toml` is not claimed by this feature. Both `skyjo-engine` (adding `open_spiel`) and `training-progress-viewer` (possibly adding `plotext`) will touch it; their forbidden zones do not include it either. Coordination cost is one merge-time review per sibling. Acceptable.
- The Makefile is owned by this feature. Sibling features that want to add `run-train` / `run-viz` / `run-play` targets do so in their own worktrees and the merges concatenate. If two siblings add Make targets simultaneously, the merge of the second will need a trivial rebase. Acceptable.

### What we explicitly are NOT doing

- No retry of every plausible fix until something works. The investigation step (success criterion 3) drives precise additions.
- No environment-variable shim layer. If `uv` needs `UV_CACHE_DIR` set, we set it in the Makefile recipe, not via a separate dotenv file.
- No pre-commit hook changes.

## Forbidden zones

Files this feature owns; other in-flight sessions must not write here:

- `Makefile`
- `docs/superpowers/specs/2026-05-14-python-workflow-zero-trust-design.md`
- `docs/superpowers/plans/2026-05-14-python-workflow-zero-trust-plan.md` (when plan is written)

Not claimed (shared or out of scope):

- `pyproject.toml` (siblings will touch)
- `uv.lock` (touched as a side effect of `uv sync` in any worktree)
- `README.md` / `CLAUDE.md` (may receive a one-line pointer to `make help`, but not a forbidden zone — siblings may also edit docs)
- `~/.claude/settings.json` (user-global; sandbox-denied for direct writes, and conceptually user-owned — handled via surfaced diff, not by Claude editing)

## Test plan

This is a tooling change with effectively zero new Python code. The "tests" are the success criteria themselves:

1. **Macro test (manual, one-shot):** in a fresh terminal, open Claude Code in this repo, ask Claude to run `make check`. Observe: no permission prompts, exits 0.
2. **Macro test (manual, one-shot):** ask Claude to run `uv sync` directly. Observe: no permission prompts, no sandbox-denied errors.
3. **Static:** `mypy --strict`, `ruff check`, `ruff format --check` clean (covered by `make check`).
4. **Documentation check:** `make help` output is human-readable and lists every target.

No automated test suite is added; the wrapper is config, not logic.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Broader `Bash(uv:*)` lets Claude accidentally mutate the environment (`uv add some-junk`). | Acceptable: any uv subcommand was already reachable via single-rule additions; we're not opening new attack surface, just removing prompts. Lockfile is committed; PR review catches regressions. |
| `make` is not installed on the user's machine. | macOS ships GNU `make` (BSD-flavor by default but compatible with our use). Verify in execution. |
| Sibling features add Make targets concurrently → merge conflict. | Conflict is a 3-line resolution. The Makefile structure is intentionally flat (one target per stanza) to make conflicts mechanical. |
| The "candidate" filesystem allowWrite additions turn out to be wrong / insufficient. | Investigation step (execution step 1) actually runs `uv sync` and reports what fails; precise additions are derived from that output, not guessed. |
| Loosening prompts encourages riskier auto-actions by Claude. | Out of scope. The wrapper layer's purpose is reducing friction for *expected* dev commands; destructive operations (git push, rm, etc.) remain prompt-gated. |

## Decisions resolved during brainstorm

1. **User-global settings, not project-local.** Same shape applies across all the user's projects. (Decided 2026-05-14.)
2. **Redundant `Bash(uv …)` rules are removed**, not left alongside the new broader rules. (Decided 2026-05-14.)
3. **`make format` is included** in v1. The marginal risk over already-allowed `Edit`/`Write` is low; if Claude becomes over-eager, the fix is a CLAUDE.md guideline, not a permission boundary. (Decided 2026-05-14.)
