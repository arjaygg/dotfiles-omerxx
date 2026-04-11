#!/usr/bin/env bash
# session-hub.sh — Unified Claude Code Session Launcher
#
# Replaces repo-launcher.sh as the primary session manager (Ctrl+A G).
# Shows ALL Claude Code sessions: live tmux panes + recent + archived.
# No zoxide dependency — reads directly from ~/.claude/projects/.
#
# Keybinding: Ctrl+A G (tmux.conf)
# Flags: --with-archived  (show archived >7d sessions, used by Alt-A reload)
#
# Actions:
#   Enter    Resume session (or switch to live pane)
#   Alt-N    New session with worktree (LLM-suggested name)
#   Alt-H    New session with handoff carry from selected
#   Ctrl-D   Mark selected session as done
#   Alt-A    Toggle archived sessions
#   Esc      Exit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECTS_DIR="${HOME}/.claude/projects"
DAYS_RECENT=30
SHOW_ARCHIVED="${1:-}"  # "--with-archived" flag

# ── Helpers ───────────────────────────────────────────────────────────────────

# Human-readable age from epoch milliseconds
age_label() {
    local mtime_ms="$1"
    local now_ms
    now_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    local diff_s=$(( (now_ms - mtime_ms) / 1000 ))
    if   (( diff_s < 3600  )); then echo "${diff_s}s"
    elif (( diff_s < 86400 )); then echo "$((diff_s/3600))h"
    else                            echo "$((diff_s/86400))d"
    fi
}

# ── Phase 1: Collect live tmux sessions ───────────────────────────────────────

collect_live_sessions() {
    # Emit: TYPE\tDISPLAY\tID_OR_TARGET\tCWD
    # TYPE = "live"
    tmux list-panes -a \
        -F '#{pane_id}|#{@claude_status}|#{@claude_project}|#{@claude_branch}|#{@claude_activity_start}|#{pane_current_path}' \
        2>/dev/null \
    | awk -F'|' '$2 != ""' \
    | while IFS='|' read -r pane_id status project branch start_time cwd; do
        local icon="·"
        [[ "$status" == "working" ]] && icon="⚙"
        local age_str=""
        if [[ -n "$start_time" && "$start_time" =~ ^[0-9]+$ ]]; then
            local elapsed=$(( $(date +%s) - start_time ))
            if   (( elapsed < 3600  )); then age_str="${elapsed}s"
            elif (( elapsed < 86400 )); then age_str="$(( elapsed/3600 ))h"
            else                             age_str="$(( elapsed/86400 ))d"
            fi
        fi
        local display
        display=$(printf "%s  %-22s [%-14s] %-8s %s" \
            "$icon" "${project:0:22}" "${branch:0:14}" "$status" "$age_str")
        printf "live\t%s\t%s\t%s\n" "$display" "$pane_id" "${cwd:-$HOME}"
    done
}

# ── Phase 2: Collect indexed + JSONL-only sessions ────────────────────────────

