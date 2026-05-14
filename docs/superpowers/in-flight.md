# In-flight features

This file is maintained by the `parallel-feature-development` skill. Manual edits are discouraged.

Each entry below describes a feature currently being developed in parallel with others in this project. Sessions reading this file before starting work get static awareness of sibling work — what's being built, what scope is owned, what should not be touched.

**Lifecycle:**
- Entry appended (status: `spec_drafted`) at the end of a brainstorm session, after spec approval and commit.
- Status flips to `dispatched` when an execute-phase session begins for that feature.
- Entry dropped when the feature is merged to `main`.

**Schema (one entry per feature):**

```yaml
- name: <kebab-case slug>
  spec_path: <relative path to spec file>
  branch: <feature/<slug>>
  worktree_path: <relative path or 'in-place'>
  status: <spec_drafted | dispatched>
  scope_summary: <1–2 sentence prose>
  forbidden_zones:
    - <glob pattern this feature owns>
    - <glob pattern this feature owns>
```

## Entries

- name: training-progress-viewer
  spec_path: docs/superpowers/specs/2026-05-10-training-progress-viewer-design.md
  branch: feature/training-progress-viewer
  worktree_path: TBD
  status: spec_drafted
  scope_summary: Terminal-rendered live training-metrics viewer (plotext) backed by a `RunStore` Port + filesystem run-dir convention; web/notebook adapters deferred.
  forbidden_zones:
    - src/table_peak/training/run.py
    - src/table_peak/training/viz.py
    - src/table_peak/training/train.py
    - tests/training/test_run.py
    - tests/training/test_viz.py
    - tests/training/test_train.py
    - runs/**

- name: skyjo-engine
  spec_path: docs/superpowers/specs/2026-05-10-skyjo-engine-design.md
  branch: feature/skyjo-engine
  worktree_path: TBD
  status: spec_drafted
  scope_summary: Skyjo rules engine in `src/table_peak/games/skyjo/` as a `pyspiel.Game` (open_spiel custom-game), parameterized 2–8 players, single round, plus a generic `pyspiel.State` → our `State` Protocol wrapper Port. No agents, no UI, no training in scope.
  forbidden_zones:
    - src/table_peak/games/skyjo/**
    - src/table_peak/games/_pyspiel_adapter.py
    - tests/games/skyjo/**

- name: python-workflow-zero-trust
  spec_path: docs/superpowers/specs/2026-05-14-python-workflow-zero-trust-design.md
  branch: feature/python-workflow-zero-trust
  worktree_path: TBD
  status: spec_drafted
  scope_summary: Keep `uv` as package manager but flatten the permission surface via a Makefile wrapper layer + broader user-global Bash matchers (`Bash(make:*)`, `Bash(uv:*)`, diagnostic pipe helpers). Settings.json edits surfaced as a diff for manual apply (sandbox denies direct writes to settings files).
  forbidden_zones:
    - Makefile
    - docs/superpowers/specs/2026-05-14-python-workflow-zero-trust-design.md
    - docs/superpowers/plans/2026-05-14-python-workflow-zero-trust-plan.md
