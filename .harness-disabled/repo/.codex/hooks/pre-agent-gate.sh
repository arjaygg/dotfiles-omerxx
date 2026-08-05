#!/usr/bin/env bash
# Codex PreToolUse gate for subagent spawns — the Codex analogue of
# .claude/hooks/pre-tool-gate-v2.sh Sections 7b and 8.
#
# Enforcement split follows decisions/0013: hard-deny ONLY where the check is a
# fixed enum or a filesystem fact; warn everywhere the check needs judgement or
# relies on a proxy. Everything unknown fails OPEN — a malformed payload or a
# Codex version whose subagent payload shape differs must never strand a session.
#
#   DENY  (exit 2): model slug outside the supported enum
#   DENY  (exit 2): spec path referenced in the prompt does not exist on disk
#   WARN  (exit 0): no explicit model (silently inherits the coordinator tier)
#   WARN  (exit 0): no plans/specs/<label>.md referenced at all
#   WARN  (exit 0): >3 spawns inside the rolling window (proxy for fan-out)
#
# Policy: ai/rules/delegation-and-context-admission.md, ai/skills/model-routing/SKILL.md.
set -euo pipefail

INPUT="$(cat || true)"
[[ -z "$INPUT" ]] && exit 0

if [[ "${CODEX_HOOKS_DISABLED:-0}" == "1" ]]; then
  exit 0
fi

# ---------------------------------------------------------------- parse
# Codex payload shape varies by version; pull each field best-effort and treat
# an empty result as "unknown", never as a violation.
if ! command -v jq >/dev/null 2>&1; then
  echo "[codex-hook] pre-agent-gate: jq missing; gate skipped (fail-open)" >&2
  exit 0
fi

# Unparseable payload → say nothing and allow. Warning on a payload we could not
# read would be noise attributed to the spawn, not to the hook.
if ! printf '%s' "$INPUT" | jq -e . >/dev/null 2>&1; then
  exit 0
fi

_field() {
  local expr="$1"
  printf '%s' "$INPUT" | jq -r "$expr // empty" 2>/dev/null || true
}

AGENT_MODEL="$(_field '.tool_input.model // .model // .input.model')"
PROMPT="$(_field '.tool_input.instructions // .instructions // .tool_input.prompt // .prompt')"

# ------------------------------------------------- 1. model enum (HARD DENY)
# Deterministic: a fixed set of slugs, mirroring check_agent_models() in
# .claude/hooks/config-integrity.sh. Refresh from `models_cache.json` when
# OpenAI ships a new tier.
SUPPORTED='gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna gpt-5.5 gpt-5.4 gpt-5.4-mini'
if [[ -n "$AGENT_MODEL" ]]; then
  _ok=0
  for _m in $SUPPORTED; do
    [[ "$AGENT_MODEL" == "$_m" ]] && _ok=1 && break
  done
  if [[ "$_ok" -eq 0 ]]; then
    echo "CODEX AGENT GATE DENY: model '$AGENT_MODEL' is not a supported slug." >&2
    echo "Supported: $SUPPORTED" >&2
    echo "See ai/skills/model-routing/SKILL.md § Codex tiers." >&2
    exit 2
  fi
else
  echo "WARN: [tier-unset] Subagent spawn declares no model — it inherits the coordinator tier (gpt-5.6-sol), the most expensive option. Pin a tier explicitly: luna for mechanical work, terra for judgement, 5.4-mini for extraction. See ai/rules/delegation-and-context-admission.md §4." >&2
fi

# ------------------------------------------------ 2. frozen spec (HARD DENY)
# Deterministic: the referenced path either exists or it does not. Only fires
# when the prompt names a spec — an unreferenced spec is a warn, since the hook
# cannot know whether the work warranted one.
if [[ -n "$PROMPT" ]]; then
  SPEC_REF="$(printf '%s' "$PROMPT" | grep -oE '(^|[^A-Za-z0-9_/.-])plans/specs/[A-Za-z0-9._-]+\.md' | head -1 | sed -E 's#^[^p]*##' || true)"
  if [[ -n "$SPEC_REF" ]]; then
    if [[ ! -f "$SPEC_REF" && ! -f "${CODEX_PROJECT_ROOT:-$PWD}/$SPEC_REF" ]]; then
      echo "CODEX AGENT GATE DENY: frozen spec '$SPEC_REF' referenced in the prompt does not exist." >&2
      echo "Write the spec before spawning the worker — an unwritten spec is why cheap tiers fail." >&2
      echo "See ai/rules/agent-user-global.md § Orchestrator-Worker Paradigm." >&2
      exit 2
    fi
  else
    echo "WARN: [spec-missing] Subagent spawn references no plans/specs/<label>.md. Non-trivial delegated work needs a frozen spec (goal, file scope, constraints, verification, return contract). See ai/rules/delegation-and-context-admission.md §5." >&2
  fi
fi

# --------------------------------------------------- 3. fan-out (WARN ONLY)
# Proxy, not a count: the hook sees spawns, never completions, so "concurrent"
# is approximated by a rolling window. Warn-only for exactly that reason —
# promoting this to deny would need real completion signal, which PreToolUse
# does not carry. Mirrors ADL-022's reasoning for the Claude-side fan-out gate.
WINDOW_SECONDS=60
FANOUT_CAP=3
STATE_DIR="${TMPDIR:-/tmp}/codex-agent-gate"
SESSION_ID="$(_field '.session_id // .sessionId')"
[[ -z "$SESSION_ID" ]] && SESSION_ID="default"
STATE_FILE="$STATE_DIR/$(printf '%s' "$SESSION_ID" | tr -c 'A-Za-z0-9._-' '_')"

mkdir -p "$STATE_DIR" 2>/dev/null || true
NOW="$(date +%s)"
if [[ -w "$STATE_DIR" ]]; then
  printf '%s\n' "$NOW" >>"$STATE_FILE" 2>/dev/null || true
  RECENT=0
  if [[ -f "$STATE_FILE" ]]; then
    # Keep only timestamps inside the window, then count them.
    _kept="$(awk -v now="$NOW" -v w="$WINDOW_SECONDS" '($1 + w) >= now' "$STATE_FILE" 2>/dev/null || true)"
    printf '%s\n' "$_kept" >"$STATE_FILE" 2>/dev/null || true
    RECENT="$(printf '%s\n' "$_kept" | grep -c '[0-9]' || true)"
  fi
  if [[ "$RECENT" -gt "$FANOUT_CAP" ]]; then
    echo "WARN: [fan-out-window] $RECENT subagent spawns in the last ${WINDOW_SECONDS}s exceeds the cap of $FANOUT_CAP concurrent agents (ai/rules/agent-user-global.md). This is a rolling-window proxy — completions are not visible at PreToolUse, so confirm manually rather than treating the count as exact." >&2
  fi
fi

exit 0
