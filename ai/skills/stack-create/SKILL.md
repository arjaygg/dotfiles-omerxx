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

Creates a new stacked branch with a worktree (default) for PR stacking workflows, with full Charcoal integration.

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

## Key Feature: Default Worktrees

Worktrees are created by **default** (no flag needed). You also get:
- ✅ Parallel development in separate `.trees/` directories
- ✅ Charcoal navigation (`stack up/down`) that's worktree-aware
- ✅ Automatic restacking with `stack restack`
- ✅ Visual stack display with worktree locations

## Instructions

1. Parse the user's request to identify:
   - `branch-name`: The name for the new branch (required)
   - `base-branch`: The branch to base on (default: current branch or main)

2. **No manual worktree detection.** The `stack create` script resolves the **main repository root** (parent of `.trees/`) even when you run it from inside `.trees/<some-branch>/`, so the new worktree is always created as a **sibling** under `<main-repo>/.trees/<sanitized-name>/`, never nested as `.trees/foo/.trees/bar`.

3. Execute the unified stack CLI (same invocation from any directory in the repo or its worktrees):
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch]
   ```

   Capture the **absolute worktree path** from the script output (line starting with `Path:` / `📂 Path:`) for the next steps. If needed, you can also resolve it with `git worktree list` after the command.

   This automatically:
   - Creates the branch and worktree at `<main-repo>/.trees/<sanitized-name>/`
   - Copies configs (MCP paths updated, .vscode, .serena copied)
   - Tracks branch in Charcoal (navigation and restacking)
   - Enables worktree-aware Charcoal commands

4. **Bootstrap `.claude/settings.local.json`** in the **new** worktree (use `WORKTREE_PATH` from step 3, not `$(pwd)/.trees/...`):
   ```bash
   LOCAL_SETTINGS="$WORKTREE_PATH/.claude/settings.local.json"
   if [ ! -f "$LOCAL_SETTINGS" ]; then
     mkdir -p "$(dirname "$LOCAL_SETTINGS")"
     cat > "$LOCAL_SETTINGS" << 'EOF'
   {
     "permissions": {
       "defaultMode": "acceptEdits"
     }
   }
   EOF
   fi
   ```
   This ensures the new session never prompts for permission on every tool call.
   Skip if the file already exists (respect any existing local overrides).

5. **Optionally create a draft PR** — ask the user if they'd like a draft PR opened immediately:
   > "Worktree created. Want me to open a draft PR now so reviewers can track progress?"

   If yes:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack pr "$(git branch --show-current)" "" "" --draft
   ```
   If no (or user doesn't respond), skip.

6. **Inform the user** — print the absolute worktree path and entry options:
   ```
   ✅ Worktree ready at <WORKTREE_PATH>
   → Work on files directly using absolute paths (Read/Edit/Bash with full path)
   → Enter interactively: EnterWorktree or  cd <WORKTREE_PATH> && claude
   → Dispatch a background agent: claude agents
   ```

## Opting out of worktrees

`stack create` always adds a linked worktree. If the user truly wants **only** a local branch without a worktree, use plain Git (e.g. `git checkout -b ...` from the desired checkout) and `gt branch track` as needed — do not rely on a `--no-worktree` flag on `stack create`.

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
Result: Branch + worktree at `.trees/user-auth`. Session accesses files via absolute paths.

User: "Create stacked worktrees for API, UI, and polish"
Actions:
```bash
$HOME/.dotfiles/.claude/scripts/stack create feature/api main
$HOME/.dotfiles/.claude/scripts/stack create feature/ui feature/api
$HOME/.dotfiles/.claude/scripts/stack create feature/polish feature/ui
```
Result: Three independent worktrees — work on each via absolute paths or dispatch agents.

User: "Stack a new branch without a worktree"
Action: Use `git checkout -b` / Charcoal tracking manually; `stack create` always creates a worktree.

User: "Create a branch for the next story" (while already inside `.trees/some-feature/`)
Action: `$HOME/.dotfiles/.claude/scripts/stack create feature/next-story [base]`
Result: New worktree at `<main-repo>/.trees/next-story/` (sibling of `some-feature`, not nested under it)

## Related Skills

- **stack-navigate**: Move between branches (worktree-aware) via tmux
- **stack-status**: View stack hierarchy with worktree info
- **stack-pr**: Create PR (auto-detects GitHub vs Azure DevOps)
- **stack-update**: Update after merge (syncs worktrees)
