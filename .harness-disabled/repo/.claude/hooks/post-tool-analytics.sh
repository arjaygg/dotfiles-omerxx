#!/usr/bin/env bash
# Consolidated PostToolUse analytics (v2)
# Replaces: post-tool-handler.sh, bash-output-guard.sh, read-tracker.sh,
#           post-task-fence.sh, advisor-escalate.sh
#           (advisor-escalate folded 2026-07-08, H2)
# Matcher: .*
#
# Design: single process, jq for JSON parse, stdout only, exit 0 always
#         (PostToolUse is not on the critical path — tool already executed).
#         All metric logging happens here (batched, not per-hook).

set -euo pipefail
trap 'echo "HOOK CRASH (post-tool-analytics.sh line $LINENO): $BASH_COMMAND"; exit 0' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_START_NS=$(date +%s%N 2>/dev/null || echo 0)

INPUT=$(cat)

# --- Single JSON parse via jq ---
eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "FILE_PATH=\(.tool_input.file_path // .tool_input.path // "")",
  @sh "CMD=\(.tool_input.command // "")",
  @sh "SESSION_ID=\(.session_id // "default")",
  @sh "TASK_STATUS=\(.tool_input.status // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

# Prefer explicit session_id from tool payload; fall back to env var for compatibility.
EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"

# Extract output text and line count for Bash/Agent results only. Initialize
# unconditionally because Section 2 reads both values for every tool call.
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
# SECTION 0: advisor-escalate backstop (folded from advisor-escalate.sh/.py, H2, 2026-07-08)
#
# Placement note: this runs FIRST, before any section that might exit early
# (Section 2's compaction path does `exit 0` on >THRESHOLD-line output). Per
# the ordering lesson learned consolidating pre-tool-gate-v2.sh: a freshly
# folded independent check that must always run cannot be placed after a
# section that can terminate the process first. Computing ADVISOR_JSON here,
# before Section 2, guarantees it always runs regardless of what any later
# section decides.
#
# advisor-escalate.py drains stdin itself (sys.stdin.read()) and needs the
# raw, un-flattened JSON (nested tool_output/tool_input fields this script's
# own jq preamble does not extract into shell vars). $INPUT was captured once
# above and is unmutated, so it is safe to re-feed here even though this
# script's own `cat` already drained the hook's actual stdin.
#
# Output contract (unchanged from standalone advisor-escalate.py): always
# valid JSON, either `{}` (nothing to report) or
# `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"..."}}`.
# Never writes to stderr, never exits non-zero.
# ============================================================
ADVISOR_JSON='{}'
if [[ -f "${SCRIPT_DIR}/advisor-escalate.py" ]]; then
    ADVISOR_JSON=$(printf '%s' "$INPUT" | python3 "${SCRIPT_DIR}/advisor-escalate.py" 2>/dev/null || echo '{}')
    # Defensive: fall back to '{}' if the script produced non-JSON/empty output
    echo "$ADVISOR_JSON" | jq -e . >/dev/null 2>&1 || ADVISOR_JSON='{}'
fi

# ============================================================
# SECTION 1: Read tracking (for read-before-overwrite in PreToolUse §3a)
# ============================================================
# Session-scoped (the gate's comment always claimed "this session"; the store never was),
# realpath-canonicalized so symlink aliases of one file share an entry, and exact-line
# matched so a path that is a substring of an existing entry is still appended.
READ_LOG="/tmp/.claude-read-log-$(id -u)-${EFFECTIVE_SESSION_ID}"

_log_read() {
    local canon
    [[ -n "$1" ]] || return 0
    # Only regular files clear the overwrite gate; a directory read says nothing
    # about the files inside it.
    [[ -f "$1" ]] || return 0
    canon=$(realpath -q "$1" 2>/dev/null || echo "$1")
    grep -qxF "$canon" "$READ_LOG" 2>/dev/null || echo "$canon" >> "$READ_LOG"
}

if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
    _log_read "$FILE_PATH"
fi

# Direct LeanCtx/native-wrapper reads must satisfy the same safety gate.
if [[ -n "$FILE_PATH" ]] && \
   [[ "$TOOL_NAME" == "ReadFile" || "$TOOL_NAME" == "ctx_read" || \
      "$TOOL_NAME" == "mcp__lean-ctx__ctx_read" || "$TOOL_NAME" == "mcp__lean_ctx__ctx_read" ]]; then
    _log_read "$FILE_PATH"
fi

