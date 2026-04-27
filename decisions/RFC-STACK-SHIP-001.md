# RFC-STACK-SHIP-001: Fully Automated Stack Branch → Release Pipeline

**Status:** Approved — implementation in progress (Phase 1)  
**Date:** 2026-04-27  
**Author:** arjaygg  
**Pre-conditions Met:**
- ✅ B-09 (merge-stack GitHub-only rewrite) stable
- ✅ B-10 (tmux window guard) fixed
- ✅ B-03 (ci-watch background agent) shipped
- ✅ B-05 + B-07 (scope-gate hooks) live

---

## 1. Summary

Implement `/stack-ship` skill: a fully automated pipeline that merges a green branch + all dependent branches atomically, rebases dependents, updates GitHub PR bases, handles conflicts gracefully with pause/resume, and logs all merges for audit trail.

---

## 2. Problem Statement

### Current State
- Stack branches exist (chore/stack-ship, feat/feature-a → main)
- Each branch has a GitHub PR in draft mode
- Merging requires manual steps: merge base, rebase dependents, update PR bases
- Risk of merge conflicts blocking entire stack
- No audit trail of what merged when

### Friction Points
1. **Manual rebasing** — After merging base branch, dependent branches must be manually rebased
2. **PR base updates** — GitHub PR target branches must be updated manually (currently defaults to main)
3. **Conflict handling** — If rebase conflicts occur, the entire operation stalls
4. **No observability** — No log of what merged, in what order, what errors occurred

---

## 3. Goals

1. **Atomic merge** — Merge a branch + all dependents in one operation or roll back all
2. **Automatic rebase** — Rebase dependent branches after each merge
3. **PR base auto-update** — Update each PR's target branch to its parent in the stack
4. **Conflict recovery** — Pause on conflict, allow manual resolution, resume
5. **Audit trail** — Log all merges to `.stack-ship/log.jsonl` with timestamps, hashes, actors
6. **Dry-run support** — Simulate merge without writing to repos or GitHub

---

## 4. Design

### 4.1 Skill Entry Point

**Skill Name:** `stack-ship`  
**Location:** `ai/skills/stack-ship/SKILL.md`  
**Invocation:**
```bash
/stack-ship [--dry-run] [--branch <name>]
```

**Parameters:**
- `--dry-run` — Simulate the merge without executing; print plan and exit
- `--branch <name>` — Merge only this branch + its dependents (default: current branch)

### 4.2 Core Algorithm (Phase 1)

**Input:** Current branch (or specified branch)  
**Output:** Merged stack or pause state (Phase 2)

```
1. Validate preconditions
   - Current branch is not main (safety check)
   - GitHub PR exists for this branch
   - All dependent PRs exist
   - CI is green on current branch (check with `gh run list` or ci-watch status)

2. Build dependency graph
   - Use `gt log` to determine parent branch of current branch
   - Recursively find all dependent branches (stack children)
   - Verify no circular dependencies

3. Merge in reverse topological order (leaves to root)
   - Start with current branch
   - For each dependent, rebase onto updated parent
   - Merge to parent via `gh pr merge --rebase --delete-branch`
   - Update GitHub PR base for next dependent

4. Update PR bases
   - For each dependent branch, update its PR target via `gh pr edit --base <new-base>`

5. Log operation
   - Write entry to `.stack-ship/log.jsonl`
   - Format: { "timestamp": ISO, "actor": $USER, "branch": name, "merged_into": parent, "hash_before": sha, "hash_after": sha, "status": "success|conflict" }

6. Return result
   - On success: "Merged N branches in M seconds"
   - On conflict: Set pause state, return instructions (Phase 2)
```

### 4.3 State File (Phase 2 groundwork)

Location: `.stack-ship/state.json`

```json
{
  "operation_id": "uuid",
  "started_at": "ISO timestamp",
  "paused_at": "ISO timestamp or null",
  "current_step": 1,
  "total_steps": 3,
  "steps": [
    {
      "branch": "feat/feature-a",
      "status": "completed|paused|pending",
      "error": "Conflict in src/file.ts" or null,
      "hash_before": "abc123",
      "hash_after": "def456"
    }
  ]
}
```

### 4.4 Logging

