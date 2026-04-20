#!/usr/bin/env bash
# UserPromptSubmit hook: auto-inject session init preamble
# If serena-init or ctx-loaded flags are missing, prepend a forced init
# instruction so Claude completes the sequence before answering.
#
# Fires on every prompt; exits immediately (no-op) once both flags are set.

set -euo pipefail

# CRITICAL: Drain stdin — all UserPromptSubmit hooks should consume stdin
cat > /dev/null

[[ -z "${CLAUDE_SESSION_ID:-}" ]] && exit 0

_SERENA_FLAG="/tmp/.claude-serena-init-$(id -u)-${CLAUDE_SESSION_ID}"
_CTX_FLAG="/tmp/.claude-ctx-loaded-$(id -u)-${CLAUDE_SESSION_ID}"

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
    _STEPS+="  - LeanCtx.ctxIntent({ query: '<describe the current task>' })\n"
fi

cat <<EOF | python3 -c 'import json,sys; m=sys.stdin.read().strip(); print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":m}}))'
[SESSION INIT INCOMPLETE] Run the following via mcp__pctx__execute_typescript BEFORE answering this prompt:
$(printf '%b' "$_STEPS")
Batch all missing steps into ONE execute_typescript call with Promise.all() where possible.
After the init call completes, continue with the user's original request in the same turn.
EOF
