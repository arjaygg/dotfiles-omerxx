# Session Undefer — Restore a Deferred Session

Removes the deferred status from a session so `/session-next` scores it normally again.

## Instructions

### Step 1: Resolve target worktree

- If `$ARGUMENTS` is provided, resolve it to a worktree path (search `.trees/<name>` under the current repo, fuzzy match on worktree directory names)
- If `$ARGUMENTS` is empty, use `$PWD` as the target worktree

### Step 2: Update handoff status

In the target worktree's `plans/session-handoff.md`:
- Change `status: deferred` to `status: pending`
- Remove the `deferred_at:` line
- If the file doesn't exist or doesn't contain `status: deferred`, report that it wasn't deferred

### Step 3: Report

```
Undeferred: <worktree-name> (branch: <branch>) — restored to normal priority
```

## Arguments

- `$ARGUMENTS` — optional worktree name. If omitted, undefers the current worktree.

### Examples

```
/session-undefer              # undefer current worktree
/session-undefer wip          # undefer the wip worktree
```
