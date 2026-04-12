---
name: start-story
description: >
  Loads a story file, renames the session, converts acceptance criteria to tasks,
  and loads the relevant Serena memories for the story domain. One command to go
  from "start working on story N" to fully loaded context with tasks ready.
triggers:
  - /start-story
  - start story
  - begin story
  - work on story
  - load story
---

# Start Story

Loads a story and sets up session context in one step.

## When to Use

Invoke when:
- User says `/start-story [N]`, "start story N", "work on story N", "begin story N"
- Starting work on a new story or resuming a story from the beginning of a session
- Any time a story number or story path is given as context for starting work

## Instructions

### Step 1 — Find the story file

Parse the argument to determine the story file:

- If argument is a number like `1.9` → find `docs/stories/1.9.*.story.md`
- If argument is `PBI-005` → find `docs/stories/PBI-005.*.story.md`
- If argument is a full path → use directly
- If no argument → list available stories and ask the user to pick one

If multiple files match (ambiguous), show the list and ask which one.

### Step 2 — Read the story

Read the story file. Extract:
- **Story number and title** (from the `# Story N: Title` header)
- **Story type** (from filename: `*.story.md` pattern)
- **Status** (from `Status:` field — check if already `in-progress` or `done`)
- **Acceptance criteria** (the numbered items under `## Acceptance Criteria`)
- **Tasks** (the checkboxes under `## Tasks / Subtasks` if present)

If `Status: done` or `Status: merged`, warn the user:
> "Story N is already marked done. Are you sure you want to start it again?"
Pause and wait for confirmation.

### Step 3 — Rename the session

Derive a session name from the story:
- Format: `[N].[type]-[slug]`
- Where `[type]` is the story category (from filename or story content: `feat`, `fix`, `chore`)
- Where `[slug]` is 2-3 words from the title, kebab-cased
- Examples: `1.9.feat-chunked-processing`, `PBI-005.feat-data-fetch`, `2.1.feat-quarantine-schema`

Run: `/rename [session-name]`

### Step 4 — Check for open PR

```bash
gh pr list --head "$(git branch --show-current)" --state open --json number,title,url
```

If an open PR exists, show it:
> "Open PR: #N — [title] ([url])"

If no PR, note: "No open PR yet for this branch."

### Step 5 — Load relevant Serena memories

Based on the story domain, load the relevant memories via pctx (batch them in one execute_typescript call):

| Story domain | Memories to load |
|---|---|
| Testing / mutation / coverage | `mutation_testing_patterns`, `go_testing_challenges`, `workflows/task_completion_checklist` |
| API / observability / metrics | `reference/api_and_environment`, `workflows/task_completion_checklist` |
| K8s / deploy / scheduler | `reference/worker_config_parameters`, `feedback_cluster_verification`, `workflows/task_completion_checklist` |
| Database / repo layer / FK | `project_gorm_sqlserver_gotchas`, `project_integration_test_infra`, `workflows/task_completion_checklist` |
| Quarantine / error handling | `project_worker_config_parameters`, `workflows/task_completion_checklist` |
| Always load | `workflows/task_completion_checklist` (if it exists) |

Infer the domain from story title + acceptance criteria keywords. If unclear, load `workflows/task_completion_checklist` only and note what was loaded.

If pctx is unavailable, skip Serena loading and note it.

### Step 6 — Update plans/active-context.md

Update (or create) `plans/active-context.md`:

```markdown
focus: Story [N] — [title]
story: docs/stories/[filename]
branch: [current branch]
step: starting
```

### Step 7 — Print summary

```
─── Story [N]: [title] ─────────────────────────────
Status:    [story status]
File:      docs/stories/[filename]
Branch:    [current branch]
PR:        #N — [title] / (none)

Acceptance Criteria: [count] items
Tasks:     [count] existing / 0 if none

Memories loaded: [list or "none — pctx unavailable"]
─────────────────────────────────────────────────────
Ready. What would you like to work on first?
```

## Notes

- Do not auto-create tasks from acceptance criteria — the story already has a `## Tasks / Subtasks` section. Only create tasks if the section is empty AND the user explicitly asks.
- Never modify the story file itself (read-only)
- If the story has a `## Dev Notes` or `## Context` section, surface it in the summary
