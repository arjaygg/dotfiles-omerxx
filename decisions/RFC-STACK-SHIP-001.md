# RFC-STACK-SHIP-001: Fully Automated Stack Branch → Release Pipeline

**Status:** Approved (pending implementation)  
**Date:** 2026-04-27  
**Author:** arjaygg  
**Related:** RFC-DOTFILES-002 (Session 3, item B-13)  
**Pre-conditions:** All met as of 2026-04-27
  - ✅ B-09 (merge-stack GitHub-only rewrite) stable
  - ✅ B-10 (tmux window guard) fixed
  - ✅ B-03 (ci-watch background agent) shipped and used in 3+ real sessions
  - ✅ B-05 + B-07 (scope-gate hooks) live

---

## 1. Problem Statement

Manual PR merges in a stacked workflow require:
1. Switching branches and running `stack merge <branch>`
2. Waiting for dependent PR rebases and GitHub base-branch updates
3. Confirming each PR is green before proceeding
4. Repeating steps 1–3 for each layer in the stack

This is error-prone and interrupts dev focus. A single command (`/stack-ship`) should:
- Merge all checked, green, approved PRs in the stack
- Rebase and update all downstream PRs atomically
- Handle conflicts and partial failures gracefully
- Return CI status for upstream blocks

---

## 2. Goals

1. **One command to ship:** `/stack-ship [branch]` merges branch and all dependent branches (if green)
2. **No manual rebasing:** Charcoal rebases the stack; GitHub PR bases auto-update
3. **CI-aware:** Skip merge if CI is red; wait for in-progress checks with timeout
4. **Conflict resolution:** On conflict, pause and ask for manual resolution; resume after fix
5. **Audit trail:** Log each merge to `.stack-ship/log.jsonl` (one JSON per merge)
6. **Rollback safety:** If a merge breaks downstream, offer revert + reopen PR options

---

## 3. Design Overview

### 3.1 Command Interface

```bash
/stack-ship [options] [branch]

Options:
  --dry-run         Show what would be merged without doing it
  --ci-timeout 300  Wait up to N seconds for CI (default: 300)
  --no-rebase       Skip rebasing dependent branches (for hotfixes)
  --force           Merge even if CI is not green (risky, use with care)
  --verbose         Show detailed logs of each merge step

Examples:
  /stack-ship feature/api          # Merge api + all dependents
  /stack-ship                       # Merge current branch + dependents
  /stack-ship --dry-run feature/ui # Show what would happen
```

### 3.2 Merge Algorithm

1. **Identify the target branch** (from argument or `git branch --show-current`)
2. **Validate prerequisites:**
   - Branch has an open PR on GitHub
   - PR is approved (at least 1 approval)
   - No requested changes
3. **Wait for CI** (up to `--ci-timeout` seconds):
   - If green → proceed
   - If red → abort with message (offer `--force` to override)
   - If still running → wait or timeout (configurable)
4. **Merge the PR** via `gh pr merge --squash --delete-branch`
5. **Rebase all dependent branches** (Charcoal-tracked children):
   - For each dependent: `git rebase <parent>`
   - Push `--force-with-lease` (safe force push)
6. **Update GitHub PR base branches** (parallel):
   - For each dependent PR: update base via `gh pr edit --base <new-base>`
7. **Sync worktrees** (if they exist):
   - For each dependent: `git worktree prune` + `git fetch`
8. **Log the operation** to `.stack-ship/log.jsonl`:
   ```json
   {
     "timestamp": "2026-04-27T14:32:00Z",
     "branch": "feature/api",
     "pr": 123,
     "status": "success",
     "merged_count": 3,
     "duration_sec": 45,
     "conflicts": []
   }
   ```

### 3.3 Conflict Handling

When a rebase conflict occurs:

1. **Pause the pipeline:** Stop rebasing dependent branches
2. **Notify the user:**
   ```
   ⚠️  Conflict in feature/ui (depends on feature/api)
   Manual resolution required:
     cd .trees/ui && git rebase --continue
   Or abort:
     git rebase --abort && /stack-ship --resume feature/api --skip feature/ui
   ```
3. **Resume after fix:**
   ```bash
   /stack-ship --resume feature/api [--skip feature/ui] [--keep-going]
   ```

### 3.4 Pre-conditions Checklist

Before implementing, verify:

- [ ] `merge-stack.sh` is GitHub-only (B-09) ✅
- [ ] Tmux window-exists guard is solid (B-10) ✅
- [ ] ci-watch skill is stable + used 3+ sessions (B-03) ✅
- [ ] scope-gate hook (B-05 + B-07) is live ✅
- [ ] GitHub auth is working (`gh auth status`) ✅
- [ ] Charcoal is initialized in repo (`gt repo status`) ✅

---

## 4. Implementation Strategy

### Phase 1: Core merge pipeline (Skill)
- Implement `/stack-ship` as Claude Code skill
- Leverage existing `merge-stack.sh` logic + `ci-watch` status checks
- Parallel PR update for dependent branches (performance)

### Phase 2: Conflict handling + resume
- Add `--resume` flag to pause/continue after conflicts
- Store pipeline state in `.stack-ship/state.json` (ephemeral)

### Phase 3: Observability + safety
- Log all merges to `.stack-ship/log.jsonl` (audit trail)
- Add `--dry-run` to preview without committing
- Implement rollback: if a downstream test fails, offer revert

### Phase 4: Production hardening (future)
- Integrate with squad/codeowners for auto-approval
- Add Slack notifications for merge status
- Rate-limit merges (e.g., max 3/hour to prevent deploy storms)

---

## 5. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Force-push breaks peer branches | Use `--force-with-lease` (safe); document in log |
| CI reports delay → false negatives | `--ci-timeout` default 300s (configurable) |
| Merge succeeds but downstream fails | Offer immediate revert + trace in audit log |
| User interrupts mid-pipeline | State file allows `--resume` after fix |
| ADO repo confusion | Explicit GitHub-only guard (already in place) |

---

## 6. Success Criteria

- [ ] Single `/stack-ship` command merges entire stack (green) without manual steps
- [ ] Conflicts are caught early; user can fix and resume
- [ ] Audit log captures all merges for post-mortem analysis
- [ ] Used in 5+ real stacked PRs without incident

---

## 7. Backlog (Later Sessions)

- [ ] `--keep-going` flag: skip conflicted branches, proceed with rest
- [ ] Rollback feature: revert last N merges if downstream breaks
- [ ] Slack integration: notify channel on successful ship
- [ ] Codeowners integration: auto-approve if author is codeowner

---

## 8. Sign-Off

**Implementation:** Ready for Session 4 (future)  
**Owner:** arjaygg  
**Reviewer:** (pending)
