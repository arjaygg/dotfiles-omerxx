---
name: stack-ship
description: Merge a stack branch and all dependents atomically with CI validation, conflict recovery, and audit logging.
triggers:
  - "/stack-ship"
  - "merge the stack"
  - "ship this stack"
  - "ship the branch"
---

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

Run: `$HOME/.dotfiles/.claude/scripts/stack-ship.sh`

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
