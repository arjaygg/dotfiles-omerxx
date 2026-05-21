#!/usr/bin/env bash
# UserPromptSubmit hook: environment preflight for PROD operations
# Fires when the prompt contains deployment/migration/PROD keywords.
# Checks: K8s auth, pctx running, CWD validity (not a stale worktree).
# Output: advisory JSON context if any check fails. Never blocks.

set -euo pipefail
trap 'exit 0' ERR

_INPUT=$(cat)
_PROMPT=$(echo "$_INPUT" | jq -r '.prompt // ""' 2>/dev/null)

# Only run for PROD-related prompts — skip for unrelated work
if ! echo "$_PROMPT" | grep -qiE '(deploy|migration|watchdog|prod|resume migration|kubectl|release v[0-9]|k8s|auc-conversion|circuit breaker|rollback|rollout|pod|namespace)'; then
    exit 0
fi

_WARNINGS=()
_CWD=$(pwd)

# 1. Stale worktree check: is CWD inside a .trees/ dir that no longer exists in git?
if [[ "$_CWD" == */.trees/* ]]; then
    _WT_NAME="${_CWD##*/.trees/}"
    _WT_NAME="${_WT_NAME%%/*}"
    _WT_LIST=$(git worktree list --porcelain 2>/dev/null | grep "^worktree " | awk '{print $2}' || echo "")
    if ! echo "$_WT_LIST" | grep -q "\.trees/${_WT_NAME}"; then
        _WARNINGS+=("⚠️  CWD appears to be inside a removed worktree (.trees/${_WT_NAME} not found in git worktree list). Shell may be stale.")
    fi
fi

# 2. K8s auth check: can we reach the cluster?
if command -v kubectl >/dev/null 2>&1; then
    if ! kubectl auth can-i get pods -n auc-conversion --request-timeout=3s >/dev/null 2>&1; then
        _WARNINGS+=("⚠️  kubectl: cannot reach auc-conversion namespace (auth failure or no cluster context). Run: kubectl config get-contexts")
    fi
fi

# 3. pctx health: is the MCP gateway running?
if ! pgrep -f 'pctx.*mcp' >/dev/null 2>&1; then
    # pctx may start on-demand; only warn if Serena init flag is also absent
    _SESSION_ID=$(echo "$_INPUT" | jq -r '.session_id // ""' 2>/dev/null)
    _SERENA_FLAG="/tmp/.claude-serena-init-$(id -u)-${_SESSION_ID:-0}"
    if [[ ! -f "$_SERENA_FLAG" ]]; then
        _WARNINGS+=("⚠️  pctx MCP process not detected and Serena init not complete. MCP tools may be unavailable.")
    fi
fi

# No issues found — exit cleanly
if [[ ${#_WARNINGS[@]} -eq 0 ]]; then
    exit 0
fi

# Output advisory context
_MSG="[ENV PREFLIGHT] Environment checks failed before PROD operation:
$(printf '%s\n' "${_WARNINGS[@]}")
Resolve the above before proceeding to avoid mid-task failures."

echo "$_MSG" | python3 -c '
import json, sys
m = sys.stdin.read().strip()
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": m}}))
'
