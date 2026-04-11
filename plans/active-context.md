# Active Context

## Completed: T5 — Fix tmux window-exists check (2026-04-11)

Branch: `feature/fix-session-hub-tmux`

### Issue Fixed
The tmux window detection logic used `grep -Fxq` which was too strict and could fail with certain window names or tmux configurations. This caused new Claude sessions to not open in new tmux windows when creating stacked branches, especially in the ~/.dotfiles project.

### Root Cause
Both `stack-create` and `stack-navigate` skills used:
```bash
tmux list-windows ... | grep -Fxq "$WINDOW_NAME"
```
This pattern is fragile because:
1. It depends on exact output formatting from tmux
2. It can fail if there are trailing spaces or other whitespace
3. It's less reliable across different tmux versions

### Solution Applied
Replaced with atomic `tmux select-window` check:
```bash
if tmux select-window -t "$TMUX_SESSION:$WINDOW_NAME" 2>/dev/null; then
    # Window exists
else
    # Create window
fi
```

### Files Modified
1. **ai/skills/stack-create/SKILL.md** — Fixed step 4 (tmux window opening logic)
2. **ai/skills/stack-navigate/SKILL.md** — Fixed tmux window check for navigation
3. **.claude/scripts/pr-stack/clean-stack.sh** — Consistent window detection

### Additional Improvements
- Added early-exit error handling if `$TMUX` or `$TMUX_SESSION` is empty
- Used `-c $WORKTREE_PATH` flag in `tmux new-window` to avoid separate `cd` commands
- Cleaner, more maintainable code with better diagnostics

### Backlog (other stack skill fixes)
- [ ] T1 — Fix `create-stack.sh` base branch default
- [ ] T3 — Rewrite `merge-stack.sh` GitHub-only + `gh-account.sh`
- [ ] T8 — Fix `stack-auto-pr-merge` Python Task() → Agent tool syntax
