---
name: stack-create
description: Creates a new stacked branch for PR stacking workflows with full Charcoal integration. Worktrees are created by default. USE THIS SKILL when user says "create worktree", "create branch on top of", "stack a branch", "worktree and branch", or mentions parallel development with git worktrees. Maintains Charcoal's navigation and restacking capabilities.
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

Creates a new stacked branch with a worktree (default) for PR stacking workflows, with full Charcoal integration. Automatically writes a rich session handoff and opens a new Claude Code session in the worktree via tmux.

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

## Key Feature: Default Worktrees + tmux Session Integration

Worktrees are created by **default** (no flag needed). You also get:
- ✅ Parallel development in separate `.trees/` directories
- ✅ Charcoal navigation (`stack up/down`) that's worktree-aware
- ✅ Automatic restacking with `stack restack`
- ✅ Visual stack display with worktree locations
- ✅ New Claude Code session opened in a tmux window inside the worktree

## Instructions

1. Parse the user's request to identify:
   - `branch-name`: The name for the new branch (required)
   - `base-branch`: The branch to base on (default: current branch or main)
   - `no-worktree`: Pass `--no-worktree` only if user explicitly says they don't want a worktree

2. Execute the unified stack CLI (**worktree is created by default**):
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch]
   ```

   To skip worktree creation:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch] --no-worktree
   ```

   This automatically:
   - Creates the branch and worktree at `.trees/<sanitized-name>`
   - Copies configs (MCP paths updated, .vscode, .serena copied)
   - Tracks branch in Charcoal (navigation and restacking)
   - Enables worktree-aware Charcoal commands

3. **Open a new Claude Code session in the worktree** (after confirming worktree was created):
   Derive the `name` from the branch by stripping the type prefix:
   - `feature/user-auth` → name = `"user-auth"`
   - `fix/cursor-issue` → name = `"cursor-issue"`
   - `chore/cleanup` → name = `"cleanup"`

   Use tmux to open a new window in the current session and start Claude there.
   Detect the current session name at runtime — never hardcode it:
   ```bash
   WORKTREE_PATH="$(pwd)/.trees/<sanitized-name>"
   WINDOW_NAME="<sanitized-name>"
   TMUX_SESSION=$(tmux display-message -p '#S')
   tmux new-window -t "$TMUX_SESSION" -n "$WINDOW_NAME"
   sleep 0.3
   tmux send-keys -t "$TMUX_SESSION:$WINDOW_NAME" "cd $WORKTREE_PATH && claude" Enter
   ```

   If `$TMUX` is unset (not inside tmux), skip the tmux commands and instead inform
   the user to open a new terminal and run `cd .trees/<sanitized-name> && claude`.

   This gives the new session a properly isolated CWD — the new Claude instance will
   start fresh in the worktree and pick up `plans/session-handoff.md` automatically.

4. **Write a rich session handoff** before opening the new session, so the new Claude
   instance starts with context from the current session:
   ```bash
   mkdir -p .trees/<sanitized-name>/plans

   # Capture current session context (empty string if files don't exist)
   ACTIVE_CONTEXT=$([ -f plans/active-context.md ] && cat plans/active-context.md || echo "*(none)*")
   PROGRESS=$([ -f plans/progress.md ] && cat plans/progress.md || echo "*(none)*")
   DECISIONS=$([ -f plans/decisions.md ] && cat plans/decisions.md || echo "*(none)*")

   cat > .trees/<sanitized-name>/plans/session-handoff.md << EOF
   # Session Handoff
   status: pending
   branch: <full-branch-name>
   created_at: $(date +%Y-%m-%d)

   ## Context from parent session

   ### active-context.md
   $ACTIVE_CONTEXT

   ### progress.md
   $PROGRESS

   ### decisions.md
   $DECISIONS
   EOF
   ```
   Only write if the worktree was actually created (skip for `--no-worktree`).
   Write the handoff **before** running the tmux command in step 3 so the file is
   present when Claude starts.

5. Inform the user:
   - Branch and worktree created at `.trees/<sanitized-name>`
   - Handoff written to `.trees/<sanitized-name>/plans/session-handoff.md`
   - New Claude session opened in tmux window `<sanitized-name>` (in the current tmux session)
   - They can switch to it with: `tmux select-window -t "$TMUX_SESSION:<sanitized-name>"`

## Opting out of worktrees

If the user explicitly does NOT want a worktree:
```bash
$HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch] --no-worktree
```
Do **not** write a handoff or open a tmux session in this case.

## Worktree Management

Add worktree to existing branch:
```bash
$HOME/.dotfiles/.claude/scripts/stack worktree-add <branch-name>
```

List all worktrees:
```bash
$HOME/.dotfiles/.claude/scripts/stack worktree-list
```

Remove a worktree (refuses if dirty):
```bash
$HOME/.dotfiles/.claude/scripts/stack worktree-remove <path>
```

## Navigation with Worktrees

When using worktrees with Charcoal:
- `stack up` - Navigate to parent branch (cd to worktree if exists)
- `stack down` - Navigate to child branch (cd to worktree if exists)
- `stack status` - Shows stack with worktree locations
- `stack restack` - Rebases entire stack and syncs all worktrees

## Examples

User: "Create a new stacked branch for user authentication"
Action: `$HOME/.dotfiles/.claude/scripts/stack create feature/user-auth main`
Then: write handoff to `.trees/user-auth/plans/session-handoff.md`, open tmux window `dev:user-auth` with `cd .trees/user-auth && claude`
Result: Branch + worktree at `.trees/user-auth`, new Claude session ready in tmux

User: "Create stacked worktrees for API, UI, and polish"
Actions:
```bash
$HOME/.dotfiles/.claude/scripts/stack create feature/api main
$HOME/.dotfiles/.claude/scripts/stack create feature/ui feature/api
$HOME/.dotfiles/.claude/scripts/stack create feature/polish feature/ui
```
Then write handoffs and open tmux windows for each: `dev:api`, `dev:ui`, `dev:polish`

User: "Stack a new branch without a worktree"
Action: `$HOME/.dotfiles/.claude/scripts/stack create feature/ui feature/backend --no-worktree`
(No EnterWorktree call)

## Related Skills

- **stack-navigate**: Move between branches (worktree-aware), with EnterWorktree/ExitWorktree session handoff
- **stack-status**: View stack hierarchy with worktree info
- **stack-pr**: Create Azure DevOps PR
- **stack-update**: Update after merge (syncs worktrees)
