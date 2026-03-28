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

**NEW:** Navigation is now worktree-aware! The commands will:
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

## Worktree Session Handoff (EnterWorktree / ExitWorktree)

When the current Claude Code session was entered via `EnterWorktree`, navigating to
a different worktree requires a session handoff so Claude Code's CWD follows you.

**Pattern — navigate up (to parent branch):**
1. Call `ExitWorktree({action: "keep"})` to leave the current worktree session
2. Run `$HOME/.dotfiles/.claude/scripts/stack up` to determine the parent path
3. Call `EnterWorktree({name: "<parent-sanitized-name>"})` to enter the parent worktree

**Pattern — navigate down (to child branch):**
1. Call `ExitWorktree({action: "keep"})` to leave the current worktree session
2. Run `$HOME/.dotfiles/.claude/scripts/stack down` to determine the child path
3. Call `EnterWorktree({name: "<child-sanitized-name>"})` to enter the child worktree

> The sanitized name is the branch name with the type prefix stripped:
> `feature/user-auth` → `"user-auth"`, `fix/bug` → `"bug"`

> **Note on bug #36205:** Until the EnterWorktree/WorktreeCreate hook bug is fixed,
> `EnterWorktree` creates a session in `.claude/worktrees/` (not `.trees/`). The
> `.trees/<name>` worktree remains the authoritative location for git operations.
> For full isolation, open a new Claude Code session: `claude` from `.trees/<name>`.

**If you're NOT in an EnterWorktree session** (normal Claude Code session):
- Just run the navigation commands and `eval` the output in your terminal
- No ExitWorktree/EnterWorktree needed

## Related Skills

- **stack-create**: Create branches with worktrees + automatic EnterWorktree session entry
- **stack-status**: View stack with worktree locations
- **stack-pr**: Create PRs from worktrees
- **stack-update**: Update and sync worktrees
