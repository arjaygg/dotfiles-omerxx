---
name: stack-status
description: Shows the current PR stack status and branch hierarchy with worktree locations. USE THIS SKILL when user says "show stack", "stack status", "show PR stack", "show branches", "where am I in stack", "list worktrees", "show dependencies", or wants to see their PR stack hierarchy.
triggers:
  - show stack
  - stack status
  - show PR stack
  - show branches
  - where am I in stack
  - list worktrees
  - show dependencies
  - what's my stack
  - view stack
  - branch hierarchy
  - PR dependencies
  - show my PRs
  - current stack
---

# Stack Status

Displays the current state of the PR stack, including branch hierarchy, PR status, and worktree locations.

## When to Use

Use this skill when the user wants to:
- See the full stack of branches
- Check which PRs are merged/open
- Understand branch dependencies
- Visualize the tree structure
- **NEW:** See which branches have worktrees
- **NEW:** Find worktree locations

## Key Feature: Worktree Information

**NEW:** Status now shows worktree locations! The display includes:
- ✅ Visual tree of branches (via Charcoal)
- ✅ Worktree locations marked with `[WT: path]`
- ✅ PR status for each branch
- ✅ Current position in the stack
- ✅ Easy identification of parallel development setup

## Instructions

**CRITICAL: Execute the command IMMEDIATELY without any investigation or file reading.**

1. Run this command RIGHT NOW:
   ```bash
   ~/.dotfiles/.claude/scripts/pr-stack/list-stack.sh
   ```

2. DO NOT:
   - Read AGENTS.md or any other files
   - Look for pr-stack or charcoal
   - Investigate the codebase
   - Do any preparation work

3. JUST execute the command above and show the output to the user.

4. The output will show:
   - Visual tree of branches (via Charcoal if available)
   - Worktree locations for each branch (if exists)
   - PR status for each branch
   - Current position in the stack

5. Interpret the markers:
   - `[WT: .trees/api]` - Branch has a worktree at that location
   - No `[WT:]` marker - Branch has no worktree (only in main repo)

## Output Example

```
╔════════════════════════════════════════════════════════════╗
║              STACK STATUS (with Worktrees)                 ║
╚════════════════════════════════════════════════════════════╝

main
├── feature/database [WT: .trees/database]
│   └── feature/api [WT: .trees/api]
│       └── feature/ui [WT: .trees/ui]
└── hotfix/security

════════════════════════════════════════════════════════════

Native Stack View (with PR info):
feature/database → main (PR #123: Open)
feature/api → feature/database (PR #124: Open)
feature/ui → feature/api (PR #125: Open)
hotfix/security → main (PR #126: Merged)
```

## Examples

User: "Show me my PR stack"
Action: `$HOME/.dotfiles/.claude/scripts/stack status`
Result: Shows stack with worktree locations

User: "Where am I in the stack?"
Action: `$HOME/.dotfiles/.claude/scripts/stack status`
Result: Shows current branch and its position

User: "Which branches have worktrees?"
Action: `$HOME/.dotfiles/.claude/scripts/stack status`
Result: Shows all branches with `[WT: path]` markers

User: "Show me the full picture of my parallel development setup"
Action: `$HOME/.dotfiles/.claude/scripts/stack status`
Result: Complete view of stack + worktrees + PR status

## Workflow Integration

Use this to:
- **Plan navigation**: See where worktrees are before using `stack up/down`
- **Check setup**: Verify all branches have worktrees for parallel development
- **Understand dependencies**: See which PRs depend on which
- **Find worktrees**: Quickly locate worktree paths for cd commands

## Related Skills

- **stack-create**: Create branches with worktrees
- **stack-navigate**: Navigate between worktrees
- **stack-pr**: Create PRs from worktrees
- **stack-update**: Update and sync worktrees
