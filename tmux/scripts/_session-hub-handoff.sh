#!/usr/bin/env bash
# _session-hub-handoff.sh — New session with context handoff carry
#
# Creates a new worktree and seeds it with context from a prior session.
# The new Claude session's session-init hook will read the written handoff.
#
# Args:
#   $1 = source_cwd       (project directory of prior session)
#   $2 = source_session_id (session ID of prior session)
#
# Flow:
#   1. Read prior session's context (session-handoff.md / active-context.md)
#   2. Pre-populate task prompt with the prior Focus line
#   3. Fire LLM for a continuation name suggestion
#   4. User confirms/overrides name
#   5. Create worktree
#   6. Write handoff file to new worktree's plans/
#   7. Open Claude in new worktree

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_session-hub-lib.sh
source "$SCRIPT_DIR/_session-hub-lib.sh"

SOURCE_CWD="${1:-}"
SOURCE_SESSION_ID="${2:-}"

if [[ -z "$SOURCE_CWD" || ! -d "$SOURCE_CWD" ]]; then
    echo "Error: source_cwd '$SOURCE_CWD' not found" >&2
    exit 1
fi

# Resolve to MAIN repo root — handles source sessions inside .trees/ worktrees.
# `git rev-parse --absolute-git-dir` exposes the /worktrees/ path segment.
resolve_repo_root() {
    local cwd="$1"
    local git_abs_dir
    git_abs_dir=$(git -C "$cwd" rev-parse --absolute-git-dir 2>/dev/null || echo "")
    if [[ -z "$git_abs_dir" ]]; then
        echo "$cwd"; return
    fi
    if [[ "$git_abs_dir" == *"/.git/worktrees/"* ]]; then
        echo "${git_abs_dir%%/.git/worktrees/*}"
    else
        git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || echo "$cwd"
    fi
}

REPO_ROOT=$(resolve_repo_root "$SOURCE_CWD")
SOURCE_PROJECT=$(basename "$SOURCE_CWD")
SOURCE_BRANCH=$(git -C "$SOURCE_CWD" branch --show-current 2>/dev/null || echo "unknown")

# ── Step 1: Read prior session context ────────────────────────────────────────

prior_context=""
prior_focus=""
pending_tasks=""

if [[ -f "$SOURCE_CWD/plans/active-context.md" ]]; then
    prior_context=$(cat "$SOURCE_CWD/plans/active-context.md")
    # Extract focus from "focus: ..." line (active-context format) or **Focus:**
    prior_focus=$(grep -m1 '^focus:' "$SOURCE_CWD/plans/active-context.md" \
        | sed 's/^focus:[[:space:]]*//' || true)
    [[ -z "$prior_focus" ]] && prior_focus=$(grep -m1 '^\*\*Focus:\*\*' "$SOURCE_CWD/plans/active-context.md" \
        | sed 's/\*\*Focus:\*\*[[:space:]]*//' || true)
fi

if [[ -z "$prior_focus" && -f "$SOURCE_CWD/plans/session-handoff.md" ]]; then
    [[ -z "$prior_context" ]] && prior_context=$(cat "$SOURCE_CWD/plans/session-handoff.md")
    prior_focus=$(grep -m1 '^\*\*Focus:\*\*\|^focus:' "$SOURCE_CWD/plans/session-handoff.md" \
        | sed 's/^\*\*Focus:\*\*[[:space:]]*//; s/^focus:[[:space:]]*//' || true)
fi

# Extract pending tasks from progress.md for smarter LLM name suggestion
if [[ -f "$SOURCE_CWD/plans/progress.md" ]]; then
    pending_tasks=$(grep '^\- \[ \]' "$SOURCE_CWD/plans/progress.md" 2>/dev/null \
        | sed 's/^- \[ \] //' | head -5 | tr '\n' '; ' | sed 's/; $//' || true)
fi

# Truncate prior_focus for display
prior_focus_display="${prior_focus:0:60}"

# ── Step 2: Prompt for new task (pre-filled with prior focus) ─────────────────

task_desc=$(printf '%s\n' "$prior_focus_display" \
    | fzf \
        --print-query \
        --prompt="  New task (continuing from $SOURCE_PROJECT): " \
        --border \
        --border-label=" Handoff — Carry Context " \
        --height=35% \
        --header="Prior context loaded from $SOURCE_PROJECT [$SOURCE_BRANCH] | Edit or clear the task description" \
    2>/dev/null | head -1 || true)

