# Active Context

## ✅ COMPLETED: T5 — Fix tmux window-exists check (2026-04-12)

**Commit:** 291ea5a  
**Branch:** feature/fix-session-hub-tmux

### Root Cause & Solution
Fixed fragile `grep -Fxq` pattern with atomic `tmux select-window` check for detecting existing tmux windows. Updated 3 files:
- **stack-create skill** (lines 108–125)
- **stack-navigate skill** (lines 140–148)  
- **clean-stack.sh** (lines 53–54)

## 🔨 IN PROGRESS: T3 — Rewrite `merge-stack.sh` (GitHub-only + gh-account.sh)

**Branch:** feature/fix-session-hub-tmux  
**Focus:** Refactor merge-stack.sh to remove multi-VCS baggage and inline dependent-branch updates

### Problem Statement
Current `merge-stack.sh` (125 lines) has 4 critical design issues:

1. **Mixed Multi-VCS Design** — Imports `gh-account.sh` for Azure DevOps + GitHub account switching, but only implements GitHub merge (`gh pr merge`). No Azure DevOps merge logic. Dead weight.

2. **Fragmented Token Injection** — Calls `GH_TOKEN=$(gh_token_for_remote)` before every `gh` command instead of relying on standard `gh auth`. Not needed for GitHub-only.

3. **Tangled Dependencies** — Merges a PR in merge-stack.sh, then delegates all dependent-branch updates to `update-stack.sh` via subprocess (line 117). This creates responsibility split:
   - merge-stack.sh: merge PR + delete branch
   - update-stack.sh: rebase dependents + sync PR bases + sync worktrees
   - **Result:** User can't understand end-to-end flow from one script; breaks on mid-workflow failures

4. **Lost Azure DevOps Implementation** — Script structure suggests multi-VCS was planned; never completed. Carrying dead code.

### Solution Roadmap
- [ ] Step 1: Copy dependent-branch update logic from update-stack.sh into merge-stack.sh
- [ ] Step 2: Remove gh-account.sh import + gh_token_for_remote calls
- [ ] Step 3: Inline Charcoal rebase + GitHub PR base sync
- [ ] Step 4: Add merge validation (PR exists, check CI/reviews)
- [ ] Step 5: Test with a live PR merge

**Expected result:** Single script that merges a PR and updates all dependents end-to-end, no subprocess.

### Remaining Backlog
- [ ] T1 — Verify `create-stack.sh` base branch logic (appears already correct)
- [ ] T8 — Verify `stack-auto-pr-merge` Agent tool syntax (appears already correct)