collect_persisted_sessions() {
    local show_archived="$1"
    python3 - "$PROJECTS_DIR" "$DAYS_RECENT" "$show_archived" <<'PYEOF'
import json
import os
import glob
import sys
import re
import time

projects_dir = sys.argv[1]
days_recent  = int(sys.argv[2])
show_archived = sys.argv[3] == "--with-archived"

now_s   = time.time()
now_ms  = now_s * 1000
cutoff_recent_s   = now_s - (days_recent * 86400)

def age_label(mtime_ms):
    diff_s = (now_ms - mtime_ms) / 1000
    if diff_s < 3600:
        return f"{int(diff_s)}s"
    elif diff_s < 86400:
        return f"{int(diff_s/3600)}h"
    else:
        return f"{int(diff_s/86400)}d"

def read_handoff_status(project_path):
    """Read status: line from plans/session-handoff.md"""
    handoff = os.path.join(project_path, "plans", "session-handoff.md")
    if not os.path.exists(handoff):
        return "none"
    try:
        with open(handoff, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.match(r"^status:\s*(\S+)", line.strip())
                if m:
                    return m.group(1)
    except Exception:
        pass
    return "none"

def status_badge(status):
    badges = {
        "pending":  "● PENDING",
        "deferred": "○ defer  ",
        "complete": "✓ done   ",
        "none":     "·        ",
    }
    return badges.get(status, "·        ")

def get_cwd_from_jsonl(jsonl_path):
    """Extract cwd from first 20 lines of a JSONL file.
    Returns path string even if directory no longer exists (deleted worktrees)."""
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i > 20:
                    break
                try:
                    obj = json.loads(line)
                    cwd = obj.get("cwd") or obj.get("projectPath")
                    if cwd and isinstance(cwd, str) and len(cwd) > 1:
                        return cwd
                except Exception:
                    pass
    except Exception:
        pass
    return None

# Track which cwds already came from an indexed project (to deduplicate)
indexed_cwds = set()
results = []

# ── Pass 1: Indexed projects (sessions-index.json) ────────────────────────────
for idx_path in glob.glob(os.path.join(projects_dir, "*", "sessions-index.json")):
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = data.get("entries", [])
        if not entries:
            continue

        # Pick the most recent non-sidechain session
        main_entries = [e for e in entries if not e.get("isSidechain", False)]
        if not main_entries:
            main_entries = entries

        most_recent = max(main_entries, key=lambda x: x.get("fileMtime", 0))
        cwd = most_recent.get("projectPath") or data.get("originalPath", "")
        if not cwd:
            continue

        indexed_cwds.add(cwd)

        mtime_ms   = most_recent.get("fileMtime", 0)
        age_days_f = (now_ms - mtime_ms) / 1000 / 86400
        is_recent  = age_days_f <= days_recent

        if not is_recent and not show_archived:
            continue

        session_id = most_recent.get("sessionId", "")
        summary    = (most_recent.get("summary") or most_recent.get("firstPrompt") or "")[:70]
        branch     = most_recent.get("gitBranch", "")
        age        = age_label(mtime_ms)
        status     = read_handoff_status(cwd)
        badge      = status_badge(status)
        project    = os.path.basename(cwd) if cwd else "unknown"

        section = "recent" if is_recent else "archived"
        results.append((mtime_ms, section, cwd, session_id, summary, branch, age, badge, project))

    except Exception:
        pass

# ── Pass 2: JSONL-only projects ───────────────────────────────────────────────
for proj_dir in glob.glob(os.path.join(projects_dir, "*")):
    if not os.path.isdir(proj_dir):
        continue
    if os.path.exists(os.path.join(proj_dir, "sessions-index.json")):
        continue  # Already handled in pass 1

    jsonl_files = glob.glob(os.path.join(proj_dir, "*.jsonl"))
    if not jsonl_files:
        continue

    # Find most recent JSONL
    try:
        most_recent_jsonl = max(jsonl_files, key=lambda p: os.path.getmtime(p))
        mtime_s   = os.path.getmtime(most_recent_jsonl)
        mtime_ms  = mtime_s * 1000
        age_days_f = (now_s - mtime_s) / 86400
        is_recent  = age_days_f <= days_recent

        if not is_recent and not show_archived:
            continue

        cwd = get_cwd_from_jsonl(most_recent_jsonl)
        if not cwd or cwd in indexed_cwds:
            continue

        session_id = os.path.splitext(os.path.basename(most_recent_jsonl))[0]
        age        = age_label(mtime_ms)
        status     = read_handoff_status(cwd)
        badge      = status_badge(status)
        project    = os.path.basename(cwd)
        branch     = ""  # not available without index

        # Try to get first prompt from JSONL
        summary = ""
        try:
            with open(most_recent_jsonl, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i > 30:
                        break
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "user":
                            msg = obj.get("message", {})
                            if isinstance(msg, dict):
                                for block in msg.get("content", []):
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        summary = block.get("text", "")[:70]
                                        break
                            if summary:
                                break
                    except Exception:
                        pass
        except Exception:
            pass

        section = "recent" if is_recent else "archived"
        results.append((mtime_ms, section, cwd, session_id, summary, branch, age, badge, project))

    except Exception:
        pass

# ── Emit sorted by recency ────────────────────────────────────────────────────
results.sort(key=lambda x: x[0], reverse=True)

for (mtime_ms, section, cwd, session_id, summary, branch, age, badge, project) in results:
    # Display line (left pane of fzf)
    proj_trunc   = project[:20]
    branch_trunc = branch[:14] if branch else ""
    summary_trunc = summary[:65] if summary else "(no summary)"
    display = f"{badge}  {proj_trunc:<20} [{branch_trunc:<14}]  {age:<5}  {summary_trunc}"
    # Tab-delimited: TYPE \t DISPLAY \t SESSION_ID \t CWD
    print(f"{section}\t{display}\t{session_id}\t{cwd}")

PYEOF
}

# ── Phase 3: Build full display list ──────────────────────────────────────────

build_display_list() {
    local show_archived="${1:-}"
    local live_lines persisted_lines
    local live_cwds=""

    live_lines=$(collect_live_sessions 2>/dev/null || true)

    # Extract live cwds for dedup reference
    if [[ -n "$live_lines" ]]; then
        live_cwds=$(printf '%s\n' "$live_lines" | awk -F'\t' '{print $4}')
    fi

    persisted_lines=$(collect_persisted_sessions "$show_archived" 2>/dev/null || true)

    # Section: ACTIVE
    if [[ -n "$live_lines" ]]; then
        printf "header\t\033[1;36m── ACTIVE (live tmux panes) ─────────────────────────────\033[0m\t\t\n"
        printf '%s\n' "$live_lines"
    else
        printf "header\t\033[1;36m── ACTIVE ── (no live Claude panes) ────────────────────\033[0m\t\t\n"
    fi

    # Section: RECENT — dedup against live cwds via temp file (avoids awk -v multiline bug)
    local recent_lines live_cwd_file
    live_cwd_file=$(mktemp /tmp/session-hub-live-cwds.XXXXXX)
    printf '%s\n' "$live_cwds" > "$live_cwd_file"

    recent_lines=$(printf '%s\n' "$persisted_lines" \
        | awk -F'\t' '$1=="recent"{print}' \
        | awk -F'\t' 'NR==FNR{live[$1]=1; next} !live[$4]' "$live_cwd_file" - \
        2>/dev/null || true)
    rm -f "$live_cwd_file"

    local recent_count=0
    [[ -n "$recent_lines" ]] && recent_count=$(printf '%s\n' "$recent_lines" | awk 'END{print NR}')

    printf "header\t\033[1;33m── RECENT (<${DAYS_RECENT}d, %s sessions) ────────────────────────\033[0m\t\t\n" "$recent_count"
    if [[ -n "$recent_lines" ]]; then
        printf '%s\n' "$recent_lines"
    else
        printf "header\t  (no recent sessions)\t\t\n"
    fi

    # Section: ARCHIVED (only if requested)
    if [[ "$show_archived" == "--with-archived" ]]; then
        local archived_lines
        archived_lines=$(printf '%s\n' "$persisted_lines" | grep $'^archived\t' || true)
        local archived_count=0
        [[ -n "$archived_lines" ]] && archived_count=$(printf '%s\n' "$archived_lines" | grep -c . || true)
        printf "header\t\033[0;37m── ARCHIVED (>%dd, %s sessions) ──────────────────────────\033[0m\t\t\n" "$DAYS_RECENT" "$archived_count"
        if [[ -n "$archived_lines" ]]; then
            printf '%s\n' "$archived_lines"
        else
            printf "header\t  (no archived sessions)\t\t\n"
        fi
    else
        printf "header\t\033[0;37m── ARCHIVED (>%dd) ── press \033[1mAlt-A\033[0;37m to expand ────────────\033[0m\t\t\n" "$DAYS_RECENT"
    fi
}

# ── Phase 4: Open / resume a session ──────────────────────────────────────────

open_session() {
    local entry_type="$1"
    local session_id="$2"
    local cwd="$3"

    if [[ "$entry_type" == "live" ]]; then
        # session_id is actually the tmux pane_id for live entries
        tmux switch-client -t "$session_id" 2>/dev/null \
            || tmux select-pane -t "$session_id" 2>/dev/null \
            || true
        return 0
    fi

    if [[ -z "$cwd" || ! -d "$cwd" ]]; then
        echo "Session directory not found: $cwd" >&2
        return 1
    fi

    local name
    name=$(basename "$cwd")
    # Get branch for window name
    local branch=""
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null || true)
    local window_name="claude:${name:0:12}"
    [[ -n "$branch" ]] && window_name="claude:${name:0:10}[${branch:0:8}]"

    tmux new-window \
        -c "$cwd" \
        -n "${window_name:0:30}" \
        bash -l -c "cd '$(printf '%s' "$cwd" | sed "s/'/'\\\\''/g")' && claude --resume '$session_id'; '$SCRIPT_DIR/claude-tmux-bridge.sh' session-stop"
}

# ── Phase 5: Preview content ──────────────────────────────────────────────────

show_preview() {
    local entry_type="$1"
    local session_id="$2"
    local cwd="$3"

    if [[ "$entry_type" == "live" ]]; then
        # session_id is pane_id for live entries
        printf "\033[1;34m── Live pane: %s ──\033[0m\n\n" "$session_id"
        tmux capture-pane -p -t "$session_id" -e 2>/dev/null | tail -25 || echo "(could not capture pane)"
        return
    fi

    printf "\033[1;34m── %s ──\033[0m\n\n" "$cwd"

    if [[ -f "$cwd/plans/active-context.md" ]]; then
        head -40 "$cwd/plans/active-context.md"
    elif [[ -f "$cwd/plans/session-handoff.md" ]]; then
        head -40 "$cwd/plans/session-handoff.md"
    else
        printf "(no context file found)\n\n"
        # Show git log as fallback
        git -C "$cwd" log --oneline -10 2>/dev/null || true
    fi
}

# ── Main fzf UI ────────────────────────────────────────────────────────────────

main() {
    # Handle --preview call (used by fzf --preview flag)
    if [[ "${1:-}" == "--preview" ]]; then
        shift
        show_preview "$@"
        return 0
    fi

    local show_archived="${SHOW_ARCHIVED:-}"
    local display_list
    display_list=$(build_display_list "$show_archived")

    # fzf with 3-section display, preview pane, action bindings
    local selected
    selected=$(printf '%s\n' "$display_list" \
        | fzf \
            --ansi \
            --no-sort \
            --prompt="  Sessions: " \
            --border \
            --border-label=" Claude Code Sessions " \
            --border-label-pos=2 \
            --header="Enter: Open  Alt-N: New  Alt-H: Handoff  Ctrl-D: Done  Alt-A: Archived  Esc: Exit" \
            --delimiter=$'\t' \
            --with-nth=2 \
            --preview="bash '$SCRIPT_DIR/session-hub.sh' --preview {1} {3} {4}" \
            --preview-window='right:50%:wrap' \
            --bind="alt-a:reload(bash '$SCRIPT_DIR/session-hub.sh' --list --with-archived)" \
            --bind="alt-n:execute(bash '$SCRIPT_DIR/_session-hub-new.sh' {4})+abort" \
            --bind="alt-h:execute(bash '$SCRIPT_DIR/_session-hub-handoff.sh' {4} {3})+abort" \
            --bind="ctrl-d:execute(bash '$SCRIPT_DIR/_session-hub-done.sh' {4})+reload(bash '$SCRIPT_DIR/session-hub.sh' --list $show_archived)" \
            --bind="enter:accept" \
            2>/dev/null || true)

    [[ -z "$selected" ]] && return 0

    # Skip if user pressed on a header line
    local entry_type
    entry_type=$(printf '%s' "$selected" | cut -f1)
    [[ "$entry_type" == "header" ]] && return 0

    local session_id cwd
    session_id=$(printf '%s' "$selected" | cut -f3)
    cwd=$(printf '%s' "$selected" | cut -f4)

    open_session "$entry_type" "$session_id" "$cwd"
}

# ── List mode (used by fzf --reload) ─────────────────────────────────────────
if [[ "${1:-}" == "--list" ]]; then
    shift
    build_display_list "${1:-}"
    exit 0
fi

main "$@"