[[ -z "$task_desc" ]] && task_desc="${prior_focus_display:-continue-work}"

# ── Step 3: Slug fallback + background LLM ───────────────────────────────────

slug_fallback=$(printf '%s' "$task_desc" \
    | iconv -t ascii//TRANSLIT 2>/dev/null \
    | tr '[:upper:]' '[:lower:]' \
    | tr -cs 'a-z0-9' '-' \
    | sed 's/-\+/-/g; s/^-//; s/-$//' \
    | cut -c1-35)

[[ -z "$slug_fallback" ]] && slug_fallback="continue-$(date +%m%d)"

# Fire LLM in background for continuation name — include pending tasks for richer context
tmpfile=$(mktemp /tmp/session-hub-handoff-name.XXXXXX)
pending_part=""
[[ -n "$pending_tasks" ]] && pending_part=" Pending tasks: $pending_tasks."
llm_prompt="Prior focus: ${prior_focus_display}.${pending_part} New task: ${task_desc}. Suggest a short 2-4 word kebab-case git branch name (no type prefix). Reply with ONLY the name."
timeout 20 claude --print --bare \
    --model claude-haiku-4-5 \
    "$llm_prompt" \
    > "$tmpfile" 2>/dev/null &
llm_pid=$!

sleep 1
if ! kill -0 "$llm_pid" 2>/dev/null; then
    llm_name=$(cat "$tmpfile" \
        | tr -d '\n' \
        | tr '[:upper:]' '[:lower:]' \
        | tr -cs 'a-z0-9' '-' \
        | sed 's/-\+/-/g; s/^-//; s/-$//' \
        | cut -c1-40)
    initial_name="${llm_name:-$slug_fallback}"
else
    initial_name="$slug_fallback"
fi
rm -f "$tmpfile"

# ── Step 4: Confirm or override name ─────────────────────────────────────────

final_name=$(printf '%s\n' "$initial_name" \
    | fzf \
        --print-query \
        --prompt="  Worktree name: " \
        --border \
        --border-label=" Name Worktree " \
        --height=30% \
        --header="Enter to accept · Type to override" \
    2>/dev/null | head -1 || true)

[[ -z "$final_name" ]] && final_name="$initial_name"

final_name=$(printf '%s' "$final_name" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -cs 'a-z0-9' '-' \
    | sed 's/-\+/-/g; s/^-//; s/-$//' \
    | cut -c1-40)

[[ -z "$final_name" ]] && final_name="handoff-$(date +%m%d%H%M)"

# ── Step 5: Create worktree ───────────────────────────────────────────────────

worktree_path="$REPO_ROOT/.trees/$final_name"

if [[ -d "$worktree_path" ]]; then
    :
elif git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$final_name" 2>/dev/null; then
    git -C "$REPO_ROOT" worktree add "$worktree_path" "$final_name" 2>/dev/null || true
else
    git -C "$REPO_ROOT" worktree add -b "$final_name" "$worktree_path" 2>/dev/null \
        || { echo "Failed to create worktree at $worktree_path" >&2; exit 1; }
fi

# ── Step 6: Write handoff to new worktree ────────────────────────────────────

mkdir -p "$worktree_path/plans"

handoff_date=$(date '+%Y-%m-%d %H:%M')

cat > "$worktree_path/plans/session-handoff.md" << HANDOFF_EOF
# Session Handoff — ${handoff_date}
status: pending

**Branch:** ${final_name}
**Continuing from:** ${SOURCE_PROJECT} [${SOURCE_BRANCH}]
**Previous session:** ${SOURCE_SESSION_ID}
**Task:** ${task_desc}

---

## Context from Prior Session

${prior_context}

---
*Handoff created by session-hub.sh*
HANDOFF_EOF

# ── Step 7: Open Claude in new worktree ──────────────────────────────────────

window_name="claude:${final_name:0:20}"
task_list_id=$(get_task_list_id "$worktree_path")
safe_path=$(printf '%s' "$worktree_path" | sed "s/'/'\\\\''/g")

tmux new-window \
    -c "$worktree_path" \
    -n "${window_name:0:30}" \
    bash -l -c "cd '$safe_path' && CLAUDE_CODE_TASK_LIST_ID='$task_list_id' claude --dangerously-skip-permissions; '$SCRIPT_DIR/claude-tmux-bridge.sh' session-stop"
