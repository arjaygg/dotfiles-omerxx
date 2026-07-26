---
name: hyper-atomic-commits-reference
description: >
  Reference detail for hyper-atomic commit discipline — the live task-gate/
  git-pipeline-gate Stop fence chain and the full `.claude-atomic.yaml` per-repo
  override schema. Use when configuring per-repo thresholds or debugging why the
  commit fence did or didn't fire.
triggers:
  - .claude-atomic.yaml
  - post-task-fence
  - commit fence
  - atomic-status
---

# Hyper-Atomic Commits — Reference

Detail supporting `ai/rules/hyper-atomic-commits.md`. Read that file first for the
active-session rules; this skill covers the mechanism and configuration schema.

## Task Tracking Integration (Live Fence Chain)

`post-task-fence.sh` is retired: it lives only under `.claude/hooks/archive/` and
is absent from `settings.json`'s hooks map, so it never fires regardless of
`TodoWrite`/`TaskUpdate` activity. The live commit-discipline fence is `stop.sh`'s
two-hook chain on session Stop, in first-deny-wins order: `task-gate.sh` (orphaned
tasks/bg-work/crons), then `git-pipeline-gate.sh` (due commit/PR/CI/merge/sync/
cleanup signals — plan: `plans/2026-07-25-agentic-git-pipeline.md`, goal:
`goals/2026-07-25-03-agentic-git-pipeline.md`).

**Use `TodoWrite` for in-session step tracking regardless** — it still gives
`task-gate.sh` visibility into orphaned/incomplete work at Stop time, even though
it no longer routes through a dedicated per-completion fence:

| Tool | Visible to `task-gate.sh` at Stop? | Persists across sessions? |
|---|---|---|
| `TodoWrite` (mark `completed`) | **Yes** — checked for orphaned items | No — ephemeral |
| `Edit(plans/progress.md)` | No — `task-gate.sh` doesn't parse it | Yes — in git |

**Correct workflow:**

1. Create `TodoWrite` list at session start.
2. Mark items `in_progress` → `completed` as tasks finish.
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
