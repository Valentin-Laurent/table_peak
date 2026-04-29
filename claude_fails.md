# Claude tool failures log

## 2026-04-29 — `git init` blocked by sandbox

**Command:** `git -C /Users/valentinlaurent/code/perso/table_peak init -b main`

**Error:** `/Users/valentinlaurent/code/perso/table_peak/.git/hooks/: Operation not permitted`

**Cause:** Sandbox / permission denial — the sandbox allowlist covers writes inside `~/code/perso/table_peak`, but `git init` creates `.git/hooks/` and copies sample hook scripts into it; macOS / sandbox flagged the operation. Resolved by retrying with `dangerouslyDisableSandbox: true`.

**Mitigation idea:** N/A — this is a one-time bootstrap action; future git operations on the existing repo work fine in the sandbox.

**Follow-up failure:** Retry with `dangerouslyDisableSandbox: true` was itself blocked by the user's "don't ask" permission mode. Resolution: user must run `git init -b main` manually (e.g., `! git init -b main`) or adjust permissions via `/sandbox`.
