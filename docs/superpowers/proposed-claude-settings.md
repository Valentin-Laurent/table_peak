# Proposed `~/.claude/settings.json`

Generated 2026-05-15 by the `python-workflow-zero-trust` feature.

This is the **full intended file** to paste into `~/.claude/settings.json`. It is not a diff; copy the whole JSON block. The sandbox blocks Claude from editing the file directly, so application is manual (or via the `update-config` skill if `Skill` is allowlisted).

## What changes vs. the prior version

**Removed from `permissions.allow`:**

- `Bash(uv run ruff check*)`
- `Bash(uv run mypy*)`
- `Bash(uv sync*)`

These are subsumed by the broader `Bash(uv:*)` rule and would otherwise sit redundant.

**Added to `permissions.allow`:**

- `Bash(make:*)` — primary dev workflow surface (via the new `Makefile`).
- `Bash(uv:*)` — any `uv` subcommand for diagnosis / ad-hoc use.
- `Bash(tail:*)`, `Bash(head:*)`, `Bash(grep:*)`, `Bash(wc:*)`, `Bash(sort:*)`, `Bash(uniq:*)` — read-only diagnostic helpers used in pipes; needed because Claude Code matches Bash pipeline *segments* individually.

**Sandbox change:**

- `sandbox.enabled` flips from `true` to `false`.
- Why: `uv` panics inside Claude Code's macOS sandbox at `SCDynamicStoreCreate` (the `system-configuration` crate, called by `reqwest` at startup). This happens on *every* uv invocation, including `uv run X`, so even `make lint` would fail. The only viable mitigations were (a) disable the sandbox layer, or (b) replace uv. The user chose to keep uv, so (a) wins.
- Trade-off: the OS-level filesystem/network containment is dropped. The **permission layer** (`permissions.allow`, the absence of an entry = denied under `dontAsk`) remains the zero-trust enforcer.
- The `sandbox.network.allowedDomains` and `sandbox.filesystem.*` blocks are kept untouched. They are inert while disabled but become active again if `sandbox.enabled` is ever flipped back to `true`.

## How to apply

1. Open `~/.claude/settings.json`.
2. Replace its entire contents with the JSON block below.
3. Restart Claude Code (or open a new session) so the settings reload.

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
      "Bash(make:*)",
      "Bash(uv:*)",
      "Bash(tail:*)",
      "Bash(head:*)",
      "Bash(grep:*)",
      "Bash(wc:*)",
      "Bash(sort:*)",
      "Bash(uniq:*)",
      "Bash(rtk git -C /Users/valentinlaurent/code/perso/table_peak*)"
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
    "enabled": false,
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
        "~/.cache/uv",
        "~/.local/share/uv"
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

- `uv sync` → no panic, completes.
- `uv run ruff check --version` → prints a version.
- `make help` → prints the target list.
- `make check` → runs the full local-CI suite.

If any of these fail, the most likely culprits are: a typo in the pasted JSON, `make` missing (unlikely on macOS), or `trash` missing for `make clean` (install via `brew install trash` or rebind the target).
