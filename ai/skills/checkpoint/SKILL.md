---
name: checkpoint
description: >
  Creates a WIP commit capturing the current state of work with a standardized message,
  then updates plans/progress.md. Use when you want to save progress mid-task without
  completing it. Pairs with /resume-context for session handoffs.
triggers:
  - /checkpoint
  - save progress
  - wip commit
  - checkpoint my work
  - save my work
---

# Checkpoint

Creates a WIP commit with standardized format and updates session artifacts.

## When to Use

Invoke when:
- User says `/checkpoint`, "save progress", "wip commit", "checkpoint my work"
- A significant sub-task is complete but the full task is not done
- Before switching context or ending a session mid-task

## Instructions

### Step 1 — Show current state

Run `git status` and show the modified files. Do NOT use `-A` or `git add .`.

### Step 2 — Ask for description

Prompt the user:
> "Brief checkpoint description? (e.g. 'add metrics struct', 'fix FK resolution')"

Wait for the response before continuing.

### Step 3 — Determine scope

Infer the scope from:
1. The current branch name (strip type prefix: `feature/add-metrics` → `metrics`)
2. Or the primary package being edited (e.g. `worker`, `scheduler`, `repo`)

### Step 4 — Stage relevant files

Add only the files shown in `git status` that are relevant to the work described.
Use specific file paths — never `git add -A` or `git add .`.

If there are unrelated files (e.g. session artifacts, scratch files), skip them and
inform the user which files were excluded.

### Step 5 — Ask for next steps

Prompt the user:
> "What's the next step after resuming? (optional — press Enter to skip)"

### Step 6 — Commit

```bash
git commit -m "$(cat <<'EOF'
wip(<scope>): checkpoint — <description>

Next: <next-steps or "TBD">

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 7 — Update plans/progress.md

In `plans/progress.md`:
- Move any `## In Progress` items that are now saved to a `## WIP` section with a `[checkpoint]` marker
- The WIP section preserves them as in-flight (not Done, not Pending)

Format:
```markdown
## WIP (checkpointed)
- [ ] <task> [checkpoint: <description>]
```

### Step 8 — Auto-Save Context to MemPalace

Run the following to ensure the latest conversational context and reasoning leading up to this checkpoint are permanently saved to MemPalace (if transcripts are being tracked):

```bash
if [ -d "agent-transcripts/" ]; then
  mempalace mine agent-transcripts/ --mode convos
fi
```

### Step 9 — Confirm

Show `git log --oneline -3` so the user can see the commit was created.

Print:
```
✓ Checkpoint saved: wip(<scope>): checkpoint — <description>
✓ Context saved to MemPalace.
  Resume with: /resume-context
```

## Notes

- Never skip asking for the description — a commit message of "checkpoint" with no context is useless
- If `plans/progress.md` doesn't exist, skip Step 7 silently
- If no files are staged after Step 4, abort and inform the user (nothing to commit)