# ============================================================
# SECTION 1b: Auto-memory drift reminder (global)
# Fires when any memory/*.md is written — reminds to update MEMORY.md index.
# Lives here (global) because ~/.claude/projects/.../memory/ is cross-project.
# ============================================================
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    if [[ "$FILE_PATH" == */memory/*.md ]] && [[ "$FILE_PATH" != */MEMORY.md ]]; then
        echo "⚠️  MEMORY FILE WRITTEN: Update MEMORY.md index with a one-line entry." >&2
        echo "   Format: - [Name]($(basename "$FILE_PATH")) — one-line description (≤150 chars)" >&2
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
        # Merge with ADVISOR_JSON (Section 0) — a PostToolUse hook can only emit
        # one JSON object on stdout, so both must be combined here rather than
        # printed separately. When ADVISOR_JSON is '{}' this is a no-op merge.
        echo "$COMPACTED" | jq -Rs --argjson adv "$ADVISOR_JSON" '{"updatedToolOutput": .} + $adv'
        exit 0
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
                echo "OUTPUT WARNING: Bash produced $LINE_COUNT lines — significant context consumption." >&2
                echo "  For data-heavy commands, prefer LeanCtx (compresses output):" >&2
                echo "    mcp__lean-ctx__ctx_shell — run a command with compressed output" >&2
                echo "    Run independent direct MCP calls in parallel when the client supports it" >&2
            elif [[ "$LINE_COUNT" -gt 50 ]]; then
                echo "OUTPUT HINT: Bash produced $LINE_COUNT lines. For commands with large output, consider mcp__lean-ctx__ctx_shell to keep raw data out of context." >&2
            fi
            ;;
    esac

    # LeanCtx diagnostic hint: recover exact test failures
    if [[ "${EXIT_CODE:-0}" != "0" ]]; then
        if echo "$CMD" | grep -qiE '(go test|pytest|npm test|npx jest|dotnet test|cargo test)'; then
            if echo "$OUTPUT" | grep -q '\[lean-ctx:' || [[ "$LINE_COUNT" -lt 10 ]]; then
                echo "LEAN_CTX_DIAGNOSTIC_HINT: Test failed with compressed output. Re-run via LeanCtx.ctxShell with raw=true, or: lean-ctx raw \"$CMD\"" >&2
            fi
        fi
    fi
fi

# ============================================================
# SECTION 4: Direct Serena/LeanCtx session-init flag setters
# ============================================================
if [[ "$TOOL_NAME" == mcp__serena__* || "$TOOL_NAME" == mcp__serena-fallback__* || \
      "$TOOL_NAME" == "Serena.initialInstructions" ]]; then
    touch "/tmp/.claude-serena-init-$(id -u)-${EFFECTIVE_SESSION_ID}" 2>/dev/null || true
fi

if [[ "$TOOL_NAME" == "ctx_call" || "$TOOL_NAME" == "mcp__lean-ctx__ctx_call" || \
      "$TOOL_NAME" == "mcp__lean_ctx__ctx_call" ]]; then
    _CALL_NAME=$(echo "$INPUT" | jq -r '.tool_input.name // .tool_input.arguments.name // ""' 2>/dev/null || echo "")
    if [[ "$_CALL_NAME" == "ctx_intent" ]]; then
        touch "/tmp/.claude-ctx-loaded-$(id -u)-${EFFECTIVE_SESSION_ID}" 2>/dev/null || true
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
if [[ -f "${SCRIPT_DIR}/hook-metrics.sh" ]]; then
    source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
    _END_NS=$(date +%s%N 2>/dev/null || echo 0)
    _DURATION_MS=$(( (_END_NS - _START_NS) / 1000000 ))
    hook_metric "post-tool-analytics" "$TOOL_NAME" 0 "$EFFECTIVE_SESSION_ID" "$_DURATION_MS" 2>/dev/null || true
fi

# ============================================================
# SECTION 7b: Emit advisor-escalate JSON (folded, H2)
# Only reached if Section 2's compaction path did not already exit with a
# merged JSON blob above. If ADVISOR_JSON is the trivial '{}' (the common
# case — no recurring-failure signature detected), stdout stays empty and
# behavior is byte-for-byte identical to before this fold-in.
# ============================================================
if [[ "$ADVISOR_JSON" != "{}" ]]; then
    echo "$ADVISOR_JSON"
fi

# ============================================================
# SECTION 8: lean-ctx hook observe (backgrounded, folded from separate
# PostToolUse .* matcher entry, R6 — docs/plans/2026-07-08-reduce-context-redundancy.md)
# ============================================================
(printf '%s' "$INPUT" | bash -lc 'lean-ctx hook observe' &>/dev/null) &

exit 0
