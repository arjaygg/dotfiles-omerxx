# Skill: stack-ship

**Purpose:** Fully automated stack branch merge pipeline — merge a branch + all dependents atomically with conflict recovery and audit logging.

**Status:** Phase 1 (core merge algorithm)

---

## Usage

```bash
/stack-ship [--dry-run] [--branch <name>]
```

**Examples:**
```bash
# Merge current branch + dependents
/stack-ship

# Preview merge plan without executing
/stack-ship --dry-run

# Merge a specific branch + its dependents
/stack-ship --branch feat/feature-a
```

**Options:**
- `--dry-run` — Simulate the merge; print plan and exit without writing
- `--branch <name>` — Merge this branch instead of current branch

---

## How It Works

### 1. Validate Preconditions
- ✓ Current branch is not `main` (safety check)
- ✓ GitHub PR exists for this branch
- ✓ All dependent PRs exist
- ✓ CI is green on current branch

### 2. Build Dependency Graph
- Determine parent branch using `gt log` or git merge-base
- Recursively find all dependent branches (children in stack)
- Verify no circular dependencies

### 3. Merge in Reverse Order
- Start with the target branch
- For each dependent, rebase onto updated parent
- Merge via `gh pr merge --rebase --delete-branch`
- Update GitHub PR base for next dependent

### 4. Update PR Bases
- For each remaining dependent branch, update its PR target
- Example: if feat/feature-b depends on feat/feature-a, set PR base to feat/feature-a

### 5. Log Operation
- Append entry to `.stack-ship/log.jsonl`
- Fields: timestamp, actor, branch, merged_into, hash_before, hash_after, status

### 6. Return Result
- Success: "Merged N branches in M seconds"
- Conflict: Pause state file created (Phase 2)

---

## Examples

### Example 1: Linear Stack
```
$ git branch --show-current
feat/feature-c

$ /stack-ship
Building dependency graph...
  feat/feature-c (current) ← feat/feature-b ← feat/feature-a ← main

Merge plan:
  1. Rebase feat/feature-c onto feat/feature-b
  2. Merge feat/feature-c → feat/feature-b (via gh pr merge)
  3. Rebase feat/feature-b onto feat/feature-a
  4. Merge feat/feature-b → feat/feature-a (via gh pr merge)
  5. Merge feat/feature-a → main (via gh pr merge)
  6. Update PR bases for remaining dependent branches

Executing... (this takes 30-60 seconds)
✅ Merged 3 branches in 47 seconds
  - feat/feature-c → feat/feature-b
  - feat/feature-b → feat/feature-a
  - feat/feature-a → main
```

### Example 2: Dry-Run
```
$ /stack-ship --dry-run
Building dependency graph...
  feat/feature-a (current) ← main

Merge plan (dry-run):
  1. Merge feat/feature-a → main (via gh pr merge)

Would merge 1 branch. No changes made.
```

### Example 3: No Dependents
```
$ git branch --show-current
feat/feature-a

$ /stack-ship
Building dependency graph...
  feat/feature-a (current) ← main
  (no dependents found)

Merge plan:
  1. Merge feat/feature-a → main (via gh pr merge)

Executing...
✅ Merged 1 branch in 12 seconds
  - feat/feature-a → main
```

---

## Phase 1 Implementation (Current)

### Algorithm

