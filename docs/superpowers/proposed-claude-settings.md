# Proposed `~/.claude/settings.json`

Generated 2026-05-25 by the `uv-to-pdm-migration` feature. Supersedes the prior 2026-05-15 version in commit history.

This is the **full intended file** to paste into `~/.claude/settings.json`. It is not a diff; copy the whole JSON block. The sandbox blocks Claude from editing the file directly, so application is manual.

## What changes vs. the actually-current settings.json

**Added to `permissions.allow`:**

- `Bash(make:*)` — primary dev workflow surface (via the existing `Makefile`).
- `Bash(pdm:*)` — any `pdm` subcommand. Replaces what the prior spec proposed adding as `Bash(uv:*)` (which was never applied).
- `Bash(tail:*)`, `Bash(head:*)`, `Bash(grep:*)`, `Bash(wc:*)`, `Bash(sort:*)`, `Bash(uniq:*)` — read-only diagnostic helpers used in pipes. Needed because Claude Code matches Bash pipeline *segments* individually.

**Sandbox filesystem swap (`sandbox.filesystem.allowWrite`):**

- Removed: `~/.cache/uv`, `~/.local/share/uv` (uv no longer used in `table_peak`).
- Added: `~/Library/Caches/pdm`, `~/Library/Logs/pdm`, `~/Library/Application Support/pdm` — pdm's cache, log, and data/config dirs.

**Why `~/Library/...` and not XDG (`~/.cache/pdm`)?** pdm resolves its directories via `platformdirs`, which on macOS returns the native `~/Library/{Caches,Logs,Application Support}/pdm` — *not* the XDG `~/.cache` / `~/.local/share` layout. (uv happens to use XDG paths even on macOS, which is why the prior uv config could whitelist `~/.cache/uv`. pdm does not — verified empirically: `pdm lock` failed under the sandbox on `~/Library/Logs/pdm` until these paths were whitelisted.) All three are pdm-scoped subdirectories, so the added write surface stays minimal. pdm must be installed via **pipx** (`pipx install pdm`), not the curl/Homebrew pyapp build — the pyapp build takes a per-run install lock under `~/Library/Caches/pyapp/locks/` that the sandbox blocks on every invocation.

**No sandbox-enabled flip:** `sandbox.enabled` is already `true` in the current file. The prior spec's plan to flip it to `false` was never executed by the user — so there's nothing to revert. The new permission shape is purely additive on top of today's reality.

## Required machine setup (one-time, NOT in settings.json)

These two steps live on the machine, not in `settings.json`, but the autonomous workflow depends on them:

1. **Install pdm via pipx:** `pipx install pdm`. *Not* the curl/Homebrew pyapp build — see the `~/Library/Caches/pyapp` note above.
2. **Point pdm's TLS verification at the OpenSSL CA bundle (global pdm config):**
   ```
   pdm config pypi.verify_ssl true
   pdm config pypi.ca_certs /etc/ssl/cert.pem
   ```
   **Why:** pdm defaults to `truststore`, which validates TLS certs against the macOS system keychain via `trustd` over Mach — and the sandbox blocks that Mach service (surfaces as `httpx.ConnectError: ('OSStatus -26276',)` on every network call, e.g. `pdm lock`). Setting `pypi.ca_certs` to a plain bundle path makes pdm pass it straight to httpx → in-process OpenSSL verification, no `trustd`, no Mach call, verification still ON. This is the TLS-layer analogue of uv's `SCDynamicStore` panic. It is stored in pdm's **global** config (`~/Library/Application Support/pdm/config.toml`), deliberately *not* in the repo: `/etc/ssl/cert.pem` is a macOS path and pinning it project-wide would break Linux CI and non-sandboxed machines.

## How to apply

1. Open `~/.claude/settings.json`.
2. Replace its entire contents with the JSON block below.
3. Restart Claude Code (or open a new session) so the settings reload.
4. Then proceed to Phase 3 of [`plans/2026-05-25-uv-to-pdm-migration-plan.md`](plans/2026-05-25-uv-to-pdm-migration-plan.md).

## Full file

```json
{
  "permissions": {
    "allow": [
      "Read(./**)",
      "Edit(./**)",
      "Write(./**)",
      "Glob(./**)",
      "Grep(./**)",
      "Read(~/code/perso/dotfiles/**)",
      "Glob(~/code/perso/dotfiles/**)",
      "Grep(~/code/perso/dotfiles/**)",
      "Read(~/.claude)",
      "Glob(~/.claude)",
      "Grep(~/.claude)",
      "WebFetch(domain:code.claude.com)",
      "WebFetch(domain:api.anthropic.com)",
      "WebFetch(domain:stackoverflow.com)",
      "WebFetch(domain:docs.python.org)",
      "WebFetch(domain:pypi.org)",
      "Agent",
      "ToolSearch",
      "TodoWrite",
      "mcp__context7__resolve-library-id",
      "mcp__context7__query-docs",
      "Bash(rtk git -C /Users/valentinlaurent/code/perso/table_peak*)",
      "Bash(make:*)",
      "Bash(pdm:*)",
      "Bash(tail:*)",
      "Bash(head:*)",
      "Bash(grep:*)",
      "Bash(wc:*)",
      "Bash(sort:*)",
      "Bash(uniq:*)",
      "Skill(superpowers:*)",
      "Skill(parallel-feature-development)",
      "Skill(simplify)"
    ],
    "defaultMode": "dontAsk",
    "additionalDirectories": [
      "~/code/pro/RATP/sequoia",
      "~/code/pro/MAPIE/MAPIE",
      "~/code/perso/claude_home",
      "~/code/perso/table_peak"
    ]
  },
  "model": "opus",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "rtk hook claude"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/notify.sh"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/notify.sh"
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/statusline.sh"
  },
  "enabledPlugins": {
    "pyright-lsp@claude-plugins-official": true
  },
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "network": {
      "allowedDomains": [
        "code.claude.com",
        "stackoverflow.com",
        "docs.python.org",
        "pypi.org",
        "files.pythonhosted.org",
        "download.pytorch.org"
      ]
    },
    "filesystem": {
      "allowWrite": [
        "~/code/pro/RATP/sequoia",
        "~/code/pro/MAPIE/MAPIE",
        "~/code/perso/claude_home",
        "~/.Trash/",
        "~/code/perso/table_peak",
        "~/Library/Caches/pdm",
        "~/Library/Logs/pdm",
        "~/Library/Application Support/pdm"
      ],
      "denyRead": [
        "~/.ssh/",
        "~/.aws/",
        "~/.config/gh/",
        "~/Downloads/"
      ]
    }
  },
  "theme": "light"
}
```

## Sanity check after applying

In a fresh Claude Code session in `table_peak`:

- `pdm --version` → prints a version (pdm must be installed; see Phase 2 of the plan).
- `pdm install` → no panic, completes; `.venv/` is created/updated.
- `make help` → prints the target list.
- `make check` → runs the full local-CI suite.

If `pdm install` panics with a `SCDynamicStoreCreate`-style error, abort and follow Phase 4 of the plan (revert + open new spec for pip+pip-tools fallback).
