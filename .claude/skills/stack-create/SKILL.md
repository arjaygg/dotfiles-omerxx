---
name: stack-create
description: Creates a new stacked branch for PR stacking workflows with full Charcoal integration. Supports worktrees for parallel development. USE THIS SKILL when user says "create worktree", "create branch on top of", "stack a branch", "worktree and branch", or mentions parallel development with git worktrees. Maintains Charcoal's navigation and restacking capabilities.
triggers:
  - create worktree
  - create branch on top of
  - stack a branch
  - new stacked branch
  - parallel development
  - git worktree
  - branch with worktree
  - worktree for branch
---

# Stack Create

Creates a new stacked branch with optional worktree for PR stacking workflows. Now with full Charcoal integration for worktrees!

## When to Use

**TRIGGER IMMEDIATELY** when the user's request contains any of these patterns:
- "create [a] worktree" + "branch"
- "create [a] branch on top of [branch]"
- "stack [a] branch on [branch]"
- "new stacked branch"
- "worktree for [branch]"
- "parallel development"
- "create worktree and branch"
- Any mention of "worktree" combined with "create" or "branch"

Use this skill when the user wants to:
- Create a new branch that builds on another branch (not just main)
- Start a PR stacking workflow
- Create a feature branch with a specific base branch
- Set up parallel development with git worktrees
- Use Charcoal's navigation (up/down) and restacking across worktrees

## Key Feature: Charcoal + Worktrees

**NEW:** Worktrees are now fully integrated with Charcoal! You get:
- ✅ Parallel development in separate directories
- ✅ Charcoal navigation (`stack up/down`) that's worktree-aware
- ✅ Automatic restacking with `stack restack`
- ✅ Visual stack display with worktree locations
- ✅ All Charcoal features work seamlessly with worktrees

## Instructions

1. Parse the user's request to identify:
   - `branch-name`: The name for the new branch (required)
   - `base-branch`: The branch to base on (default: current branch or main)
   - `worktree`: Boolean, whether to create a worktree (explicit request or implied by context)

2. Determine if worktree is needed:
   - If user explicitly asks for "worktree" or "parallel development" -> Set `worktree=true`
   - If user wants to work on multiple branches simultaneously -> Recommend worktrees
   - If user asks for "branch" only -> Create without worktree (can add later)

3. Execute the unified stack CLI:
   ```bash
   .claude/scripts/stack create <branch-name> [base-branch] [--worktree]
   ```

   This will automatically:
   - Create the branch (and worktree if requested)
   - Handle config copying for worktrees (IDE settings, MCP configs, .env)
   - Track branch in Charcoal (enables navigation and restacking)
   - Sync metadata for PR stacking
   - Enable worktree-aware Charcoal commands

4. Report the result to the user, including:
   - Branch created successfully
   - Worktree path (if applicable)
   - Base branch it's built on
   - Charcoal tracking status
   - Next steps (navigation commands, development workflow)

## Worktree Management

If user needs to add worktree to existing branch:
```bash
.claude/scripts/stack worktree-add <branch-name>
```

List all worktrees:
```bash
.claude/scripts/stack worktree-list
```

Remove a worktree:
```bash
.claude/scripts/stack worktree-remove <path>
```

## Navigation with Worktrees

When using worktrees with Charcoal:
- `stack up` - Navigate to parent branch (cd to worktree if exists)
- `stack down` - Navigate to child branch (cd to worktree if exists)
- `stack status` - Shows stack with worktree locations
- `stack restack` - Rebases entire stack and syncs all worktrees

## Examples

User: "Create a new stacked branch for user authentication with a worktree"
Action: `.claude/scripts/stack create feature/user-auth main --worktree`
Result: Branch + worktree created, tracked in Charcoal

User: "Create stacked worktrees for API, UI, and polish"
Actions:
```bash
.claude/scripts/stack create feature/api main --worktree
.claude/scripts/stack create feature/ui feature/api --worktree
.claude/scripts/stack create feature/polish feature/ui --worktree
```
Result: Three worktrees for parallel development, all tracked in Charcoal stack

User: "Stack a new branch called feature/ui on top of feature/backend"
Action: `.claude/scripts/stack create feature/ui feature/backend`
Result: Branch created without worktree, can add later with `worktree-add`

User: "Add a worktree for my existing feature/api branch"
Action: `.claude/scripts/stack worktree-add feature/api`
Result: Worktree created for existing branch, Charcoal navigation still works

## Workflow Example

```bash
# Setup parallel development
stack create feature/database main --worktree
stack create feature/api feature/database --worktree
stack create feature/ui feature/api --worktree

# Work in parallel (3 terminal windows)
cd .trees/database  # Terminal 1
cd .trees/api       # Terminal 2
cd .trees/ui        # Terminal 3

# Navigate using Charcoal (from any terminal)
stack up            # Goes to parent worktree
stack down          # Goes to child worktree
stack status        # Shows stack with worktree info

# After making changes to database, restack everything
stack restack       # Rebases api and ui, syncs all worktrees
```

## Related Skills

- **stack-navigate**: Move between branches (worktree-aware)
- **stack-status**: View stack hierarchy with worktree info
- **stack-pr**: Create Azure DevOps PR
- **stack-update**: Update after merge (syncs worktrees)