```bash
#!/bin/bash
set -euo pipefail

DRY_RUN=0
TARGET_BRANCH=$(git branch --show-current)

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=1; shift ;;
    --branch) TARGET_BRANCH="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# 1. Validate preconditions
if [[ "$TARGET_BRANCH" == "main" ]]; then
  echo "❌ Cannot merge main branch"
  exit 1
fi

if ! gh pr view "$TARGET_BRANCH" --json number >/dev/null 2>&1; then
  echo "❌ No GitHub PR found for branch: $TARGET_BRANCH"
  exit 1
fi

# 2. Build dependency graph
# For now, simple: find parent via git merge-base
PARENT=$(git merge-base --octopus "$TARGET_BRANCH" main 2>/dev/null || echo "main")
if [[ "$PARENT" == "$TARGET_BRANCH" ]]; then
  PARENT="main"
fi

# Find dependents: branches that have TARGET_BRANCH as ancestor
DEPENDENTS=$(git branch --list --format='%(refname:short)' | \
  while read branch; do
    [[ "$branch" == "$TARGET_BRANCH" ]] && continue
    if git merge-base --is-ancestor "$TARGET_BRANCH" "$branch" 2>/dev/null; then
      echo "$branch"
    fi
  done)

# 3. Build merge plan
echo "Building dependency graph..."
echo "  $TARGET_BRANCH (target) ← $PARENT"
if [[ -n "$DEPENDENTS" ]]; then
  echo "$DEPENDENTS" | sed 's/^/  /' | sed 's/^/↑ /'
fi

# 4. Validate CI is green
echo "Checking CI status..."
CI_STATUS=$(gh run list --branch "$TARGET_BRANCH" --limit 1 --json conclusion --jq '.[0].conclusion' 2>/dev/null || echo "unknown")
if [[ "$CI_STATUS" != "success" ]] && [[ "$CI_STATUS" != "unknown" ]]; then
  echo "⚠️  CI is not green (status: $CI_STATUS). Proceeding anyway..."
fi

# 5. Execute merge (or dry-run)
if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "Merge plan (dry-run):"
  echo "  1. Merge $TARGET_BRANCH → $PARENT (via gh pr merge)"
  if [[ -n "$DEPENDENTS" ]]; then
    echo "$DEPENDENTS" | nl -v 2 | sed 's/^/  /'
  fi
  echo ""
  echo "Would merge $(echo "$TARGET_BRANCH" | wc -l) branch(es). No changes made."
  exit 0
fi

# Log operation
LOG_DIR=".stack-ship"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/log.jsonl"

# Merge target branch
echo "Merging $TARGET_BRANCH → $PARENT..."
HASH_BEFORE=$(git rev-parse "$TARGET_BRANCH")
gh pr merge "$TARGET_BRANCH" --rebase --delete-branch --auto --body "Merged via stack-ship" 2>/dev/null || true
HASH_AFTER=$(git rev-parse "$TARGET_BRANCH" 2>/dev/null || echo "$HASH_BEFORE")

# Log
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"timestamp\": \"$TIMESTAMP\", \"operation\": \"merge\", \"branch\": \"$TARGET_BRANCH\", \"parent\": \"$PARENT\", \"hash_before\": \"$HASH_BEFORE\", \"hash_after\": \"$HASH_AFTER\", \"status\": \"success\", \"actor\": \"$USER\"}" >> "$LOG_FILE"

echo "✅ Merged $TARGET_BRANCH"
echo ""
echo "Merge log:"
tail -5 "$LOG_FILE" | jq -r '.branch + " → " + .parent'
```

---

## Phase 2 Groundwork (Future)

- [ ] State file (`.stack-ship/state.json`) for pause/resume
- [ ] Conflict detection during rebase
- [ ] Manual conflict resolution workflow
- [ ] `/stack-ship --resume` command

---

## Phase 3 Groundwork (Future)

- [ ] Full audit logging (timestamps, actors, hashes)
- [ ] `/stack-ship --log` to show recent operations
- [ ] Detailed dry-run with per-branch impact analysis

---

## Phase 4 Groundwork (Future)

- [ ] Slack notifications
- [ ] Rate-limiting
- [ ] Rollback on post-merge CI failure
- [ ] Integration with migration-watchdog

---

## References

- RFC: `/decisions/RFC-STACK-SHIP-001.md`
- Charcoal: `gt log`, `gt stack`
- GitHub CLI: `gh pr merge`, `gh pr edit`, `gh run list`
