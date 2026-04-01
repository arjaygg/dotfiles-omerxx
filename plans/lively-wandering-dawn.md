# Plan: tmux + Claude Code Productivity Enhancements
_Date: 2026-04-01_

## Context

The existing tmux ↔ Claude Code integration is already sophisticated: session lifecycle hooks, window naming, pane-level state variables (`@claude_status`, `@claude_project`, `@claude_branch`), a session picker (Ctrl+A w), and a worktree selector (Ctrl+A W). The catppuccin status bar shows a ⚙/· icon and project name.

**What's missing:**
- Visual urgency/liveliness beyond a text icon (no color differentiation between idle/working windows)
- Elapsed time when Claude is grinding through a task
- A skill/command picker to inject prompts without leaving tmux
- A cross-repo launcher (current worktree selector is scoped to the current repo)
- Activity monitoring — no visual alert when Claude finishes in a background window

---

## Step 1 — Activity Monitoring + Finish Notifications
**Files:** `tmux/tmux.conf`, `tmux/scripts/claude-tmux-bridge.sh`
**Accepts:** Windows with new output since last visit get highlighted; a 2-second toast appears when Claude finishes a response.

- [ ] Add to `tmux.conf` (after the pane-border lines):
  ```tmux
  setw -g monitor-activity on
  set -g window-status-activity-style "bg=colour214,fg=black,bold"
  set -g visual-activity off
  ```
  `colour214` is tmux's amber/orange — distinct from catppuccin but not alarm-red.

- [ ] In bridge `activity-stop` action, add after `set_pane_var`:
  ```bash
  local project
  project=$(get_pane_var "claude_project")
  tmux display-message -d 2000 "✓ Claude: ${project:-done}"
  ```

---

## Step 2 — Elapsed Timer in Working State
**Files:** `tmux/scripts/claude-tmux-bridge.sh`, `tmux/scripts/catppuccin-claude.sh`, `tmux/scripts/claude-session-picker.sh`
**Accepts:** When Claude is working, the status bar module shows "⚙ project 1m42s" and the session picker shows an elapsed column.

- [ ] Bridge `activity-start`: add `set_pane_var "claude_activity_start" "$(date +%s)"`
- [ ] Bridge `activity-stop`: add `unset_pane_var "claude_activity_start"`
- [ ] Bridge `session-stop`: add `unset_pane_var "claude_activity_start"` to the cleanup loop
- [ ] `catppuccin-claude.sh` `show_claude()`: when status == "working", read `@claude_activity_start`, compute elapsed, append to text:
  ```bash
  local start
  start="$(tmux display-message -p '#{@claude_activity_start}' 2>/dev/null)"
  if [[ -n "$start" ]]; then
      local now elapsed
      now=$(date +%s)
      elapsed=$((now - start))
      if [[ $elapsed -lt 60 ]]; then
          text="${text} ${elapsed}s"
      else
          text="${text} $((elapsed / 60))m"
      fi
  fi
  ```
- [ ] Session picker: add `elapsed` column — read `#{@claude_activity_start}` per pane in the `tmux list-panes` format string and format inline with awk

---

## Step 3 — Color-coded Working State in Window Titles
**Files:** `tmux/tmux.conf`
**Accepts:** Currently-working Claude windows show the ⚙ icon in amber/yellow; idle-with-Claude windows show · in dimmed color; non-Claude windows unchanged.

