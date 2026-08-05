#!/usr/bin/env bash
# Multi-event hook — fires after Agent tool calls complete (PostToolUse), and on
# teammate/subagent lifecycle events (SubagentStop, TeammateIdle).
#
# Inspects teammate output for quality signals:
#   - Did the agent produce any output at all?
#   - Did it report a blocked or error state?
#   - Did any git changes land on main (forbidden)?
#
# Emits advisory to stderr (and a local log file) only — never blocks. Teammates
# surface their own errors; this hook is purely observational.
# Level: advisory (always warn, never block)

set -euo pipefail
trap 'exit 0' ERR

LOG_FILE="/tmp/.claude-teammate-quality-gate-$(id -u).log"

log() {
    local msg="$1"
    echo "$msg" >&2
    printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

INPUT=$(cat)
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

# --- SubagentStop / TeammateIdle: lifecycle events, not tool-call events ---
# These payloads don't carry a `.tool_name`/`.tool_response` shape like PostToolUse
# does, so handle them on their own branch rather than falling through to the
# PostToolUse-specific guards below.
if [[ "$HOOK_EVENT" == "SubagentStop" || "$HOOK_EVENT" == "TeammateIdle" ]]; then
    AGENT_NAME=$(echo "$INPUT" | jq -r '.agent_name // .subagent_type // .name // "unnamed"' 2>/dev/null || echo "unnamed")
    log "TEAMMATE-GATE [${AGENT_NAME}]: ${HOOK_EVENT} — worker completed."

    # Guard 3 still applies: warn if the completed worker left the repo on main.
    if git rev-parse --git-dir >/dev/null 2>&1; then
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
        if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
            log "TEAMMATE-GATE [${AGENT_NAME}]: current branch is '${CURRENT_BRANCH}' — teammate may have committed directly to main. Verify: git log -3."
        fi
    fi

    exit 0
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

# Only fire on Agent tool completions
[[ "$TOOL_NAME" == "Agent" ]] || exit 0

OUTPUT=$(echo "$INPUT" | jq -r '.tool_response // .output // ""' 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.tool_input.name // "unnamed"' 2>/dev/null || echo "unnamed")

# --- Guard 1: Empty output ---
if [[ -z "$OUTPUT" || "$OUTPUT" == "null" ]]; then
    log "TEAMMATE-GATE [${AGENT_NAME}]: produced no output — check if it was interrupted."
    exit 0
fi

# --- Guard 2: Error or blocked indicators ---
if echo "$OUTPUT" | grep -qiE "(error:|blocked:|BLOCKED|failed to|cannot|permission denied)" 2>/dev/null; then
    FIRST_ERROR=$(echo "$OUTPUT" | grep -iEm 1 "(error:|blocked:|BLOCKED|failed to|cannot|permission denied)" || echo "see output")
    log "TEAMMATE-GATE [${AGENT_NAME}]: possible error — \"${FIRST_ERROR}\""
fi

# --- Guard 3: Check if any git changes landed on main ---
# This is best-effort — only fires if git is accessible and we're in a git repo
if git rev-parse --git-dir >/dev/null 2>&1; then
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
        # Check if HEAD moved (new commits on main)
        RECENT_MSG=$(git log -1 --format="%s" 2>/dev/null || echo "")
        if [[ -n "$RECENT_MSG" ]]; then
            log "TEAMMATE-GATE [${AGENT_NAME}]: current branch is '${CURRENT_BRANCH}' — teammate may have committed directly to main. Verify: git log -3."
        fi
    fi
fi

exit 0
