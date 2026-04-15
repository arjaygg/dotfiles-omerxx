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

2. **Detect if already inside a worktree** before creating anything:
   ```bash
   CURRENT_PATH="$(pwd)"
   # Check if current path contains /.trees/ — indicates we're already in a worktree
   if echo "$CURRENT_PATH" | grep -q "/.trees/"; then
     IN_WORKTREE=true
   else
     IN_WORKTREE=false
   fi
   ```
   **If `IN_WORKTREE=true`:** Do NOT create a new worktree. Just create the branch in the current worktree using `--no-worktree`. Skip steps 3–5 (handoff and tmux).

3. Execute the unified stack CLI:
   - **If already in a worktree** (skip new worktree):
     ```bash
     $HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch] --no-worktree
     ```
   - **If NOT in a worktree** (default — create worktree):
     ```bash
     $HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch]
     ```
   - **If user explicitly says no worktree:**
     ```bash
     $HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch] --no-worktree
     ```

   This automatically:
   - Creates the branch and worktree at `.trees/<sanitized-name>` (when not already in one)
   - Copies configs (MCP paths updated, .vscode, .serena copied)
   - Tracks branch in Charcoal (navigation and restacking)
   - Enables worktree-aware Charcoal commands

4. **Bootstrap `.claude/settings.local.json`** in the worktree (only when a worktree was created — i.e., `IN_WORKTREE=false`):
   ```bash
   WORKTREE_PATH="$(pwd)/.trees/<sanitized-name>"
   LOCAL_SETTINGS="$WORKTREE_PATH/.claude/settings.local.json"
   if [ ! -f "$LOCAL_SETTINGS" ]; then
     mkdir -p "$WORKTREE_PATH/.claude"
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

5. **Open a new Claude Code session in the worktree** (only when `IN_WORKTREE=false` and worktree was created):
   Derive the `name` from the branch by stripping the type prefix:
   - `feature/user-auth` → name = `"user-auth"`
   - `fix/cursor-issue` → name = `"cursor-issue"`
   - `chore/cleanup` → name = `"cleanup"`

   When not inside tmux (e.g. Cursor Desktop), the script outputs `cd <worktree-path>`
   so the agent can `eval` it to navigate. Use: `eval $($HOME/.dotfiles/.claude/scripts/stack create <name> [base])`

   When inside tmux, open a new window in the current session and start Claude there.
   Detect the current session name at runtime — never hardcode it:
   ```bash
   WORKTREE_PATH="$(pwd)/.trees/<sanitized-name>"
   WINDOW_NAME="<sanitized-name>"
   
   if [ -z "${TMUX:-}" ]; then
       # Cursor Desktop / no-tmux: output cd command for agent to eval
       # Run: eval $($HOME/.dotfiles/.claude/scripts/stack create <name> [base])
       echo "cd $WORKTREE_PATH"
       exit 0
   fi
   
   TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null)
   if [ -z "$TMUX_SESSION" ]; then
       echo "⚠️  Could not determine tmux session. To open the new worktree in tmux:"
       echo "   cd $WORKTREE_PATH && claude"
       exit 0
   fi
   
   # Use tmux select-window to test if window exists (simpler & more reliable than grep)
   # If select succeeds, window exists; if it fails, create it
   if tmux select-window -t "$TMUX_SESSION:$WINDOW_NAME" 2>/dev/null; then
       # Window already exists — already switched to it
       echo "Switched to existing tmux window: $WINDOW_NAME"
   else
       # Window doesn't exist — create it and start Claude
       tmux new-window -t "$TMUX_SESSION" -n "$WINDOW_NAME" -c "$WORKTREE_PATH"
       sleep 0.3
       tmux send-keys -t "$TMUX_SESSION:$WINDOW_NAME" "claude" Enter
       
       # Sync tmux bridge display if available
       sleep 0.5
       if [ -f ~/.dotfiles/tmux/scripts/claude-tmux-bridge.sh ]; then
           ~/.dotfiles/tmux/scripts/claude-tmux-bridge.sh session-start 2>/dev/null || true
       fi
   fi
   ```

   **Key fixes for window-exists bug (T5):**
   - Use `tmux select-window` instead of `grep -Fxq` (more direct, avoids formatting edge cases)
   - Add early exit if `$TMUX` or `$TMUX_SESSION` is empty (proper error handling)
   - Use `-c $WORKTREE_PATH` in `tmux new-window` to avoid `cd` command issues
   - Cleaner, more maintainable code
   
   **Why this fixes the dotfiles issue:**
   - The original `grep -Fxq` could fail with certain window names or tmux configurations
   - `tmux select-window` is atomic and foolproof: it either succeeds or fails
   - Explicit error messages help debug when tmux isn't available

   This gives the new session a properly isolated CWD — the new Claude instance will
   start fresh in the worktree and pick up `plans/session-handoff.md` automatically.

6. **Write a rich session handoff** before opening the new session, so the new Claude
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
   Write the handoff **before** running the tmux command in step 4 so the file is
   present when Claude starts.

7. **Optionally create a draft PR** — ask the user if they'd like a draft PR opened immediately:
   > "Worktree created. Want me to open a draft PR now so reviewers can track progress?"

   If yes:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack pr "$(git branch --show-current)" "" "" --draft
   ```
   If no (or user doesn't respond), skip.

8. Inform the user:
   - If `IN_WORKTREE=true`: Branch created in current worktree (no new worktree created)
   - If `IN_WORKTREE=false` + **tmux**: Branch and worktree created, handoff written, tmux window opened
   - If `IN_WORKTREE=false` + **no tmux (Cursor Desktop)**: Branch and worktree created at `.trees/<sanitized-name>`, handoff written. The skill outputs a `cd` command — use `eval $(...stack create ...)` to navigate to the new worktree automatically.

## Opting out of worktrees

Worktrees are skipped automatically when:
1. **Already inside a `.trees/` worktree** — detected by checking if `$(pwd)` contains `/.trees/`
2. **User explicitly requests no worktree** — pass `--no-worktree`

```bash
$HOME/.dotfiles/.claude/scripts/stack create <branch-name> [base-branch] --no-worktree
```
Do **not** write a handoff or open a tmux session in either case.

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
Then: write handoff to `.trees/user-auth/plans/session-handoff.md`
- **tmux**: opens window `dev:user-auth` with `claude`
- **Cursor Desktop / no tmux**: outputs `cd .trees/user-auth` — agent evals it to navigate
Result: Branch + worktree at `.trees/user-auth`, session (or cwd) in the worktree

User: "Create stacked worktrees for API, UI, and polish"
Actions:
```bash
$HOME/.dotfiles/.claude/scripts/stack create feature/api main
$HOME/.dotfiles/.claude/scripts/stack create feature/ui feature/api
$HOME/.dotfiles/.claude/scripts/stack create feature/polish feature/ui
```
Then write handoffs and open tmux windows for each: `api`, `ui`, `polish` (in current tmux session)

User: "Stack a new branch without a worktree"
Action: `$HOME/.dotfiles/.claude/scripts/stack create feature/ui feature/backend --no-worktree`
(No tmux session opened)

User: "Create a branch for the next story" (while already inside `.trees/some-feature/`)
Detection: `$(pwd)` contains `/.trees/` → `IN_WORKTREE=true`
Action: `$HOME/.dotfiles/.claude/scripts/stack create feature/next-story --no-worktree`
Result: Branch created in the current worktree — no new `.trees/` directory created

## Related Skills

- **stack-navigate**: Move between branches (worktree-aware) via tmux
- **stack-status**: View stack hierarchy with worktree info
- **stack-pr**: Create PR (auto-detects GitHub vs Azure DevOps)
- **stack-update**: Update after merge (syncs worktrees)
