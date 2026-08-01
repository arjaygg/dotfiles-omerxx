#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.dotfiles/.codex/hooks/lib.sh"

# Keep one copy of payload in case downstream scripts expect stdin.
INPUT="$(cat || true)"
COMBINED_CTX=""
BLOCK_REASON=""

_append_ctx() {
  local ctx="$1"
  if [[ -n "$ctx" ]]; then
    [[ -n "$COMBINED_CTX" ]] && COMBINED_CTX+=$'\n'
    COMBINED_CTX+="$ctx"
  fi
}

_run_prompt_hook() {
  local name="$1"
  local script_path="$2"
  local out rc parsed ctx reason

  if [[ "${CODEX_HOOKS_DISABLED:-0}" == "1" ]]; then
    codex_hook_log "${name}: skipped (CODEX_HOOKS_DISABLED=1)"
    return 0
  fi

  if [[ ! -f "$script_path" || ! -r "$script_path" ]]; then
    codex_hook_log "${name}: missing or unreadable script: $script_path"
    [[ "${CODEX_HOOKS_STRICT:-0}" == "1" ]] && return 1 || return 0
  fi

  set +e
  out=$(printf '%s' "$INPUT" | /usr/bin/env bash "$script_path")
  rc=$?
  set -e

  if [[ "$rc" -ne 0 ]]; then
    codex_hook_log "${name}: downstream failed (exit=$rc) script=$script_path"
    [[ "${CODEX_HOOKS_STRICT:-0}" == "1" ]] && return "$rc" || return 0
  fi

  [[ -z "$out" ]] && return 0

  parsed=$(python3 -c '
import json, sys
text = sys.stdin.read()
try:
    data = json.loads(text)
except Exception:
    print(json.dumps({"context": text.strip(), "reason": ""}))
    raise SystemExit(0)
hook = data.get("hookSpecificOutput") or {}
context = hook.get("additionalContext") or ""
reason = data.get("reason") if data.get("decision") == "block" else ""
print(json.dumps({"context": context, "reason": reason or ""}))
' <<< "$out" 2>/dev/null || printf '{"context":"","reason":""}')

  ctx=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("context", ""), end="")' <<< "$parsed" 2>/dev/null || true)
  reason=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("reason", ""), end="")' <<< "$parsed" 2>/dev/null || true)

  _append_ctx "$ctx"
  if [[ -z "$BLOCK_REASON" && -n "$reason" ]]; then
    BLOCK_REASON="$reason"
  fi
}

_run_prompt_hook "session-init-enforcer" "$HOME/.dotfiles/.claude/hooks/session-init-enforcer.sh"
# plans-healthcheck.sh's auto-install is opt-in (DOTFILES_AUTO_INSTALL=1, unset
# here) — this used to set CLAUDE_HOOKS_DISABLE_AUTO_INSTALL=1 to suppress the
# old opt-out gate; that var is now a no-op since M5 (2026-07-08) flipped the
# default to disabled.
_run_prompt_hook "plans-healthcheck" "$HOME/.dotfiles/.claude/hooks/plans-healthcheck.sh"
_run_prompt_hook "plan-todowrite-reminder" "$HOME/.dotfiles/.claude/hooks/plan-todowrite-reminder.sh"

if [[ -n "$COMBINED_CTX" || -n "$BLOCK_REASON" ]]; then
  COMBINED_CTX="$COMBINED_CTX" BLOCK_REASON="$BLOCK_REASON" python3 -c '
import json, os
context = os.environ.get("COMBINED_CTX", "")
reason = os.environ.get("BLOCK_REASON", "")
output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}
if context:
    output["hookSpecificOutput"]["additionalContext"] = context
if reason:
    output["decision"] = "block"
    output["reason"] = reason
print(json.dumps(output))
'
fi
