#!/usr/bin/env bash
# UserPromptSubmit dispatcher — single login-shell entry for all per-prompt hooks.
# Replaces 12+ separate bash -lc entries with one process, paying the login-shell
# startup cost once and running all sub-hooks as plain `bash script.sh`.
#
# Output contract: collects hookSpecificOutput.additionalContext from each hook,
# combines them into a single JSON response. Propagates non-zero exits from
# blocking hooks (session-init-enforcer, session-duration-guard).

set -uo pipefail

# Read stdin once — piped to each hook that needs it
_INPUT=$(cat)

_COMBINED_CTX=""

# FD3 = original stderr so sub-hooks' stderr flows through to Claude Code
exec 3>&2

# ─── Helper: run a hook, let stderr through, capture stdout JSON ───────────────
_run() {
    local _script="$1"
    local _out _rc
    _out=$(echo "$_INPUT" | bash "$_script" 2>&3)
    _rc=$?
    if [[ $_rc -ne 0 ]]; then
        return $_rc
    fi
    if [[ -n "$_out" ]]; then
        local _ctx
        _ctx=$(python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    ctx = d.get('hookSpecificOutput', {}).get('additionalContext', '')
    if ctx: print(ctx, end='')
except:
    pass
" <<< "$_out" 2>/dev/null || true)
        if [[ -n "$_ctx" ]]; then
            [[ -n "$_COMBINED_CTX" ]] && _COMBINED_CTX+=$'\n'
            _COMBINED_CTX+="$_ctx"
        fi
    fi
    return 0
}

# ─── Helper: run a side-effect hook in background (no output needed) ──────────
_bg() {
    (echo "$_INPUT" | bash "$1" &>/dev/null) &
}

# ─────────────────────────────────────────────────────────────────────────────
# ORDER MATTERS: blocking guards run first so they can short-circuit
# ─────────────────────────────────────────────────────────────────────────────

# 1. Session init guard — may output additionalContext demanding init steps
_run "$HOME/.dotfiles/.claude/hooks/session-init-enforcer.sh" || exit $?

# 2. Session duration guard — exits 1 at 500 turns, writes warnings to stderr
_run "$HOME/.dotfiles/.claude/hooks/session-duration-guard.sh" || exit $?

# 3. QMD sync — fire-and-forget side effect, no stdin content needed
_bg "$HOME/.dotfiles/.claude/hooks/qmd-sync.sh"

# 4. Plans health check — outputs additionalContext for missing artifacts
_run "$HOME/.dotfiles/.claude/hooks/plans-healthcheck.sh"

# 5. Prompt parallelism hint — nudges parallel tool use
_run "$HOME/.dotfiles/.claude/hooks/prompt-parallelism-hint.sh"

# 6. Plan/TodoWrite reminder — reminds to create task lists for multi-step work
_run "$HOME/.dotfiles/.claude/hooks/plan-todowrite-reminder.sh"

# 7. tmux activity bridge — fire-and-forget, no stdin
(bash "$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh" activity-start &>/dev/null) &

# 8. Prompt capture — logs prompts for analytics
_bg "$HOME/.dotfiles/.claude/hooks/prompt-capture.sh"

# 9. Prompt score correction — scoring side-effect
_bg "$HOME/.dotfiles/.claude/hooks/prompt-score-correction.sh"

# 11. Symbol intent — records symbol references
_bg "$HOME/.dotfiles/.claude/hooks/symbol-intent.sh"

# 12. Env preflight — checks required env vars
_run "$HOME/.dotfiles/.claude/hooks/env-preflight.sh"

# 13. lean-ctx observe — fire-and-forget telemetry
(echo "$_INPUT" | lean-ctx hook observe &>/dev/null) &

# ─── Output combined additionalContext ────────────────────────────────────────
if [[ -n "$_COMBINED_CTX" ]]; then
    python3 -c "
import json, sys
msg = sys.stdin.read()
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': msg}}))
" <<< "$_COMBINED_CTX"
fi

wait
exit 0
