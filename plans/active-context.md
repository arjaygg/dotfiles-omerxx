# Active Context

## ✅ COMPLETED: T5 — Fix tmux window-exists check (2026-04-12)

**Commit:** 291ea5a  
**Branch:** feature/fix-session-hub-tmux

### Issue
When using session-hub to create new Claude sessions (especially when selecting from ~/.dotfiles), the `tmux new-window` command would fail silently because there was NO window-existence check at all. This caused:
- Stack branch creation to not open new Claude sessions
- Session windows disappearing or not starting
- Broken workflow for creating stacked branches with parallel development

### Root Cause
Both `_session-hub-new.sh` and `session-hub.sh` were missing the window-exists detection logic entirely:
- `_session-hub-new.sh` (line 143): directly called `tmux new-window` without checking
- `session-hub.sh` (line 361): directly called `tmux new-window` without checking

If the window already existed, the command would fail silently (2>/dev/null suppresses errors).

### Solution ✅
Added proper window-exists detection to both scripts:

**Pattern:**
```bash
# Get window name (truncated to 30 chars for tmux limit)
window_name_trunc="${window_name:0:30}"

# Check if we're in tmux first
if [[ -n "$TMUX" ]]; then
    TMUX_SESSION=$(tmux display-message -p '#S')
    # Check if window exists
    if tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' | grep -Fxq "$window_name_trunc"; then
        # Window exists — switch to it
        tmux select-window -t "$TMUX_SESSION:$window_name_trunc"
        return 0
    fi
fi

# Window doesn't exist — create it
tmux new-window -c "$worktree_path" -n "$window_name_trunc" bash -l -c "..."
```

### Files Modified
1. **tmux/scripts/_session-hub-new.sh** (lines 137-155) — Added window-exists check
2. **tmux/scripts/session-hub.sh** (lines 354-374) — Added window-exists check in open_session()

### Validation
- Tested `tmux list-windows` output format and grep matching — works correctly
- Window detection now properly handles truncation (tmux limits window names to 30 chars)
- Switching to existing window works without errors

### Remaining Backlog (stack skill fixes)
- [ ] T1 — Fix `create-stack.sh` base branch default (current branch, not main)
- [ ] T3 — Rewrite `merge-stack.sh` GitHub-only + use `gh-account.sh`
- [ ] T8 — Fix `stack-auto-pr-merge` Python Task() → Agent tool syntax
