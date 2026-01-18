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
   .claude/scripts/stack up    # Go to parent (worktree-aware)
   .claude/scripts/stack down  # Go to child (worktree-aware)
   ```

   **Behavior:**
   - If target branch has a worktree: Outputs `cd /path/to/.trees/branch`
   - If target branch has no worktree: Suggests creating one or navigating in main repo
   - Requires Charcoal to be installed and initialized

3. Tell user to use `eval` for automatic navigation:
   ```bash
   eval $(.claude/scripts/stack up)
   ```
   
   Or recommend setting up aliases:
   ```bash
   alias stup='eval $(~/.claude/scripts/stack up)'
   alias stdown='eval $(~/.claude/scripts/stack down)'
   ```

4. If command fails (Charcoal not installed), fall back to git:
   - Find parent/child branch name from `.git/pr-stack-info`
   - `git checkout <branch>`

## Examples

User: "Go to the parent branch"
Action: `.claude/scripts/stack up`
Result: 
- If parent has worktree: `cd /path/to/.trees/parent`
- If not: Suggests creating worktree or checking out

User: "Navigate up in the stack"
Action: Suggest `eval $(.claude/scripts/stack up)` for automatic cd

User: "Switch to the next PR in the stack"
Action: `.claude/scripts/stack down`
Result: Navigates to child worktree if it exists

User: "I'm in .trees/ui/, go to the API branch"
Action: `.claude/scripts/stack up`
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

## Related Skills

- **stack-create**: Create branches with worktrees
- **stack-status**: View stack with worktree locations
- **stack-pr**: Create PRs from worktrees
- **stack-update**: Update and sync worktrees