The catppuccin format strings already use `#{@claude_status}` (resolved from the pane's active pane). Extend them with inline `#[fg=...]` color codes:

- [ ] Modify `@catppuccin_window_current_text` in `tmux.conf`:
  ```tmux
  set -g @catppuccin_window_current_text \
    "#{?#{@claude_status},#{?#{==:#{@claude_status},working},#[fg=colour214]⚙ #[fg=default],· }#{@claude_project}#{?#{@claude_branch},[#{@claude_branch}],},#W}#{?window_zoomed_flag, (),}"
  ```
  Working → `colour214` (amber) ⚙ icon; idle → default color · icon.

- [ ] Modify `@catppuccin_window_default_text` similarly to show the idle indicator for non-current Claude windows:
  ```tmux
  set -g @catppuccin_window_default_text \
    "#{?#{@claude_status},#{?#{==:#{@claude_status},working},#[fg=colour214]⚙ #[fg=default],· }#{@claude_project},#W}"
  ```

---

## Step 4 — Skill / Command Picker (Ctrl+A P)
**Files:** `tmux/scripts/skill-picker.sh` (new), `tmux/tmux.conf`
**Accepts:** `Ctrl+A P` opens an fzf popup listing all skills and commands; Enter pastes the invocation into the current pane; Alt+P shows full file content.

### Script: `tmux/scripts/skill-picker.sh`

```bash
#!/usr/bin/env bash
# skill-picker.sh — fzf picker for ai/skills, ai/commands, .claude/commands
# Enter: paste invocation into current pane
# Alt-P: show full file preview

set -euo pipefail

# Resolve dotfiles root regardless of CWD
DOTFILES="${DOTFILES_ROOT:-$HOME/.dotfiles}"

# Build list: TYPE | NAME | PATH
items=""

# Skills: ai/skills/*/SKILL.md  → skill name = directory name
while IFS= read -r path; do
    dir=$(dirname "$path")
    name=$(basename "$dir")
    items="${items}skill\t${name}\t${path}\n"
done < <(find "$DOTFILES/ai/skills" -maxdepth 2 -name "SKILL.md" -o -name "skill.md" 2>/dev/null | sort)

# Commands: ai/commands/*.md
while IFS= read -r path; do
    name=$(basename "$path" .md)
    items="${items}command\t${name}\t${path}\n"
done < <(find "$DOTFILES/ai/commands" -maxdepth 1 -name "*.md" 2>/dev/null | sort)

# Slash commands: .claude/commands/*.md
while IFS= read -r path; do
    name=$(basename "$path" .md)
    items="${items}/cmd\t/${name}\t${path}\n"
done < <(find "$DOTFILES/.claude/commands" -maxdepth 1 -name "*.md" 2>/dev/null | sort)

# Saved prompts: ai/prompts/*.md (optional, may not exist)
while IFS= read -r path; do
    name=$(basename "$path" .md)
    items="${items}prompt\t${name}\t${path}\n"
done < <(find "$DOTFILES/ai/prompts" -maxdepth 1 -name "*.md" 2>/dev/null | sort)

if [[ -z "$items" ]]; then
    echo "No skills or commands found in $DOTFILES"
    read -r; exit 0
fi

display=$(printf "%b" "$items" | awk -F'\t' '{
    printf "%-9s  %-30s  %s\n", $1, $2, $3
}')

selected=$(printf '%s\n' "$display" \
    | fzf \
        --prompt="  skills & commands: " \
        --header="Enter: paste invocation · Alt-P: preview content · Esc: close" \
        --border \
        --height=80% \
        --ansi \
        --bind='alt-p:preview(cat {3})' \
        --preview='head -40 {3}' \
        --preview-window='right:50%:wrap:hidden' \
    2>/dev/null || true)

[[ -z "$selected" ]] && exit 0

# Extract name (field 2) — the invocation string
name=$(printf '%s' "$selected" | awk '{print $2}')
type=$(printf '%s' "$selected" | awk '{print $1}')

# Build invocation:
# - slash commands (/cmd type): paste the slash command literally
# - skills: paste /skill-name  (Claude Code skill invocation)
# - commands: paste the command name
case "$type" in
    /cmd)    invocation="$name" ;;
    skill)   invocation="/$name" ;;
    command) invocation="/$name" ;;
    prompt)  invocation=$(cat "$(printf '%s' "$selected" | awk '{print $3}')") ;;
esac

# Paste into the parent pane (the pane that launched this popup)
# TMUX_PANE is the popup's own pane; we want the pane that triggered display-popup
# Use tmux send-keys to active pane of current window
tmux send-keys "$invocation"
```

- [ ] Create `tmux/scripts/skill-picker.sh` with the above content (chmod +x)
- [ ] Add to `tmux.conf`:
  ```tmux
  bind-key P display-popup -E -w 75% -h 70% -d "#{pane_current_path}" "~/.dotfiles/tmux/scripts/skill-picker.sh"
  ```

---

## Step 5 — Cross-Repo Launcher (Ctrl+A G)
**Files:** `tmux/scripts/repo-launcher.sh` (new), `tmux/tmux.conf`
**Accepts:** `Ctrl+A G` opens an fzf picker with git repos from zoxide history; Enter opens Claude in a new tmux window at that repo; Alt-O opens Cursor.

### Script: `tmux/scripts/repo-launcher.sh`

```bash
#!/usr/bin/env bash
# repo-launcher.sh — cross-repo launcher via zoxide

set -euo pipefail

# Get all directories from zoxide, filter to those with a .git directory
repos=$(zoxide query -l 2>/dev/null \
    | while IFS= read -r dir; do
        [[ -d "$dir/.git" ]] && echo "$dir"
    done \
    | head -100)

if [[ -z "$repos" ]]; then
    echo "No git repos found in zoxide history."
    read -r; exit 0
fi

# Add current repo's worktrees
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    GIT_COMMON_DIR=$(git rev-parse --git-common-dir 2>/dev/null)
    REPO_ROOT=$(cd "$GIT_COMMON_DIR/.." && pwd)
    if [[ -d "$REPO_ROOT/.trees" ]]; then
        while IFS= read -r wt; do
            repos="${repos}"$'\n'"${REPO_ROOT}/.trees/${wt}"
        done < <(ls -1 "$REPO_ROOT/.trees" 2>/dev/null)
    fi
fi

repos=$(echo "$repos" | sort -u)

selected=$(printf '%s\n' "$repos" \
    | fzf \
        --prompt="  Open repo: " \
        --header="Enter: Claude · Alt-O: Cursor · Alt-W: Windsurf · Esc: close" \
        --border \
        --height=70% \
        --preview='git -C {} log --oneline -8 2>/dev/null || ls {}' \
        --preview-window='right:45%:wrap' \
        --bind="alt-o:execute($HOME/.dotfiles/tmux/scripts/open-cursor.sh {})+abort" \
        --bind="alt-w:execute($HOME/.dotfiles/tmux/scripts/open-windsurf.sh {})+abort" \
    2>/dev/null || true)

[[ -z "$selected" ]] && exit 0

name=$(basename "$selected")

tmux new-window -c "$selected" -n "claude:${name:0:12}" bash -l -c \
    "cd '$selected' && echo '📂 $selected' && echo '🌿 Branch: \$(git branch --show-current 2>/dev/null)' && echo '' && echo 'Starting Claude...' && unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT && \$HOME/.local/bin/claude; \$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh session-stop"
```

- [ ] Create `tmux/scripts/repo-launcher.sh` (chmod +x)
- [ ] Add to `tmux.conf`:
  ```tmux
  bind-key G display-popup -E -w 70% -h 65% -d "#{pane_current_path}" "~/.dotfiles/tmux/scripts/repo-launcher.sh"
  ```

---

## Step 6 — ai/prompts/ Library
**Files:** `ai/prompts/` (new directory + seed files)
**Accepts:** `ai/prompts/` exists with at least 3 useful prompt templates; they appear in skill-picker.sh output.

- [ ] Create `ai/prompts/` directory
- [ ] Add seed files (examples):
  - `ai/prompts/debug-trace.md` — "Walk me through what's happening in this code step by step. Show me the data flow and any potential failure points."
  - `ai/prompts/pr-review.md` — Standard PR review checklist prompt
  - `ai/prompts/explain-codebase.md` — "Explain the architecture of this project. What are the key components, how do they interact, and where is the main business logic?"

---

## Verification

1. **Activity monitoring:** Open Claude in one window, switch to another, run a command — the first window gets amber highlight. Claude finishes → 2-second "✓ Claude: done" toast appears.
2. **Elapsed timer:** While Claude is working, check `catppuccin-claude.sh` output — should show "⚙ projectname 45s". Status bar refreshes within 15 seconds.
3. **Window coloring:** Active Claude window shows amber ⚙ in the catppuccin window tab; idle Claude shows · in default color.
4. **Skill picker:** `Ctrl+A P` → fzf popup lists all skills, commands, slash commands. Select `/stack-create` → Enter → current pane receives `/stack-create` typed.
5. **Repo launcher:** `Ctrl+A G` → fzf popup shows git repos from zoxide. Select a repo → new window opens with Claude.
6. **Prompts:** Skill picker shows `prompt` type entries from `ai/prompts/`.

---

## Critical Files

| File | Role |
|---|---|
| `tmux/tmux.conf` | Keybindings, catppuccin format strings, monitor-activity |
| `tmux/scripts/claude-tmux-bridge.sh` | Add elapsed timer vars, finish notification |
| `tmux/scripts/catppuccin-claude.sh` | Add elapsed time display in status bar |
| `tmux/scripts/claude-session-picker.sh` | Add elapsed column |
| `tmux/scripts/skill-picker.sh` | NEW — skill/command/prompt fzf picker |
| `tmux/scripts/repo-launcher.sh` | NEW — cross-repo launcher |
| `ai/prompts/*.md` | NEW — saved prompt templates |

## Ordering Rationale

Steps 1-3 are **low-risk in-place edits** to existing files (bridge, tmux.conf, status module). Steps 4-6 are **net-new additions** (scripts, directory). No step depends on a previous step completing, so they can be implemented in any order, but 1→2→3 builds up the status bar coherently before adding new pickers.
