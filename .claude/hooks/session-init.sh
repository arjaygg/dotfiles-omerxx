#!/usr/bin/env bash
# SessionStart hook: record session start timestamp for session-scoped tracking
# Used by pre-compact.sh (H7) to find files edited THIS session (not since last git op).

set -euo pipefail
trap 'echo "HOOK CRASH (session-init.sh line $LINENO): $BASH_COMMAND"; exit 0' ERR

# Emit the SessionStart payload. Three encoders, tried in order, so the hook degrades
# gracefully on a host missing jq, python3, or both — it must never emit malformed JSON.
emit_hook_context() {
    local msg="$1"
    if command -v jq >/dev/null 2>&1; then
        jq -n --arg msg "$msg" \
            '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $msg}}'
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
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
        return 0
    fi
    # Last resort: escape the five characters JSON forbids raw in a string.
    local escaped="$msg"
    escaped="${escaped//\\/\\\\}"
    escaped="${escaped//\"/\\\"}"
    escaped="${escaped//$'\t'/\\t}"
    escaped="${escaped//$'\r'/\\r}"
    escaped="${escaped//$'\n'/\\n}"
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' \
        "$escaped"
}

# One-line-per-phase digest of the generated router, built from the manifest with awk so it
# needs neither jq nor python3. Empty output if the manifest is absent.
router_digest() {
    # Resolve relative to this hook: <repo>/.claude/hooks/session-init.sh -> <repo>.
    local hook_dir repo manifest
    hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo="$(cd "$hook_dir/../.." && pwd)"
    manifest="$repo/ai/skills/manifest.csv"
    [[ -r "$manifest" ]] || manifest="$HOME/.dotfiles/ai/skills/manifest.csv"
    [[ -r "$manifest" ]] || return 0
    awk -F, 'NR>1 && $1 != "" { order[$2] = order[$2] " " $1 }
        END {
            n = split("orient diagnose plan implement review ship operate", phases, " ")
            for (i = 1; i <= n; i++)
                if (phases[i] in order) printf "  %s:%s\n", phases[i], order[phases[i]]
        }' "$manifest"
}

# Write session-start timestamp to a per-user temp file
TIMESTAMP_FILE="/tmp/.claude-session-start-$(id -u)"
date '+%s' > "$TIMESTAMP_FILE"

# Warn if a substantial session already ran in this directory recently
_DUPLICATE_WARN="$(bash "$HOME/.dotfiles/.claude/hooks/duplicate-session-check.sh" 2>/dev/null || true)"

# Kill stale pctx processes from other worktrees to prevent cross-contamination.
# Each stdio pctx session inherits its CWD, so a process started in worktree A
# must not serve worktree B. Only kill processes with hardcoded worktree paths.
CWD="$(pwd)"
if [[ "$CWD" == */.trees/* ]]; then
    WORKTREE_NAME="${CWD##*/.trees/}"
    WORKTREE_NAME="${WORKTREE_NAME%%/*}"
    while IFS= read -r line; do
        pid="${line%% *}"
        if echo "$line" | grep -q '\.trees/[^/]*/\.config/pctx\.json' && \
           ! echo "$line" | grep -q "\.trees/${WORKTREE_NAME}/\.config/pctx\.json"; then
            kill "$pid" 2>/dev/null || true
        fi
    done < <(pgrep -fl 'pctx.*mcp.*start' 2>/dev/null || true)
fi

# Inject mandatory session-init instruction so Claude sees it at session start
# Serena.initialInstructions() is only needed when a .serena/ config dir is present.
HAS_SERENA=false
dir="$(pwd)"
while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.serena" ]]; then
        HAS_SERENA=true
        break
    fi
    dir="$(dirname "$dir")"
done

_SESSION_MSG=""
if $HAS_SERENA; then
    # Count available memories for the hint
    _SERENA_DIR="$(pwd)/.serena/memories"
    _MEM_COUNT=0
    if [[ -d "$_SERENA_DIR" ]]; then
        _MEM_COUNT=$(find "$_SERENA_DIR" -name "*.md" ! -path "*/_archive/*" 2>/dev/null | wc -l | tr -d ' ')
    fi
    _MEM_HINT=""
    if [[ "$_MEM_COUNT" -gt 0 ]]; then
        _MEM_HINT="  - Serena.readMemory({ name: \"START_HERE\" }) — load project memories ($_MEM_COUNT available)"
    fi

    _SESSION_MSG="$(cat <<EOT
hook: session-init
status: pending
steps not yet run this session:
  - mcp__pctx__list_functions (then write result to plans/pctx-functions.md)
  - Serena.initialInstructions() — load project-specific rules
${_MEM_HINT}
  - LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "<task-description>" } }) — primes lean-ctx task scoping for ctx_search/ctx_read (raw grep/rg stay blocked by global permissions.deny regardless of this call)
note: skip if plans/pctx-functions.md already exists and was written today
EOT
)"
else
    _SESSION_MSG="$(cat <<'EOT'
hook: session-init
status: pending
steps not yet run this session:
  - mcp__pctx__list_functions (then write result to plans/pctx-functions.md)
  - LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "<task-description>" } }) — primes lean-ctx task scoping for ctx_search/ctx_read (raw grep/rg stay blocked by global permissions.deny regardless of this call)
note: Serena.initialInstructions skipped — no .serena/ config found in this directory tree; skip all steps if plans/pctx-functions.md already exists and was written today
EOT
)"
fi

# Register QMD collection for this worktree on first session (idempotent)
if [[ "$CWD" == */.trees/* ]]; then
    _QMD="$HOME/.bun/bin/qmd"
    if [[ -x "$_QMD" ]]; then
        _WT_NAME="${CWD##*/.trees/}"
        _WT_NAME="${_WT_NAME%%/*}"
        if ! "$_QMD" collection list 2>/dev/null | grep -qF "${_WT_NAME}"; then
            "$_QMD" collection add "$CWD" --name "$_WT_NAME" --mask "**/*.md" 2>/dev/null || true
        fi
    fi
fi

# Update tmux window name with Claude session context
"$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh" session-start >/dev/null 2>&1 &

# Inject the skill router once per session. The marker file is keyed to this session's
# start timestamp, so a new session re-injects and a re-fired hook within one session does not.
_ROUTER_MARKER="${TMPDIR:-/tmp}/.claude-router-injected-$(id -u)-$(cat "$TIMESTAMP_FILE" 2>/dev/null || echo 0)"
if [[ ! -e "$_ROUTER_MARKER" ]]; then
    _ROUTER="$(router_digest)"
    if [[ -n "$_ROUTER" ]]; then
        : > "$_ROUTER_MARKER" 2>/dev/null || true
        _SESSION_MSG="${_SESSION_MSG}

skill router (generated from ai/skills/manifest.csv; full table: ai/skills/using-my-skills/SKILL.md)
${_ROUTER}
core behaviors (non-negotiable): surface assumptions; stop on confusion; push back with numbers;
enforce simplicity; hold scope; verify with evidence."
    fi
fi

if [[ -n "${_DUPLICATE_WARN:-}" ]]; then
    _SESSION_MSG="${_DUPLICATE_WARN}

${_SESSION_MSG}"
fi

emit_hook_context "$_SESSION_MSG"

exit 0
