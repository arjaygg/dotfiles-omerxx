---
name: stack-merge
description: Completes a PR merge in Azure DevOps and updates the entire stack. USE THIS SKILL when user says "merge PR", "complete PR", "ship PR", "merge pull request", "complete the merge", or wants to merge a PR and update dependent branches.
triggers:
  - merge PR
  - complete PR
  - ship PR
  - merge pull request
  - complete the merge
  - finish PR
  - merge and update
  - ship this PR
  - land PR
  - land the PR
---

# Stack Merge

Merges a Pull Request and rebases dependent branches in the stack.

## When to Use

Use this skill when the user wants to:
- Merge a specific PR
- "Ship" a feature in the stack
- Update the stack after a PR has been approved and completed

## Instructions

1. Identify the PR ID from the user's request.

2. Execute the merge command:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack merge <pr-id>
   ```

   This will:
   - Complete the PR in Azure DevOps
   - Restack dependent branches via Charcoal (`gt restack`)
   - Sync worktrees after restack (if any)

3. Report status to user:
   - Confirm merge success
   - List any branches that were rebased
   - Check if any conflicts occurred during rebase

4. **Close the merged branch's tmux window** (if open) and switch to the parent:

   The sanitized window name is the branch name with its type prefix stripped:
   - `feature/user-auth` → `user-auth`
   - `fix/bug` → `bug`

   ```bash
   MERGED_WINDOW=$(echo "$SOURCE_BRANCH" | sed -E 's|^(feature|feat|bugfix|fix|hotfix|release|chore)/||')
   TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null || true)

   if [ -n "$TMUX_SESSION" ]; then
       # Find parent branch window and switch to it first
       PARENT_BRANCH=$(gt branch info "$SOURCE_BRANCH" 2>/dev/null | grep "^Parent:" | sed 's/^Parent: //' | tr -d ' ' || true)
       PARENT_WINDOW=$(echo "${PARENT_BRANCH:-}" | sed -E 's|^(feature|feat|bugfix|fix|hotfix|release|chore)/||')

       if [ -n "$PARENT_WINDOW" ] && \
          tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' 2>/dev/null | grep -Fxq "$PARENT_WINDOW"; then
           tmux select-window -t "$TMUX_SESSION:$PARENT_WINDOW"
       fi

       tmux kill-window -t "$TMUX_SESSION:$MERGED_WINDOW" 2>/dev/null || true
   fi
   ```

   Skip if not inside tmux (`$TMUX` is unset).

   **Cursor Desktop / no tmux:** No window management needed. Work continues in the
   current session. To move to the parent branch's worktree after merge, run:
   ```bash
   eval $($HOME/.dotfiles/.claude/scripts/stack up)
   ```

## Examples

User: "Merge PR #12345"
Action: `$HOME/.dotfiles/.claude/scripts/stack merge 12345`

User: "Ship the current PR"
Action: First find PR ID, then `$HOME/.dotfiles/.claude/scripts/stack merge <id>`
