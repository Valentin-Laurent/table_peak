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

```yaml
- name: skyjo-web-play
  spec_path: docs/superpowers/specs/2026-06-05-skyjo-web-play-design.md
  branch: feature/skyjo-web-play
  worktree_path: in-place
  status: dispatched
  scope_summary: >
    Play one full round of Skyjo in the browser (human player 0 vs N Random bots,
    2-8 total). Generalizes the TTT web stack the minimal amount to host a second
    game; auto-randomizes setup and drops the human into main play to round-end.
  forbidden_zones:
    - src/table_peak/web/renderers/skyjo.py
    - src/table_peak/web/templates/_skyjo_board.html
    - tests/web/test_skyjo_play.py
    # Shared files this feature also modifies (coordinate before touching):
    - src/table_peak/web/app.py
    - src/table_peak/web/sessions.py
    - src/table_peak/web/agents.py
    - src/table_peak/web/renderers/__init__.py
    - src/table_peak/web/templates/new_game.html
    - src/table_peak/web/templates/game.html
    - src/table_peak/web/templates/_board.html
    - src/table_peak/games/skyjo/state.py
    - src/table_peak/games/skyjo/__init__.py
    - src/table_peak/games/_pyspiel_adapter.py
```
