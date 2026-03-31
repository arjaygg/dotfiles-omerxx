# Session Defer — Deprioritize a Session

Marks a session as deferred so `/session-next` ranks it last (-30 score penalty).

## Instructions

### Step 1: Resolve target worktree

- If `$ARGUMENTS` is provided, resolve it to a worktree path (search `.trees/<name>` under the current repo, fuzzy match on worktree directory names)
- If `$ARGUMENTS` is empty, use `$PWD` as the target worktree

### Step 2: Write deferred status

Create or update `plans/session-handoff.md` in the target worktree:
- If the file exists, update the `status:` line to `deferred` and add/update `deferred_at: <today's date>`
- If the file doesn't exist, create it with:
  ```
  # Session Handoff
  status: deferred
  deferred_at: <today's date>
  ```
- Preserve all other fields in the file

### Step 3: Report

```
Deferred: <worktree-name> (branch: <branch>) — will score -30 in /session-next queue
```

## Arguments

- `$ARGUMENTS` — optional worktree name. If omitted, defers the current worktree.

### Examples

```
/session-defer              # defer current worktree
/session-defer wip          # defer the wip worktree
/session-defer backlog      # defer worktree matching "backlog"
```
