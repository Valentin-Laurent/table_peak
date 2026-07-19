<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

## Beads sync (project-specific)

**The Dolt remote does not sync on `git push` by itself.** In bd 1.0.5 the `pre-push` hook (`bd hooks run pre-push`) does not call `bd dolt push`, and `sync.auto-push` is not consumed on that path (root cause in bead `table_peak-n5o`). The canonical beads sync is an explicit step — **`bd close` → `bd dolt push` → `git push`** ("Land the Plane").

This repo wires that sync into the pre-push hook itself. Git runs `.beads/hooks/pre-push` (via `core.hooksPath`), and that tracked file carries a `bd dolt push` block **after** bd's managed `END BEADS INTEGRATION` marker — non-fatal, so a Dolt hiccup or the offline sandbox never blocks a code push. It's version-controlled and survives `bd hooks install`, so a single `git push` syncs both code and Beads with no separate install. To disable, delete that block (everything after the END marker).

The `.beads/issues.jsonl` and `interactions.jsonl` exports are gitignored: they are passive, locally-regenerated snapshots (`export.auto: true`). The Dolt remote is the source of truth; do not commit the JSONL.

Under the Claude Code sandbox, agents can't reach the GitHub remote, so `bd dolt push` / `git push` must be run by the human (e.g. `! git push`, which also triggers the hook).
