# Python workflow under zero-trust — Design

**Date:** 2026-05-14 (revised 2026-05-15)
**Status:** Drafted, in execution
**Slug:** `python-workflow-zero-trust`

## Goal

Make the day-to-day Python workflow in `table_peak` survive the user's zero-trust Claude Code setup without manual permission edits per command. Keep `uv` as the package/project manager (it remains best-in-class); flatten the *permission surface* via a Makefile wrapper layer and broader Bash matchers; and resolve the **macOS-sandbox incompatibility** uv has with Claude Code's seatbelt profile.

## Execution finding (2026-05-15) — the problem is two-layered, not one

The first execution step (`uv sync` and `uv run X` inside the current sandbox) revealed that the friction has two independent causes:

1. **Permission layer (the originally-suspected one).** Per-uv-subcommand `Bash(...)` allows are brittle; pipes break matchers; daily friction. **Solved by:** Makefile wrapper + broader matchers — the original design.
2. **macOS sandbox layer (newly discovered).** Both `uv sync` and `uv run X` panic inside the Claude Code sandbox at `system-configuration-0.6.1/src/dynamic_store.rs:154` — a `SCDynamicStoreCreate` call (uv's HTTP client `reqwest` probing macOS network/proxy config at startup, before any subcommand logic). The sandbox profile denies the Mach lookup for this service. No `permissions.allow` entry fixes this because the failure is below the permission layer. The only escape hatch — `dangerouslyDisableSandbox=true` on each Bash call — is itself auto-denied under `defaultMode: dontAsk`.

The original spec assumed only layer 1. Layer 2 forces a choice; see "Sandbox layer" architectural decision below.

## Non-goals (explicit YAGNI)

- **No tool replacement.** `uv` stays. No `pip` / `poetry` / `pdm` / `pixi` migration.
- **No CI overhaul.** Whatever GitHub Actions or pre-commit hooks exist (if any) are out of scope.
- **No Python-version manager change.** `.python-version` (if present) is left alone.
- **No dependency changes.** `pyproject.toml` is touched only if the wrapper layer needs a script entry; no `add` / `remove` of deps as part of this work.
- **No project-local settings file.** Per user decision, permissions live in user-global `~/.claude/settings.json` so the same shape works across all the user's projects (sequoia, MAPIE, claude_home, table_peak). No `.claude/settings.json` is created in this repo.
- **No replacement of `rtk`.** The existing `rtk hook claude` PreToolUse hook stays.
- **No partial sandbox bypass per call.** `dangerouslyDisableSandbox=true` per Bash invocation is auto-denied under `dontAsk` and would prompt the user N times per session if `dontAsk` were relaxed — not workable. The sandbox decision is binary (see architectural decisions).
- **No automated edit of `settings.json` by Claude.** The sandbox lists both `~/.claude/settings.json` and `<project>/.claude/settings.json` in `denyWithinAllow`; Claude cannot write either. The execution plan surfaces the **complete intended `~/.claude/settings.json`** (not a diff) for the user to paste wholesale (or apply via the `update-config` skill).

## Success criteria (binary, machine-checkable)

1. From a fresh sandboxed Claude Code session in this repo, the following commands all run without any permission prompt and exit 0 (assuming the working tree is healthy):
   - `make sync`
   - `make lint`
   - `make format-check`
   - `make typecheck`
   - `make test`
2. `make help` lists all available targets with a one-line description each.
3. Running `uv sync` directly (via `Bash(uv …)`) succeeds end-to-end — no permission prompt, no sandbox panic.
4. The user-global `~/.claude/settings.json` contains the new permission shape, with the three now-redundant per-`uv`-subcommand rules removed (`Bash(uv run ruff check*)`, `Bash(uv run mypy*)`, `Bash(uv sync*)`), and `sandbox.enabled: false` (see "Sandbox layer" decision).
5. `mypy --strict` and `ruff check` clean on any new Python files (expected: zero — this is a tooling change).

## Architectural decisions

### Sandbox layer: disable macOS sandbox; keep permission-layer zero-trust

Given the layer-2 finding, three paths exist:

| Path | Action | Verdict |
|---|---|---|
| **A. Disable the macOS sandbox** | Set `sandbox.enabled: false`; rely on `permissions.allow` / `denyRead` for zero-trust | **Chosen.** Permission layer remains; uv works; Makefile pays off. |
| B. Keep sandbox, bypass per call | `dangerouslyDisableSandbox=true` on every uv-bearing Bash call | Auto-denied under `dontAsk`; relaxing `dontAsk` introduces N prompts per session. Not workable. |
| C. Replace uv | Use `pip`/`poetry`/`pdm` (all use urllib/requests, no SystemConfiguration Mach lookup) | User explicitly ruled this out. |

**Path A trade-off:** Claude operates inside the same permission rules as before — what changes is that the OS-level filesystem/network containment (a second defense layer) is dropped. The permission layer is still load-bearing: `Read(./**)` / `Write(./**)` / `denyRead(~/.ssh/)` etc. continue to gate Claude's actions. "Zero-trust at the permission layer, not at the OS-sandbox layer" is the honest framing.

**What gets preserved when sandbox is disabled:**
- All `permissions.allow` rules (Bash matchers, file scopes, network domain allows in their permission form).
- The `rtk hook claude` PreToolUse hook.
- All read-deny rules expressed as the absence of an `allow` entry.

**What gets lost:**
- macOS-level mandatory filesystem isolation (seatbelt-enforced). A bug in Claude that bypasses its own permission check would no longer be caught at the OS layer. Mitigation: the bug surface is the same as a normal terminal session; nothing about this project is more sensitive than the rest of the user's machine.
- `sandbox.network.allowedDomains` becomes inert. Network access is governed by whatever the OS / user's network setup allows. Practical effect: minimal, since none of the project's external services were outside the existing allowedDomains list.

**Why not narrow the macOS sandbox profile to permit SystemConfiguration?** Settings.json exposes only filesystem paths and network hosts. Mach-service allowlisting is not user-configurable today. That's an upstream Claude Code issue, not in scope here.

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

- **Set `sandbox.enabled: false`** (see "Sandbox layer" above).
- **Remove** the three now-redundant per-uv-subcommand rules: `Bash(uv run ruff check*)`, `Bash(uv run mypy*)`, `Bash(uv sync*)`.
- **Add** two broader rules:
  - `Bash(make:*)` — primary dev workflow surface. Covers `make sync`, `make lint`, `make test`, `make check`, etc., across every project.
  - `Bash(uv:*)` — ad-hoc `uv` for diagnosis, one-off installs, lockfile checks. Kept deliberately broad: the threat model here is "Claude does something weird with uv," and any uv subcommand can already mutate the lockfile or environment, so subcommand-level granularity is theater.
- **Add** common read-only diagnostic helpers used in pipes: `Bash(tail:*)`, `Bash(head:*)`, `Bash(grep:*)`, `Bash(wc:*)`, `Bash(sort:*)`, `Bash(uniq:*)`. These are the segments that get denied today when the user runs `uv sync 2>&1 | tail -20`.
- **Leave** `sandbox.network.allowedDomains` and `sandbox.filesystem.{allowWrite,denyRead}` as-is. They are inert while `sandbox.enabled: false` but become active again if the user ever re-enables the macOS sandbox.
- **Do not** add `Bash(*)` or any catch-all. The dev-tool surface is what we're loosening; destructive-action permissions stay narrow.

### Application mechanism: full settings.json, not a diff

Both `~/.claude/settings.json` and `<project>/.claude/settings.json` are in the sandbox's `denyWithinAllow` list. Claude cannot write either. The execution plan therefore produces:

1. The **complete intended `~/.claude/settings.json`** as a single fenced code block — every key the file should contain after the change, not just the delta. This eliminates the "diff misapplication" failure mode and makes a single copy-paste sufficient.
2. Instructions to apply via either (a) manual paste by the user, or (b) the `update-config` skill if `Skill` is allowlisted at that point.

The Makefile *can* be created by Claude (project filesystem is writable). The settings change *cannot* — that step is the user's hand on the keyboard, on purpose, because settings.json is a high-trust file.

Authoring the full file means execution must (a) read the *current* `~/.claude/settings.json` first to capture every key/value the user already relies on (model, hooks, statusLine, theme, sandbox config, additionalDirectories, the unrelated permission rules, etc.), and (b) emit a version that preserves all of those untouched, modifying only the `permissions.allow` list per this spec.

### Cross-project effect

These rules will apply to sequoia, MAPIE, and claude_home as well. Implications:

- `Bash(make:*)` user-wide means any Makefile in any of those projects runs without prompt. Acceptable: those are all user-owned projects, and the user already has `additionalDirectories` for each.
- `Bash(uv:*)` user-wide same logic.
- The diagnostic-pipe helpers are inherently read-only on input, so user-wide is harmless.
- If any of those other projects has a Makefile target that does something destructive, the user is the one who wrote it; this is consistent with the trust model.

### Diagnostic-first ordering (executed 2026-05-15)

The first execution step was to actually run `uv sync` under the current sandbox to see what failed. The result reshaped the spec — see "Execution finding" at the top. Without that step, the design would have shipped an allowlist expansion that fixed nothing.

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
| Disabling the macOS sandbox layer loses a defense layer. | Accepted trade-off (see "Sandbox layer" decision). Permission layer still gates Claude; user's machine isn't more exposed than during a normal terminal session. If upstream Claude Code later adds Mach-service allowlisting, the user can re-enable `sandbox.enabled: true` with no other change. |

## Decisions resolved during brainstorm and execution

1. **User-global settings, not project-local.** Same shape applies across all the user's projects. (Decided 2026-05-14.)
2. **Redundant `Bash(uv …)` rules are removed**, not left alongside the new broader rules. (Decided 2026-05-14.)
3. **`make format` is included** in v1. The marginal risk over already-allowed `Edit`/`Write` is low; if Claude becomes over-eager, the fix is a CLAUDE.md guideline, not a permission boundary. (Decided 2026-05-14.)
4. **macOS sandbox is disabled** (`sandbox.enabled: false`) as the only viable way to keep `uv` in a `dontAsk` workflow. Permission layer continues to enforce zero-trust. (Decided 2026-05-15, after execution finding.)
