# uv → pdm migration to keep the macOS sandbox enabled — Design

**Date:** 2026-05-25
**Status:** Drafted
**Slug:** `uv-to-pdm-migration`
**Supersedes:** [`2026-05-14-python-workflow-zero-trust-design.md`](2026-05-14-python-workflow-zero-trust-design.md) (Path A — sandbox-off — is reversed)

## Goal

Restore `sandbox.enabled: true` in the user's Claude Code config without losing the autonomy gains of the prior feature. Achieve this by **replacing uv with pdm** as the project's package/lockfile manager. pdm is pure Python, so it has no `system-configuration` Rust crate and no `SCDynamicStoreCreate` Mach lookup — the failure mode that forced the previous Path-A decision goes away.

The previous spec's permission-layer work (Makefile wrapper, broader `Bash(make:*)` matcher, diagnostic-helper allowlist additions) was independently sound and is **preserved verbatim**. Only the sandbox-layer decision and the choice of tool change.

## Reframe vs. the prior spec

The prior spec set sandbox-off as a hard requirement because keeping uv was treated as a non-goal. With that constraint relaxed (the user has confirmed uv is replaceable for this project), the layered problem collapses to a single layer:

| Layer | Prior verdict | New verdict |
|---|---|---|
| Permission layer | Solved by Makefile + broader matchers | **Unchanged. Kept.** |
| macOS sandbox layer | Disabled (Path A) to accommodate uv's reqwest probe | **Re-enabled.** pdm doesn't trigger the panic, so the OS containment layer can stay on. |

## Non-goals (explicit YAGNI)

- **No CI changes.** Whatever GitHub Actions or pre-commit hooks exist stay.
- **No Python-version manager change.** `.python-version` and `requires-python = ">=3.12"` stay.
- **No dependency edits.** `pyproject.toml`'s `[project.dependencies]` and `[dependency-groups].dev` lists are unchanged. The lockfile gets *regenerated* by pdm, which may produce different exact pinned versions; that is acceptable.
- **No removal of uv from the user's machine.** uv may still be used in sibling projects (sequoia, MAPIE, claude_home). This spec is `table_peak`-scoped.
- **No project-local settings file.** Permissions stay in user-global `~/.claude/settings.json`.
- **No partial-sandbox-bypass mechanism.** No `dangerouslyDisableSandbox=true`, no hook escape, no per-allowlist-entry sandbox bypass. The sandbox is binary: on, fully on.
- **No automated edit of `~/.claude/settings.json` by Claude.** The sandbox denies writes to that file; the execution plan emits the full intended file for the user to paste.
- **No tightening of unrelated permission rules.** Out of scope.

## Architectural decisions

### Tool layer: pdm, with pip+pip-tools as documented fallback

Why pdm rather than poetry / pip-tools / pixi / rye:

- **PEP 621-native.** Current `pyproject.toml` is pure PEP 621; pdm reads the same keys uv does. No `[tool.pdm]` block required up front; metadata migration cost is zero.
- **PEP 735 `[dependency-groups]` aware.** pdm contributed to that PEP; the project's existing `[dependency-groups].dev` block transfers without rewrite (subject to verification).
- **Sibling-merge cost is minimal.** Both in-flight features (`skyjo-engine`, `training-progress-viewer`) touch `pyproject.toml`. Because pdm reads the *same* PEP 621 keys, siblings need no rewrite of metadata — just a `pdm lock` after rebase.
- **Real lockfile.** `pdm.lock` is committed and consumed by `pdm install --frozen-lockfile` semantics.
- **Pure Python.** No Rust crates probing macOS network/proxy config at startup. The verification step exists to confirm this empirically before any rollout.

Why **not** poetry: poetry uses its own `[tool.poetry]` metadata format rather than PEP 621. Migrating to poetry would rewrite `pyproject.toml`'s entire project-metadata section, which collides with sibling work on the same file.

Why **not** pip+pip-tools: workable but loses `pyproject.toml`-as-source-of-truth ergonomics; lockfile is a flat `requirements.txt`. Kept as the documented **fallback** if pdm fails verification under the sandbox.

Why **not** rye: rye uses uv internally — same panic.

### Sandbox layer: re-enabled, with cache-path swap

`sandbox.enabled` flips from `false` back to `true`. For pdm to function under that profile, `sandbox.filesystem.allowWrite` must list pdm's cache and state directories rather than uv's:

- Remove: `~/.cache/uv`, `~/.local/share/uv`.
- Add: `~/.cache/pdm`, `~/.local/share/pdm`.

