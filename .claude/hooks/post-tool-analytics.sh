#!/usr/bin/env bash
# Consolidated PostToolUse analytics (v2)
# Replaces: post-tool-handler.sh, bash-output-guard.sh, pctx-batch-tracker.sh,
#           read-tracker.sh, post-task-fence.sh
# Matcher: .*
#
# Design: single process, jq for JSON parse, stdout only, exit 0 always
#         (PostToolUse is not on the critical path — tool already executed).
#         All metric logging happens here (batched, not per-hook).

set -euo pipefail
trap 'echo "HOOK CRASH (post-tool-analytics.sh line $LINENO): $BASH_COMMAND"; exit 0' ERR

INPUT=$(cat)

# --- Single JSON parse via jq ---
eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "FILE_PATH=\(.tool_input.file_path // .tool_input.path // "")",
  @sh "CMD=\(.tool_input.command // "")",
  @sh "SESSION_ID=\(.session_id // "default")",
  @sh "TASK_STATUS=\(.tool_input.status // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

# Extract output text and line count for Bash/Agent (heavier parse, only when needed)
LINE_COUNT=0
OUTPUT=""
if [[ "$TOOL_NAME" == "Bash" || "$TOOL_NAME" == "Agent" ]]; then
    eval "$(echo "$INPUT" | jq -r '
      def text_content:
        .tool_response.content // .content //
        (if type == "object" then
          (.tool_response.content // .content // "") |
          if type == "array" then map(select(.type == "text") | .text) | join("") else . end
        else "" end);
      @sh "OUTPUT=\(text_content)",
      @sh "EXIT_CODE=\(.tool_response.exitCode // .tool_response.exit_code // "0")"
    ' 2>/dev/null)" 2>/dev/null || true
    if [[ -n "$OUTPUT" ]]; then
        LINE_COUNT=$(echo "$OUTPUT" | wc -l | tr -d ' ')
    fi
fi

# ============================================================
# SECTION 1: Read tracking (for edit-without-read in PreToolUse)
# ============================================================
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
    READ_LOG="/tmp/.claude-read-log-$(id -u)"
    if [[ ! -f "$READ_LOG" ]] || ! grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
        echo "$FILE_PATH" >> "$READ_LOG"
    fi
fi

# ============================================================
# SECTION 2: Bash/Agent output compaction (>300 lines)
# ============================================================
if [[ "$LINE_COUNT" -gt 0 ]]; then
    THRESHOLD=300
    [[ "$TOOL_NAME" == "Agent" ]] && THRESHOLD=200

    if [[ "$LINE_COUNT" -gt "$THRESHOLD" ]]; then
        HEAD=$(echo "$OUTPUT" | head -40)
        TAIL=$(echo "$OUTPUT" | tail -40)
        OMITTED=$(( LINE_COUNT - 80 ))
        COMPACTED=$(printf '%s\n\n... %d lines omitted (use grep/search to find specific content) ...\n\n%s' \
            "$HEAD" "$OMITTED" "$TAIL")
        echo "$COMPACTED" | jq -Rs '{"type": "text", "text": .}'
    fi
fi

# ============================================================
# SECTION 3: Bash output guard (advisory)
# ============================================================
if [[ "$TOOL_NAME" == "Bash" ]]; then
    # Skip known short-output commands
    case "$CMD" in
        git\ status*|git\ branch*|git\ diff\ --stat*|git\ log\ --oneline*|ls*|pwd*|which*|echo*) ;;
        *)
            if [[ "$LINE_COUNT" -gt 200 ]]; then
                echo "OUTPUT WARNING: Bash produced $LINE_COUNT lines — significant context consumption."
                echo "  For data-heavy commands, use context-mode MCP tools:"
                echo "    mcp__context-mode__ctx_batch_execute — runs commands + auto-indexes output"
                echo "    mcp__context-mode__ctx_execute — processes data in sandbox"
            elif [[ "$LINE_COUNT" -gt 50 ]]; then
                echo "OUTPUT HINT: Bash produced $LINE_COUNT lines. For commands with large output, consider context-mode MCP tools to keep raw data out of context."
            fi
            ;;
    esac

    # RTK diagnostic hint: detect compressed test failures
    if [[ "${EXIT_CODE:-0}" != "0" ]]; then
        if echo "$CMD" | grep -qiE '(go test|pytest|npm test|npx jest|dotnet test|cargo test)'; then
            if echo "$OUTPUT" | grep -q '\[lean-ctx:' || [[ "$LINE_COUNT" -lt 10 ]]; then
                echo "RTK_DIAGNOSTIC_HINT: Test failed but output was compressed by rtk. To see full error details, re-run with: rtk proxy $CMD"
            fi
        fi
    fi
