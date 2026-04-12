# Active Context

## ✅ COMPLETED: T5 — Fix tmux window-exists check (2026-04-12)

**Commit:** 291ea5a  
**Branch:** feature/fix-session-hub-tmux

### Root Cause & Solution
Fixed fragile `grep -Fxq` pattern with atomic `tmux select-window` check for detecting existing tmux windows. Updated 3 files:
- **stack-create skill** (lines 108–125)
- **stack-navigate skill** (lines 140–148)  
- **clean-stack.sh** (lines 53–54)

## ✅ COMPLETED: T3 — Rewrite `merge-stack.sh` (GitHub-only)

**Commit:** 14a63d9  
**Branch:** feature/fix-session-hub-tmux

### What Was Fixed
1. ✅ Removed `gh-account.sh` import (multi-VCS token management)
2. ✅ Removed `GH_TOKEN=$(gh_token_for_remote)` pattern from all `gh` commands
3. ✅ Inlined dependent-branch updates (copied `_update_dependent_branches()` from update-stack.sh)
4. ✅ Inlined GitHub PR base sync (`_sync_github_pr_bases()`)
5. ✅ Fixed shellcheck warnings: `if ! command` instead of `[ $? -ne 0 ]`

### Result
Single 183-line script that handles full merge workflow end-to-end:
- Resolves PR number (from branch name or explicit number)
- Fetches PR details (title, source, target, state)
- Merges PR with `--squash --delete-branch`
- Rebases all dependent branches via Charcoal
- Syncs all dependent PR base branches on GitHub
- **No subprocess call to update-stack.sh**

### Remaining Backlog
- [ ] T1 — Verify `create-stack.sh` base branch logic (appears already correct)
- [ ] T8 — Verify `stack-auto-pr-merge` Agent tool syntax (appears already correct)
