---
name: stack-navigate
description: Navigate between stacked branches using Charcoal (gt up/down) with worktree awareness. Automatically detects and navigates to worktrees when available. USE THIS SKILL when user says "go up", "go down", "navigate up", "navigate down", "parent branch", "child branch", "switch to parent", "switch to child", or wants to move between branches in their PR stack.
triggers:
  - go up
  - go down
  - navigate up
  - navigate down
  - parent branch
  - child branch
  - switch to parent
  - switch to child
  - move up stack
  - move down stack
  - next branch
  - previous branch
  - go to parent
  - go to child
---

# Stack Navigate

Navigate between branches in a PR stack using Charcoal's navigation, now with full worktree support!

## When to Use

Use this skill when the user wants to:
- "Go up" to the parent branch
- "Go down" to a child branch
- Traverse the PR stack
- Switch context to a dependency
- Navigate between worktrees

## Key Feature: Worktree-Aware Navigation

Navigation is worktree-aware. The commands will:
- ✅ Detect if parent/child branch has a worktree
- ✅ Output `cd` command to navigate to the worktree
- ✅ Fall back to checkout if no worktree exists
- ✅ Work seamlessly with Charcoal's stack tracking

## Instructions

1. Determine direction (up/down) from user request.

2. Execute the navigation command:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack up    # Go to parent (worktree-aware)
   $HOME/.dotfiles/.claude/scripts/stack down  # Go to child (worktree-aware)
   ```

   **Behavior:**
   - If target branch has a worktree: Outputs `cd /path/to/.trees/branch`
   - If target branch has no worktree: Suggests creating one or navigating in main repo
   - Requires Charcoal to be installed and initialized

3. Tell user to use `eval` for automatic navigation:
   ```bash
   eval $($HOME/.dotfiles/.claude/scripts/stack up)
   ```
   
   Or recommend setting up aliases:
   ```bash
   alias stup='eval $(~/.dotfiles/.claude/scripts/stack up)'
   alias stdown='eval $(~/.dotfiles/.claude/scripts/stack down)'
   ```

4. If command fails because Charcoal is missing/uninitialized:
   - Install: `brew install danerwilliams/tap/charcoal`
   - Initialize in the repo: `$HOME/.dotfiles/.claude/scripts/stack init`
   - Re-run: `$HOME/.dotfiles/.claude/scripts/stack up` or `down`

## Examples

User: "Go to the parent branch"
Action: `$HOME/.dotfiles/.claude/scripts/stack up`
Result: 
- If parent has worktree: `cd /path/to/.trees/parent`
- If not: Suggests creating worktree or checking out

User: "Navigate up in the stack"
Action: Suggest `eval $($HOME/.dotfiles/.claude/scripts/stack up)` for automatic cd

User: "Switch to the next PR in the stack"
Action: `$HOME/.dotfiles/.claude/scripts/stack down`
Result: Navigates to child worktree if it exists

User: "I'm in .trees/ui/, go to the API branch"
Action: `$HOME/.dotfiles/.claude/scripts/stack up`
Result: `cd /path/to/.trees/api` (if api has worktree)

## Workflow Integration

When working with worktrees:
```bash
# User is in .trees/ui/
# Wants to go to parent (feature/api)

stack up
# Output: cd /path/to/.trees/api

# User can:
# 1. Copy and paste the cd command
# 2. Use: eval $(stack up)
# 3. Use alias: stup (if configured)
```

## Worktree Session Handoff (tmux-based)

When navigating to a different worktree, use tmux to switch or open a session there.
Never use `EnterWorktree`/`ExitWorktree` — use the tmux approach instead.

**Pattern — navigate to a worktree:**

1. Run the navigation command to get the target path:
   ```bash
   TARGET_PATH=$($HOME/.dotfiles/.claude/scripts/stack up)   # or stack down
   # TARGET_PATH will be something like: cd /path/to/.trees/parent
   # Extract the actual path:
   WORKTREE_PATH=$(echo "$TARGET_PATH" | sed 's/^cd //')
   WINDOW_NAME=$(basename "$WORKTREE_PATH")
   ```

2. Detect the current tmux session and navigate to/create a window for that worktree:
   ```bash
   if [ -z "${TMUX:-}" ]; then
       # Not inside tmux — just navigate directly
       eval "$TARGET_PATH"
       exit 0
   fi
   
   TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null)
   if [ -z "$TMUX_SESSION" ]; then
       # Cannot get tmux session — navigate directly
       eval "$TARGET_PATH"
       exit 0
   fi
   
   # Use tmux select-window to check if window exists (more reliable than grep -Fxq)
   if tmux select-window -t "$TMUX_SESSION:$WINDOW_NAME" 2>/dev/null; then
       # Window already exists — already switched to it
       echo "Switched to tmux window: $WINDOW_NAME"
   else
       # Create new window and start claude in the worktree
       tmux new-window -t "$TMUX_SESSION" -n "$WINDOW_NAME" -c "$WORKTREE_PATH"
       sleep 0.3
       tmux send-keys -t "$TMUX_SESSION:$WINDOW_NAME" "claude" Enter
   fi
   ```

> The sanitized name is the branch name with the type prefix stripped:
> `feature/user-auth` → `"user-auth"`, `fix/bug` → `"bug"`

**If not inside tmux:** Just run the navigation command and `eval` its output:
```bash
eval $($HOME/.dotfiles/.claude/scripts/stack up)
```

**Key fix (T5):**
- Replaced `grep -Fxq` with `tmux select-window` check (more robust and atomic)
- Added proper error handling for missing `$TMUX` or `$TMUX_SESSION`
- Use `-c $WORKTREE_PATH` flag in `tmux new-window` to start in correct directory

## Related Skills

- **stack-create**: Create branches with worktrees + automatic tmux session in new window
- **stack-status**: View stack with worktree locations
- **stack-pr**: Create PRs from worktrees
- **stack-update**: Update and sync worktrees
