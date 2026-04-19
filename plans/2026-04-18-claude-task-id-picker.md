# Plan: prefix+C — Interactive CLAUDE_CODE_TASK_LIST_ID picker

**Date:** 2026-04-18  
**Goal:** Replace the bare `claude` launch on `prefix+C` with an fzf popup that lets the user pick or create a task list ID, then opens Claude in a new window with `CLAUDE_CODE_TASK_LIST_ID` set.

---

## Context

Current binding (`tmux.conf:93`):
```
bind-key C new-window -c "#{pane_current_path}" "claude --dangerously-skip-permissions"
```

Target UX:
1. Press `prefix+C` → fzf popup appears
2. Three pre-filled choices at top:
   - Current git branch name (e.g. `feature/my-branch`)
   - Datetime-based ID (e.g. `task-20260418-143022`)
   - `[no task id]` — launch Claude without the env var
3. User can type to filter or enter a **custom** string (fzf `--print-query` mode)
4. On Enter → popup closes → new tmux window opens with Claude + the chosen env var

---

## Step 1 — Create `claude-task-launcher.sh`

**File:** `tmux/scripts/claude-task-launcher.sh`  
**Accepts:** Script exists, is executable, launches Claude with the chosen `CLAUDE_CODE_TASK_LIST_ID` value.

```bash
#!/usr/bin/env bash
# claude-task-launcher.sh — Interactive CLAUDE_CODE_TASK_LIST_ID picker for prefix+C
#
# Called by tmux display-popup. Receives the pane's current working path as $1.
# Presents three default choices + free-text entry via fzf, then opens a new
# tmux window with CLAUDE_CODE_TASK_LIST_ID set to the chosen value.

set -euo pipefail

PANE_PATH="${1:-$PWD}"
SENTINEL_NO_ID="[no task id]"

# ── Derive default candidates ─────────────────────────────────────────────────
branch=$(git -C "$PANE_PATH" branch --show-current 2>/dev/null || true)
datetime_id="task-$(date +%Y%m%d-%H%M%S)"

# Build the candidate list: branch first (most likely choice), then datetime, then no-id
candidates=()
[[ -n "$branch" ]] && candidates+=("$branch")
candidates+=("$datetime_id")
candidates+=("$SENTINEL_NO_ID")

# ── fzf picker ────────────────────────────────────────────────────────────────
# --print-query: if user types a custom value and presses Enter with no match,
#               the typed query is returned (line 1); selected entry is line 2.
# --no-sort: preserve our ordering (branch first)
chosen=$(printf '%s\n' "${candidates[@]}" \
    | fzf \
        --prompt="  Task list ID: " \
        --header="Enter: launch Claude · Esc: cancel · Type to enter custom ID" \
        --border \
        --height=40% \
        --no-sort \
        --print-query \
    2>/dev/null || true)

# fzf --print-query returns:
#   line 1 = typed query (empty if user selected without typing)
#   line 2 = selected item (empty if no match and user pressed Enter)
query=$(printf '%s\n' "$chosen" | sed -n '1p')
selection=$(printf '%s\n' "$chosen" | sed -n '2p')

# Priority: explicit selection > typed query > abort
task_id="${selection:-$query}"
[[ -z "$task_id" ]] && exit 0   # Esc or empty

# ── Launch Claude in a new window ─────────────────────────────────────────────
if [[ "$task_id" == "$SENTINEL_NO_ID" ]]; then
    # No env var — plain Claude
    tmux new-window -c "$PANE_PATH" "claude --dangerously-skip-permissions"
else
    tmux new-window -c "$PANE_PATH" -e "CLAUDE_CODE_TASK_LIST_ID=$task_id" "claude --dangerously-skip-permissions"
fi
```

**Notes:**
- `git -C "$PANE_PATH"` avoids `cd` (per CLAUDE.md working directory rules)
- `--dangerously-skip-permissions` flag passed to Claude (user-requested)
- `--print-query` enables free-text custom IDs without an extra input step
- Selection priority: explicit pick > typed query > abort (natural UX)

---

## Step 2 — Update `tmux.conf` binding

**File:** `tmux/tmux.conf`  
**Accepts:** Line 93 replaced; `source-file` or reload applies the change.

Replace:
```
bind-key C new-window -c "#{pane_current_path}" "claude --dangerously-skip-permissions"
```

With:
```
bind-key C display-popup -E -w 65% -h 30% -d "#{pane_current_path}" "~/.dotfiles/tmux/scripts/claude-task-launcher.sh '#{pane_current_path}'"
```

**Why `display-popup` instead of inline?**  
The ID must be chosen *before* the window is opened. A popup runs the picker and then calls `tmux new-window` internally — that's the standard pattern used by `claude-session-picker.sh` and `claude-worktree-select.sh`.

---

## Step 3 — Smoke test

```bash
# Make executable
chmod +x tmux/scripts/claude-task-launcher.sh

# Reload tmux config (if inside a running session)
tmux source ~/.config/tmux/tmux.conf   # or prefix+R if you have that bound

# Verify:
# 1. Press prefix+C — popup opens
# 2. Branch name (or datetime) appears as top choice
# 3. Press Enter — new window opens with CLAUDE_CODE_TASK_LIST_ID set
# 4. In the new Claude window, run: echo $CLAUDE_CODE_TASK_LIST_ID
```

---

## Acceptance Criteria

- [ ] `tmux/scripts/claude-task-launcher.sh` exists and is executable
- [ ] Popup shows branch name as first option (when inside a git repo)
- [ ] Datetime option always present as second choice
- [ ] `[no task id]` option launches Claude without the env var
- [ ] Typing a custom string and pressing Enter sets that as the ID
- [ ] Esc/cancel closes the popup without opening a window
- [ ] `CLAUDE_CODE_TASK_LIST_ID` is visible in the new Claude window's environment
- [ ] No `--dangerously-skip-permissions` flag is used

---

## Optional Enhancements (not in scope for this PR)

- **Persist recent IDs** — write chosen IDs to `~/.local/share/claude-task-ids` and surface them in fzf as a history section.
- **Worktree-aware** — if `TMUX_PANE` is inside a worktree, auto-derive the branch from the worktree path rather than running git.
- **Preview pane** — show recent `plans/active-context.md` content in fzf preview when a task ID maps to an existing plans/ file.
