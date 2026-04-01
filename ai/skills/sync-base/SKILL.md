---
name: sync-base
description: Rebase the current branch onto its parent/base branch to pick up new commits. USE THIS SKILL when user says "sync base", "sync with base", "rebase base", "update from base", "pull base", "sync parent", "rebase onto parent", "catch up with base", "bring in base changes", or wants their feature branch up to date with the branch it was forked from.
triggers:
  - sync base
  - sync with base
  - rebase base
  - update from base
  - pull base
  - sync parent
  - rebase onto parent
  - catch up with base
  - bring in base changes
  - sync from parent
  - rebase from base
---

# Sync Base

Rebases the current branch onto its upstream parent branch so it includes the latest commits from the base. This is the everyday "keep my branch current" operation.

## When to Use

- The base/parent branch got new commits and you want them under your work
- Before creating a PR, to ensure a clean diff against the target
- Periodically during long-lived feature branches

## Instructions

### Step 1: Detect the base branch

Try these in order — use the first that succeeds:

1. **Charcoal** (if available):
   ```bash
   gt info 2>/dev/null | grep -i parent
   ```
   Extract the parent branch name from the output.

2. **Git tracking config**:
   ```bash
   git config --get branch.$(git branch --show-current).merge | sed 's|refs/heads/||'
   ```
   If it returns the branch's own name (self-tracking), skip to the next method.

3. **Merge-base heuristic** — find the nearest common ancestor among known bases:
   ```bash
   git fetch origin main develop feat/k8s-supervisor-platform 2>/dev/null
   for base in main develop; do
     COUNT=$(git rev-list --count "origin/${base}..HEAD" 2>/dev/null)
     echo "$COUNT $base"
   done | sort -n | head -1
   ```
   The base with the fewest commits diverged is likely the parent.

4. **Ask the user** if none of the above gives a clear answer.

Store the result: `BASE_BRANCH=<detected branch>`

### Step 2: Fetch and check for new commits

```bash
git fetch origin "$BASE_BRANCH"
NEW_COMMITS=$(git rev-list --count "HEAD..origin/${BASE_BRANCH}")
```

If `NEW_COMMITS` is 0, report "Already up to date with origin/${BASE_BRANCH}" and stop.

### Step 3: Handle uncommitted changes

```bash
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -m "sync-base: auto-stash before rebase"
  STASHED=1
fi
```

### Step 4: Rebase

Count our commits before rebasing (for the summary):
```bash
OUR_COMMITS=$(git rev-list --count "origin/${BASE_BRANCH}..HEAD")
```

Run the rebase:
```bash
git rebase "origin/${BASE_BRANCH}"
```

**If conflicts occur:**
- Report which files conflict
- Tell the user to resolve them, then run `git rebase --continue`
- Do NOT force or abort automatically
- Pop the stash reminder if we stashed

### Step 5: Push

Safety check — never force-push to main or master:
```bash
CURRENT=$(git branch --show-current)
if [[ "$CURRENT" == "main" || "$CURRENT" == "master" ]]; then
  echo "ERROR: Will not force-push to $CURRENT"
  exit 1
fi
```

```bash
git push --force-with-lease
```

### Step 6: Pop stash (if applicable)

```bash
if [[ "${STASHED:-0}" == "1" ]]; then
  git stash pop
fi
```

### Step 7: Summary

Report:
- Base branch: `origin/${BASE_BRANCH}`
- New commits from base: `${NEW_COMMITS}`
- Our commits replayed: `${OUR_COMMITS}`
- Status: success / conflicts (needs manual resolution)

## Examples

User: "sync with base"
Action: Detect base → fetch → rebase → push → summary

User: "update from base"
Action: Same flow

User: "rebase base" (while on feature/dev-e2e-tests stacked on feat/k8s-supervisor-platform)
Action: Detects feat/k8s-supervisor-platform as base → rebases → pushes

## Safety

- **Never** force-push to main or master
- Always uses `--force-with-lease` (refuses if remote has unexpected commits)
- Auto-stashes uncommitted work and restores after
- Reports conflicts instead of auto-resolving
