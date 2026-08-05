---
name: stack-clean
description: Removes a merged or stale branch and its associated worktree and tmux window. USE THIS SKILL when the user says "clean up branch", "remove worktree", "delete branch", "clean merged branch", or wants to tear down a finished stack entry.
triggers:
  - clean up branch
  - clean branch
  - remove worktree
  - delete branch
  - clean merged branch
  - tear down branch
  - remove stale branch
  - clean stack
  - delete worktree
---

# Stack Clean

Removes a merged or stale branch along with its worktree (`.trees/<name>`) and tmux window, keeping the repo tidy after merges.

## When to Use

- After a branch has been merged and its worktree/window are no longer needed
- To clean up a stale or abandoned branch
- During periodic stack maintenance

## Instructions

1. Identify the branch to clean (default: current branch):
   - If the user names a branch, use it
   - Otherwise use `$(git branch --show-current)`

2. Run the clean script:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack clean <branch>
   ```

   For branches that aren't fully merged (or have uncommitted worktree changes), add `--force`:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack clean <branch> --force
   ```

   The script will:
   - Close the tmux window for that branch (if open in the current session)
   - Remove the worktree at `.trees/<sanitized-name>` (refuses if dirty without `--force`)
   - Delete the local branch (refuses if unmerged without `--force`)

3. Remove the QMD collection for this worktree (if it exists):
   ```bash
   $HOME/.bun/bin/qmd collection remove "<worktree-dir-name>" 2>/dev/null || true
   ```
   Use the same sanitized name as the `.trees/<name>` directory (e.g. branch `feature/auth` → dir `auth` → collection name `auth`). Silently skip if `qmd` is not installed or collection doesn't exist.

4. Inform the user what was cleaned.

## Safety

- Never cleans `main`, `master`, or the detected trunk branch
- Refuses to remove a dirty worktree without `--force`
- Refuses to delete an unmerged branch without `--force`
- Switches away from the current window/branch before killing it

## Examples

User: "Clean up the feature/auth branch"
```bash
$HOME/.dotfiles/.claude/scripts/stack clean feature/auth
```

User: "Remove the worktree for fix/login-crash"
```bash
$HOME/.dotfiles/.claude/scripts/stack clean fix/login-crash
```

User: "Force-clean the stale feature/old-experiment branch"
```bash
$HOME/.dotfiles/.claude/scripts/stack clean feature/old-experiment --force
```
