#!/usr/bin/env bash
# UserPromptSubmit hook: auto-inject session init preamble
# If serena-init or ctx-loaded flags are missing, prepend a forced init
# instruction so Claude completes the sequence before answering.
#
# Fires on every prompt; exits immediately (no-op) once both flags are set.

set -euo pipefail

# UserPromptSubmit hooks receive session_id in stdin JSON (not as env var).
_INPUT=$(cat)
_SESSION_ID=$(echo "$_INPUT" | jq -r '.session_id // ""' 2>/dev/null)
[[ -z "${_SESSION_ID:-}" ]] && exit 0

_SERENA_FLAG="/tmp/.claude-serena-init-$(id -u)-${_SESSION_ID}"
_CTX_FLAG="/tmp/.claude-ctx-loaded-$(id -u)-${_SESSION_ID}"
# Warm-session shortcut: if pctx-functions.md was written today, auto-set flags
# and skip the init mandate — mirrors the same optimization in pre-tool-gate-v2.sh.
_PROJECT_CWD=$(echo "$_INPUT" | jq -r '.cwd // ""')
_PCTX_FILE="${CLAUDE_PROJECT_DIR:-${_PROJECT_CWD:-$PWD}}/plans/pctx-functions.md"
_TODAY=$(date +%Y-%m-%d)
if [[ -f "$_PCTX_FILE" ]]; then
    _FILE_DATE=$(stat -f %Sm -t %Y-%m-%d "$_PCTX_FILE" 2>/dev/null         || stat -c %y "$_PCTX_FILE" 2>/dev/null | cut -c1-10         || echo "")
    if [[ "$_FILE_DATE" == "$_TODAY" ]]; then
        touch "$_SERENA_FLAG" "$_CTX_FLAG" 2>/dev/null
    fi
fi
_MISSING_SERENA=false
_MISSING_CTX=false

[[ ! -f "$_SERENA_FLAG" ]] && _MISSING_SERENA=true
[[ ! -f "$_CTX_FLAG" ]]   && _MISSING_CTX=true

# Both flags set — nothing to do
if ! $_MISSING_SERENA && ! $_MISSING_CTX; then
    exit 0
fi

# Build the missing steps list
_STEPS=""
if $_MISSING_SERENA; then
    _STEPS+="  - mcp__pctx__list_functions (then write result to plans/pctx-functions.md)\n"
    _STEPS+="  - Serena.initialInstructions()\n"
fi
if $_MISSING_CTX; then
    _STEPS+="  - LeanCtx.ctxCall({ name: \"ctx_intent\", arguments: { query: \"<describe the current task>\" } })\n"
fi

cat <<EOF | python3 -c 'import json,sys; m=sys.stdin.read().strip(); print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":m}}))'
[SESSION INIT INCOMPLETE] Run the following via mcp__pctx__execute_typescript BEFORE answering this prompt:
$(printf '%b' "$_STEPS")
Batch all missing steps into ONE execute_typescript call with Promise.all() where possible.
Also run as a SEPARATE direct tool call (NOT inside execute_typescript): ToolSearch({ query: "select:TaskCreate,TaskUpdate,EnterPlanMode,Monitor,WebSearch" }) to pre-load deferred tool schemas for this session.
After the init call completes, continue with the user's original request in the same turn.
EOF
