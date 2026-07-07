#!/usr/bin/env bash
# SessionStart hook: verify the configured model/advisor/auth look reachable
# before the user sends a prompt, instead of the session silently producing
# no response later (insights report: "asked twice, got only a model access
# error, no answer at all").
#
# Best-effort and fail-open by design: this can only catch config-shape and
# network-reachability problems from a plain bash subprocess. It cannot
# guarantee the API call itself will succeed. Never blocks session start.

set -uo pipefail
trap 'exit 0' ERR

emit_hook_context() {
    local msg="$1"
    python3 - "$msg" <<'PYEOF'
import json, sys
msg = sys.argv[1]
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": msg
    }
}))
PYEOF
}

VALID_MODEL_RE='^(opusplan|opus|sonnet|haiku|fable|best|claude-[a-z0-9.-]+)$'
issues=()

# Resolve effective "model" setting: project settings.json wins over global.
_read_setting() {
    local key="$1"
    local val=""
    if [[ -f "./.claude/settings.json" ]]; then
        val=$(jq -r --arg k "$key" '.[$k] // empty' "./.claude/settings.json" 2>/dev/null || echo "")
    fi
    if [[ -z "$val" && -f "$HOME/.claude/settings.json" ]]; then
        val=$(jq -r --arg k "$key" '.[$k] // empty' "$HOME/.claude/settings.json" 2>/dev/null || echo "")
    fi
    echo "$val"
}

model="$(_read_setting model)"
if [[ -n "$model" ]] && ! [[ "$model" =~ $VALID_MODEL_RE ]]; then
    issues+=("model \"$model\" does not match any known alias/ID pattern (opusplan/opus/sonnet/haiku/fable/best/claude-*) — verify it's not a typo before relying on it")
fi

advisor_model="$(_read_setting advisorModel)"
if [[ -n "$advisor_model" ]] && ! [[ "$advisor_model" =~ $VALID_MODEL_RE ]]; then
    issues+=("advisorModel \"$advisor_model\" does not match any known alias/ID pattern — the advisor tool will silently fail to fire if this is wrong")
fi

# Auth: accept any of the recognized mechanisms; only warn if none present.
has_auth=false
[[ -n "${ANTHROPIC_API_KEY:-}" ]] && has_auth=true
[[ -n "${CLAUDE_CODE_USE_BEDROCK:-}" ]] && has_auth=true
[[ -n "${CLAUDE_CODE_USE_VERTEX:-}" ]] && has_auth=true
[[ -f "$HOME/.claude/.credentials.json" ]] && has_auth=true
if ! $has_auth; then
    issues+=("no recognized auth mechanism found (ANTHROPIC_API_KEY, Bedrock/Vertex env vars, or ~/.claude/.credentials.json) — API calls this session may fail with no response")
fi

# Network reachability: short timeout, never let this hang session start.
if command -v curl &>/dev/null; then
    http_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 https://api.anthropic.com/ 2>/dev/null || echo "000")
    if [[ "$http_code" == "000" ]]; then
        issues+=("api.anthropic.com unreachable within 2s (DNS/network/VPN) — expect no-response failures this session")
    fi
fi

if [[ ${#issues[@]} -gt 0 ]]; then
    msg="hook: model-availability-check
status: ISSUES FOUND — surface these to the user immediately, don't wait for a failed request
"
    for i in "${issues[@]}"; do
        msg+=$'\n'"  - $i"
    done
    emit_hook_context "$msg"
fi

exit 0