The rest of the sandbox configuration (`sandbox.network.allowedDomains`, the other `allowWrite` entries, `denyRead`) stays as-is. Those entries already cover pdm's network needs (pypi.org, files.pythonhosted.org).

### Verification step gates the rollout — the lesson from the previous round

The execution plan **must** front-load a sandbox-verification step *before* touching the Makefile, `pyproject.toml`, or the user's settings. The previous feature was bitten by exactly this: assumed compatibility, hit a panic in production. The verification step is the only addition to the methodology this round.

Verification, in shape (details belong to the plan, not the spec):

1. Stand up a scratch environment that uses the **target** sandbox profile — `sandbox.enabled: true` with the pdm cache/state paths added to `allowWrite`. (The same `~/.claude/settings.json` shape we'd ship.)
2. Under that profile, run `pdm install` against a copy of this project and a representative `pdm run X` invocation. Both must exit 0 with no sandbox denial and no panic.
3. **Only if both pass**, proceed with the in-repo migration.
4. **If either fails**, halt the migration. Fall back to `pip + pip-tools` (lockfile becomes `requirements.txt` + `requirements-dev.txt`) and re-verify that fallback before any rollout.

The verification step is non-skippable. The plan that follows this spec must encode it as its first task.

### Permission shape — user-global `~/.claude/settings.json`

The shape evolves from the prior spec's version as follows:

- **Flip** `sandbox.enabled`: `false` → `true`.
- **Remove** `Bash(uv:*)` from `permissions.allow`.
- **Add** `Bash(pdm:*)` to `permissions.allow`.
- **Swap** `~/.cache/uv` + `~/.local/share/uv` for `~/.cache/pdm` + `~/.local/share/pdm` in `sandbox.filesystem.allowWrite`.
- **Keep** `Bash(make:*)`, the diagnostic-helper rules (`Bash(tail:*)` etc.), `sandbox.network.allowedDomains`, `sandbox.filesystem.denyRead`, and every other unrelated key untouched.

### Application mechanism — full settings.json, not a diff

Unchanged from the prior spec: `~/.claude/settings.json` lives in the sandbox's `denyWithinAllow` set; Claude cannot write it. The execution plan produces the **complete intended file** as a single fenced block for the user to paste (or apply via `update-config`). This emission must read the current file first so unrelated keys (model, hooks, statusLine, theme, additionalDirectories, etc.) are preserved.

### Makefile — target names stay, recipes change

Every `make` target keeps its name and contract. Internally:

- `uv sync` → `pdm install`
- `uv run X` → `pdm run X`

The wrapper layer remains the single permission surface (`Bash(make:*)`). The whether-to-use-`.venv/bin/X`-directly question is deferred to the plan; the spec only commits to "pdm under the hood."

### Sibling coordination

After this feature merges, the two in-flight sibling branches need a small rebase:

1. Delete any stale `uv.lock` on the branch.
2. Run `pdm lock` to regenerate against `pdm.lock` from main, merging any deps the sibling added (which live in `[project.dependencies]` or `[dependency-groups]`, both PEP 621 / PEP 735 — pdm reads them directly).
3. Update any Makefile target the sibling may have added from `uv X` to `pdm X` (currently none).

**Recommended merge order:** this feature first, then siblings. Reason: this is the smallest scope but the most disruptive to siblings, so getting it on `main` early minimizes the lockfile churn each sibling has to absorb at their own merge time.

This feature does **not** claim `pyproject.toml`. Both pdm and uv consume the same PEP 621 keys, so siblings continue editing it as before — the only difference is which tool reads it post-merge.

### Supersession of prior-feature artifacts

Two files from the prior feature become stale on merge of this one:

- `docs/superpowers/specs/2026-05-14-python-workflow-zero-trust-design.md` — gets a SUPERSEDED banner pointing here. Original content kept for the diagnostic record (the `SCDynamicStoreCreate` panic location and the layered-problem framing remain useful context).
- `docs/superpowers/proposed-claude-settings.md` — gets a SUPERSEDED banner pointing here; the new execution plan regenerates it.

Banners are applied as part of this feature's commit set, not deferred to a follow-up.

### What we explicitly are NOT doing

- No "try a uv flag / env var to neutralize SystemConfiguration" investigation. The previous round established the panic is below the permission layer; the cheap fix is to leave the layer that calls it.
- No environment-variable shim layer for pdm.
- No retry loop of plausible fixes. The verification step gives a single binary answer (pdm works under sandbox, yes/no); fallback is pre-decided.

## Success criteria (binary, machine-checkable)

With `sandbox.enabled: true` restored and the new settings applied:

1. From a fresh sandboxed Claude Code session in this repo, the following commands all run without permission prompt, without sandbox panic, and exit 0:
   - `make sync`
   - `make lint`
   - `make format-check`
   - `make typecheck`
   - `make test`
   - `make check`
2. `pdm install` invoked directly (matched by `Bash(pdm:*)`) exits 0 with no sandbox denial.
3. `make help` lists all available targets with a one-line description each.
4. `uv.lock` is removed; `pdm.lock` is present and committed; `pyproject.toml` is unchanged except possibly a minimal `[tool.pdm]` block if verification shows one is required.
5. `~/.claude/settings.json` reflects the swap: `sandbox.enabled: true`, `Bash(pdm:*)` present, `Bash(uv:*)` absent, pdm cache paths in `allowWrite`, uv cache paths absent.
6. `mypy --strict` and `ruff check` clean on any new Python files (expected: zero — this is a tooling change).

## Forbidden zones

Files this feature owns; other in-flight sessions must not write here:

- `Makefile`
- `pdm.lock` (created), `uv.lock` (deleted)
- `docs/superpowers/specs/2026-05-25-uv-to-pdm-migration-design.md`
- `docs/superpowers/plans/2026-05-25-uv-to-pdm-migration-plan.md` (when written)
- `docs/superpowers/proposed-claude-settings.md` (banner-then-replace cycle owned here for the duration of this feature)
- `docs/superpowers/specs/2026-05-14-python-workflow-zero-trust-design.md` (banner edit only; content preserved)

Not claimed (shared or out of scope):

- `pyproject.toml` (siblings will touch; this feature reads PEP 621 keys but does not rewrite them)
- `~/.claude/settings.json` (user-global; sandbox-denied for direct writes; handled via surfaced full-file paste)
- `README.md` / `CLAUDE.md` (siblings may also edit docs)

## Test plan

This is a tooling change with no new Python code. "Tests" are the success criteria above, plus the verification step that gates the rollout:

1. **Pre-rollout (verification, mandatory):** scratch-env `pdm install` + `pdm run X` under the target sandbox profile. Pass = green-light; fail = pivot to pip-tools fallback and re-verify.
2. **Macro (manual, one-shot post-rollout):** in a fresh Claude Code session in this repo, ask Claude to run `make check`. Observe: no prompts, no panics, exits 0.
3. **Macro (manual, one-shot post-rollout):** ask Claude to run `pdm install` directly. Observe: same.
4. **Documentation:** `make help` output is human-readable and lists every target.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| pdm panics under the same sandbox profile uv did (different code path, same Mach-lookup family). | The verification step gates the rollout; fallback to pip+pip-tools is pre-decided and explicit. |
| PEP 735 `[dependency-groups]` not fully honored by the installed pdm version. | Verification catches; fallback is to fold dev deps into `[project.optional-dependencies]`, which both pdm and pip-tools handle uniformly. |
| Sibling branches drift further while this feature is in flight, accumulating uv-specific changes. | Merge order is "this feature first." Siblings rebase mechanically (delete `uv.lock`, run `pdm lock`). The rebase recipe is short and codified above. |
| `pdm run X` adds startup latency vs. `uv run X`. | Accepted trade-off: autonomy + sandbox-on beats raw speed for the day-to-day loop. Plan may choose to bypass `pdm run` for hot targets by calling `.venv/bin/X` directly. |
| Some pdm subcommand needs a path not in the allowlist that verification did not exercise. | Extend the allowlist on observed need, not on speculation. Pattern is consistent with the prior spec's diagnostic-first ordering. |
| Removing uv from the project breaks a workflow the user runs in their own terminal. | Out of scope: uv stays installed on the user's machine; only `table_peak`'s in-repo plumbing changes. |

## Decisions resolved during brainstorm

1. **Sandbox-on is a hard constraint** (user clarified: option (a) — sandbox must stay on; if no narrower fix works, change the tool). Decided 2026-05-25.
2. **uv is replaceable for this project** (user clarified: option (b) — replace uv, prioritize Claude autonomy over preserving uv's ergonomics in-repo). Decided 2026-05-25.
3. **pdm is the chosen replacement** (PEP 621 native, lowest sibling-merge cost, real lockfile). Decided 2026-05-25.
4. **pip+pip-tools is the documented fallback** if pdm fails sandbox verification. Decided 2026-05-25.
5. **Verification step gates rollout, non-skippable**. Decided 2026-05-25 (in direct response to the lesson from the previous round).
6. **Prior-feature artifacts get SUPERSEDED banners, not deletion** (preserve diagnostic context). Decided 2026-05-25.
