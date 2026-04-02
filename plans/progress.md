# Progress

## Done
- [x] T2: Fix stack-pr skill — delegate gt log awk NR==2 to stack script
- [x] T6: stack-merge tmux cleanup (was already done)
- [x] T7: tmux bridge refresh in stack-create (was already done)
- [x] T9: Add stack chain visualization to create-pr.sh PR body
- [x] T10: New clean-stack.sh script + stack-clean skill
- [x] T11: New stack-pr-all skill
- [x] T12: Add draft PR prompt to stack-create skill
- [x] T13: Rename sync-base → stack-sync + update symlinks
- [x] T1/T3/T5/T8: Confirmed already done in prior sessions
- [x] Add trap ERR handlers to all 7 hooks for crash diagnostics
- [x] Merge all stale feature branches into main
- [x] Consolidate hooks to v2 architecture (pre-tool-gate-v2.sh, post-tool-analytics.sh)
- [x] Promote todo-gate and edit-without-read to block enforcement
- [x] Clean up worktrees and local branches
- [x] Re-add prompt-score-commit.sh to PostToolUse

## Backlog (Stack Skills Overhaul — carried forward)
- [ ] T1 — Fix `create-stack.sh` base branch default (current branch, not main)
- [ ] T3 — Rewrite `merge-stack.sh` GitHub-only + use `gh-account.sh`
- [ ] T8 — Fix `stack-auto-pr-merge` Python Task() → Agent tool syntax
- [ ] T5 — Fix tmux window-exists check in `stack-navigate` + `stack-create`
- [ ] T6 — Add post-merge tmux window cleanup to `stack-merge` skill
- [ ] T7 — Add tmux bridge refresh call to `stack-create` skill
- [ ] T10 — New `stack-clean` skill + script
- [ ] T11 — New `stack pr-all` script + skill + entrypoint routing
- [ ] T2 — Fix `stack-pr` skill `gt log awk NR==2` → delegate to script
- [ ] T9 — Add stack chain visualization to PR body in `create-pr.sh`
- [ ] T12 — Add optional draft PR prompt to `stack-create` skill
- [ ] T13 — Rename `sync-base` → `stack-sync` + `gt sync` + update `setup.sh`