Location: `.stack-ship/log.jsonl` (append-only)

```json
{ "timestamp": "2026-04-27T14:23:45Z", "operation": "merge", "branch": "feat/feature-a", "parent": "main", "hash_before": "abc123", "hash_after": "def456", "status": "success" }
{ "timestamp": "2026-04-27T14:24:12Z", "operation": "rebase", "branch": "feat/feature-b", "onto": "feat/feature-a", "status": "success" }
```

---

## 5. Implementation Plan

### Phase 1 (This Session) — Core Skill + Merge Algorithm
- [ ] Create `ai/skills/stack-ship/SKILL.md`
- [ ] Implement merge algorithm (validate → graph → merge → update → log)
- [ ] Add `--dry-run` support
- [ ] Test with stacked branches on this repo
- [ ] Create PR when ready

### Phase 2 (Future) — Conflict Handling + Pause/Resume
- [ ] Implement state file (`.stack-ship/state.json`)
- [ ] Pause on conflict during rebase
- [ ] `/stack-ship --resume` to continue after manual fix
- [ ] Auto-detect stale state and offer rollback

### Phase 3 (Future) — Observability + Dry-Run
- [ ] Audit logging (`.stack-ship/log.jsonl`)
- [ ] `/stack-ship --log` to show recent operations
- [ ] Dry-run with detailed plan output

### Phase 4 (Future) — Hardening
- [ ] Slack notifications on success/failure
- [ ] Rate-limiting (prevent 2+ merges within 5 min)
- [ ] Rollback capability if post-merge CI fails
- [ ] Integration with migration-watchdog for safe merges

---

## 6. Acceptance Criteria (Phase 1)

1. **Skill file exists** at `ai/skills/stack-ship/SKILL.md`
2. **Merge command works** — `/stack-ship` on a stacked branch merges it + dependents
3. **Dependency graph detection** — Correctly identifies parent and children in stack
4. **Dry-run works** — `/stack-ship --dry-run` prints plan without executing
5. **Logging works** — `.stack-ship/log.jsonl` has entries after each merge
6. **Safety checks pass** — Refuses to merge main, requires green CI, checks PR exists

---

## 7. Testing Strategy

**Test Scenario 1: Linear Stack**
```
main → feat/feature-a → feat/feature-b → feat/feature-c
```
On `feat/feature-c`: `/stack-ship` should merge in order: c→a, then b→a, then a→main (or equivalent)

**Test Scenario 2: Dry-Run**
```
On feat/feature-a: `/stack-ship --dry-run` should print:
  Will merge:
    1. feat/feature-a → main
    2. feat/feature-b → feat/feature-a
    3. feat/feature-c → feat/feature-b
  (no actual merges)
```

**Test Scenario 3: Already Merged**
```
If feat/feature-a is already in main, skip it and continue with dependents
```

---

## 8. Key Files

| File | Purpose |
|---|---|
| `ai/skills/stack-ship/SKILL.md` | Skill entry point + usage guide |
| `.stack-ship/log.jsonl` | Audit log (created on first merge) |
| `.stack-ship/state.json` | Pause/resume state (Phase 2) |
| `decisions/RFC-STACK-SHIP-001.md` | This document |

---

## 9. Alternatives Considered

### Alternative 1: Use `git merge --squash` instead of `--rebase`
**Rejected:** Squashing loses commit history; stack philosophy is linear rebasing.

### Alternative 2: Merge top-to-bottom instead of bottom-to-top
**Rejected:** Would require rebasing main after every merge, which is unsafe.

### Alternative 3: Async queue-based merge (background agent)
**Rejected:** Sync merge with pause/resume is simpler; can upgrade to async in Phase 4.

---

## 10. Open Questions

1. Should we auto-detect when a dependent's PR has already been merged?
2. Should `/stack-ship` offer a preview before executing, or just --dry-run?
3. Should conflict resolution pause for manual `git rebase --continue` or prompt for auto-resolve strategies?

---

## 11. References

- RFC-DOTFILES-002: Pre-conditions (B-03, B-05, B-07, B-09, B-10)
- Charcoal (git worktree) stacking conventions
- GitHub MCP: `gh pr merge`, `gh pr edit`, `gh run list`
