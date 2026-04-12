---
name: resume-context
description: >
  Prints a ≤20-line situation summary from git history, session artifacts (plans/),
  and relevant Serena memories. Use at the start of a resumed session to quickly
  re-establish context without manually reading multiple files.
triggers:
  - /resume-context
  - resume context
  - what was I doing
  - where were we
  - catch me up
  - restore context
  - what's the current state
---

# Resume Context

Prints a concise situation summary to restore context at session start or after a long break.

## When to Use

Invoke when:
- User says `/resume-context`, "resume context", "where were we", "catch me up"
- Starting a new session on a branch that has prior work
- After `/compact` when context was summarized and detail was lost
- Returning to work after interruption

## Instructions

Execute these steps in order. Keep the final output to ≤20 lines.

### Step 1 — Git context

```bash
git log --oneline -5
git diff --stat HEAD
```

Show only if there are changes in the diff stat; skip the diff line if clean.

### Step 2 — Session artifacts

Read these files if they exist:
1. `plans/active-context.md` — current focus and plan pointer
2. `plans/progress.md` — task state (In Progress / Done / WIP sections)
3. `plans/session-handoff.md` — if it exists, extract the "Context from parent session" section

After reading `plans/session-handoff.md`, delete it (it's been consumed).

### Step 3 — Load relevant Serena memories

Based on the `focus:` line in `plans/active-context.md`, identify 2–3 Serena memory names
that are most relevant to the current work. Load them via pctx:

```typescript
// Match focus keywords to memory namespaces
// focus: "testing" → mutation_testing_patterns, go_testing_challenges
// focus: "k8s / deploy" → reference/worker_config_parameters, cluster_verification
// focus: "api / auth" → reference/api_and_environment
// focus: "knowledge management" → tools/*, workflows/session_management_*
// Always include: workflows/task_completion_checklist (if exists)
```

If pctx is unavailable, skip Serena loading and note it in the output.

### Step 4 — Print summary

Format the output as:

```
─── Context Resume ──────────────────────────────
Branch: <branch>
Focus:  <focus from active-context.md>
Plan:   <plan file if present>

Recent commits:
  <git log output — 3-5 lines>

Progress:
  In Progress: <items>
  WIP checkpoints: <items if any>
  Done this session: <count> items

Next action: <suggested next step from progress.md or session-handoff.md>
─────────────────────────────────────────────────
```

Keep the entire output under 20 lines. If progress has many items, summarize counts
("3 done, 2 in progress") rather than listing all.

### Step 5 — Update active-context.md

If `plans/session-handoff.md` was consumed, update `plans/active-context.md` to reflect
the restored state. Do not add new content — just ensure the `focus:` line is current.

## Notes

- If none of `plans/active-context.md`, `plans/progress.md`, or `plans/session-handoff.md` exist,
  fall back to just the git context from Step 1 and note "no session artifacts found"
- Do not print raw file contents — synthesize into the summary format above
- Do not ask the user questions during this skill — just print the summary and stop
