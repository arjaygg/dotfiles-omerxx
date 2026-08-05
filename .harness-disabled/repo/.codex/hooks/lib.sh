#!/usr/bin/env bash
set -euo pipefail

codex_hook_log() {
  printf '[codex-hook] %s\n' "$*" >&2
}

codex_hook_run() {
  local name="$1"
  local script_path="$2"
  local input="${3-}"

  if [[ "${CODEX_HOOKS_DISABLED:-0}" == "1" ]]; then
    codex_hook_log "${name}: skipped (CODEX_HOOKS_DISABLED=1)"
    return 0
  fi

  if [[ ! -f "$script_path" ]]; then
    codex_hook_log "${name}: missing script: $script_path"
    [[ "${CODEX_HOOKS_STRICT:-0}" == "1" ]] && return 1 || return 0
  fi

  if [[ ! -r "$script_path" ]]; then
    codex_hook_log "${name}: unreadable script: $script_path"
    [[ "${CODEX_HOOKS_STRICT:-0}" == "1" ]] && return 1 || return 0
  fi

  local rc=0
  if [[ -n "$input" ]]; then
    printf '%s' "$input" | /usr/bin/env bash "$script_path" || rc=$?
  else
    /usr/bin/env bash "$script_path" || rc=$?
  fi

  if [[ "$rc" -ne 0 ]]; then
    codex_hook_log "${name}: downstream failed (exit=$rc) script=$script_path"
    [[ "${CODEX_HOOKS_STRICT:-0}" == "1" ]] && return "$rc"
  fi

  return 0
}
