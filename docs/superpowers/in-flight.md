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

_(none — no features currently in flight)_
