---
name: hyper-atomic-commits-reference
description: >
  Reference detail for hyper-atomic commit discipline — the TodoWrite-to-fence
  mechanism and the full `.claude-atomic.yaml` per-repo override schema. Use when
  configuring per-repo thresholds or debugging why the commit fence did or didn't
  fire.
triggers:
  - .claude-atomic.yaml
  - post-task-fence
  - commit fence
  - atomic-status
---

# Hyper-Atomic Commits — Reference

Detail supporting `ai/rules/hyper-atomic-commits.md`. Read that file first for the
active-session rules; this skill covers the mechanism and configuration schema.

## Task Tracking Integration (TodoWrite → Fence)

The `post-task-fence.sh` hook fires on every **`TaskUpdate`** event — which is
emitted by the built-in `TodoWrite` task tracker when items are marked
`completed`. This is the bridge between task tracking and the commit fence.

**Use `TodoWrite` for in-session step tracking, NOT `Edit(plans/progress.md)`:**

| Tool | Triggers fence? | Persists across sessions? |
|---|---|---|
| `TodoWrite` (mark `completed`) | **Yes** → `TaskUpdate` → `post-task-fence.sh` | No — ephemeral |
| `Edit(plans/progress.md)` | **No** — bypasses hook chain entirely | Yes — in git |

Using only `Edit(progress.md)` silently disables the fence. Uncommitted changes
accumulate between tasks with no reminder.

**Correct workflow:**

1. Create `TodoWrite` list at session start.
2. Mark items `in_progress` → `completed` as tasks finish (this fires the fence).
3. Mirror final state to `progress.md` at commit boundaries (for cross-session resume).

## `.claude-atomic.yaml` schema

Place at the repo root to customize subsystem detection and thresholds:

```yaml
subsystems:
  source: ["src/", "lib/"]
  tests: ["tests/", "spec/"]
  config: ["*.toml", "*.yaml"]
thresholds:
  max_files: 10
  max_subsystems: 4
  max_diff_lines: 500
```

- `subsystems`: maps a category name to a list of path prefixes or glob patterns.
  Files are bucketed into subsystems for the `blocked` (mixed-concerns) check.
- `thresholds.max_files`: overrides the default 7 staged files.
- `thresholds.max_subsystems`: overrides the default 3 distinct subsystem categories.
- `thresholds.max_diff_lines`: overrides the default 300 added+removed lines.