fi

# ============================================================
# SECTION 4: pctx batch tracker
# ============================================================
if [[ "$TOOL_NAME" == mcp__serena__* || "$TOOL_NAME" == mcp__pctx__* ]]; then
    TRACKER="/tmp/.claude-serena-calls-$(id -u)-${SESSION_ID}"

    if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]]; then
        # Batched call — reset counter
        rm -f "$TRACKER" 2>/dev/null || true
    else
        # Track the call
        NOW=$(date '+%s')
        echo "$NOW $TOOL_NAME" >> "$TRACKER"

        # Prune entries older than 60 seconds
        if [[ -f "$TRACKER" ]]; then
            CUTOFF=$((NOW - 60))
            TEMP=$(mktemp)
            awk -v cutoff="$CUTOFF" '$1 >= cutoff' "$TRACKER" > "$TEMP" 2>/dev/null && mv "$TEMP" "$TRACKER" || rm -f "$TEMP"
        fi

        # Count and warn
        COUNT=0
        [[ -f "$TRACKER" ]] && COUNT=$(wc -l < "$TRACKER" | tr -d ' ')
        if [[ "$COUNT" -ge 2 ]]; then
            echo "BATCH HINT: You've made $COUNT sequential Serena/pctx MCP calls in the last 60s."
            echo "  Consider batching into one pctx execute_typescript call with Promise.all()."
            echo "  See: pctx-unified-rules.md section 2 'Batching & Code Mode'"
            rm -f "$TRACKER" 2>/dev/null || true
        fi
    fi
fi

# ============================================================
# SECTION 4b: Serena session-init flag setter
# Set the flag that pre-tool-gate-v2 Section 0 checks, so Grep is unblocked
# once the model has called mcp__pctx__list_functions or any Serena tool.
# ============================================================
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    if [[ "$TOOL_NAME" == "mcp__pctx__list_functions" ]] || [[ "$TOOL_NAME" == mcp__serena__* ]]; then
        _INIT_FLAG="/tmp/.claude-serena-init-$(id -u)-${CLAUDE_SESSION_ID}"
        touch "$_INIT_FLAG" 2>/dev/null || true
    fi
fi

# ============================================================
# SECTION 5: pctx batching reminder (once per session)
# ============================================================
if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]]; then
    REMINDER_FLAG="/tmp/.claude-pctx-reminder-$(id -u)"
    if [[ ! -f "$REMINDER_FLAG" ]]; then
        touch "$REMINDER_FLAG"
        echo "BATCH CHECK: Was this the only Serena/MCP operation needed this turn? If 2+ ops are coming, combine them into one execute_typescript call."
    fi
fi

# ============================================================
# SECTION 6: Post-task fence (commit reminder)
# ============================================================
if [[ "$TOOL_NAME" == "TaskUpdate" && "$TASK_STATUS" == "completed" ]]; then
    HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || echo "")
    if [[ "$HOOKS_PATH" == "$HOME/.dotfiles/git/hooks" ]]; then
        STAGED=$(git diff --cached --name-only 2>/dev/null || true)
        UNSTAGED=$(git diff --name-only 2>/dev/null || true)
        if [[ -n "$STAGED" || -n "$UNSTAGED" ]]; then
            echo "WARNING: Task marked complete with uncommitted changes."
            [[ -n "$STAGED" ]] && echo "  Staged: $(echo "$STAGED" | wc -l | tr -d ' ') file(s)"
            [[ -n "$UNSTAGED" ]] && echo "  Unstaged: $(echo "$UNSTAGED" | wc -l | tr -d ' ') file(s)"
            echo "  Commit before starting next task:"
            echo "  ~/.dotfiles/scripts/ai/commit.sh -m 'type(scope): subject' -m 'why'"
        fi
    fi
fi

# ============================================================
# SECTION 7: Metrics logging (single write, end of script)
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/hook-metrics.sh" ]]; then
    source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
    hook_metric "post-tool-analytics" "$TOOL_NAME" 0 2>/dev/null || true
fi

exit 0
