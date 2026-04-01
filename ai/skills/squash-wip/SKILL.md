---
name: squash-wip
description: Squash iterative WIP commits (autoresearch/iter-N/checkpoint/wip) into clean commits before rebasing. USE THIS SKILL when user says "squash wip", "squash iterative", "squash iterative commits", "clean up commits", "squash before rebase", "consolidate wip", "clean commits before sync", or when drift-guard warns about WIP commits.
triggers:
  - squash wip
  - squash iterative
  - squash iterative commits
  - clean up commits
  - squash before rebase
  - consolidate wip
  - clean commits before sync
  - clean wip commits
---

# Squash WIP

Identifies iterative/WIP commits since the merge-base with `origin/main` and squashes them into clean, logical commits before rebasing. Prevents the "same file conflicts at every rebase step" failure mode caused by accumulated WIP history.

## When to Use

- `drift-guard` warned about WIP commit count ≥ 5
- About to run `/sync-base` and the branch has many autoresearch/iter-N commits
- Branch history has checkpoint commits from iterative AI research sessions
- Preparing a branch for PR — want clean, reviewable history

## Instructions

### Step 1: Safety — stash uncommitted changes

```bash
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -m "squash-wip: auto-stash before interactive rebase"
  STASHED=1
fi
```

### Step 2: Find the merge-base and count WIP commits

```bash
MERGE_BASE=$(git merge-base HEAD origin/main 2>/dev/null \
  || git merge-base HEAD origin/master 2>/dev/null)

TOTAL_COUNT=$(git rev-list --count "${MERGE_BASE}..HEAD")

WIP_SUBJECTS=$(git log --format="%H %s" "${MERGE_BASE}..HEAD" \
  | grep -E '(autoresearch|iter-[0-9]|checkpoint|wip|WIP)' || true)

WIP_COUNT=$(echo "$WIP_SUBJECTS" | grep -c . 2>/dev/null || echo 0)
```

Report to the user:
- Total commits since merge-base: `$TOTAL_COUNT`
- WIP commits found: `$WIP_COUNT`
- List the WIP commit subjects (up to 20)

If `WIP_COUNT` is 0, report "No WIP commits found — branch history is already clean." and stop.

### Step 3: Confirm with the user

Show summary and wait for explicit confirmation before proceeding:

```
Found $WIP_COUNT WIP commits out of $TOTAL_COUNT total commits since merge-base.

WIP commits to squash:
<list subjects>

Proceed with interactive rebase? (yes/no)
```

Do NOT proceed without user confirmation.

### Step 4: Run interactive rebase

```bash
git rebase -i "$MERGE_BASE"
```

Instruct the user on what to do in the rebase editor:

1. Leave `pick` on the **first** commit of each logical group
2. Change `pick` → `squash` (or `s`) for subsequent WIP commits in that group
3. Use `fixup` (or `f`) for pure noise commits (e.g. `checkpoint: iter-47`) to squash and discard their message
4. Save and close the editor
5. When git opens the combined commit message editor, write a clean descriptive message

**If conflicts occur:**
- Report which files conflict
- Tell the user to resolve them and run `git rebase --continue`
- Do NOT force-push, abort, or auto-resolve

### Step 5: Verify clean state

```bash
git log --oneline "${MERGE_BASE}..HEAD"
```

Report the resulting commit list and confirm WIP commits are gone.

### Step 6: Pop stash (if applicable)

```bash
if [[ "${STASHED:-0}" == "1" ]]; then
  git stash pop
fi
```

### Step 7: Summary

Report:
- Commits before squash: `$TOTAL_COUNT`
- WIP commits squashed: `$WIP_COUNT`
- Commits after squash: `$(git rev-list --count ${MERGE_BASE}..HEAD)`
- Branch is now ready for `/sync-base`

## Examples

User: "squash wip"
Action: Detect WIP commits → stash → confirm → interactive rebase → verify → summary

User: "clean up commits before rebase"
Action: Same flow

User: "squash before rebase" (after drift-guard warned about 12 WIP commits)
Action: Same flow, then offer to continue with `/sync-base`

## Safety

- **Never** modifies commits that already exist on `origin/` (merge-base is the boundary)
- Always stashes uncommitted work before rebasing
- Requires user confirmation before starting the interactive rebase
- Reports conflicts instead of auto-resolving them
- Does **not** push — user must push separately after reviewing the result
