# PreToolUse hook: allow `rm -rf` once per session, deny the second attempt

## Design decisions (per the hook-authoring conventions)

**Standalone file, not folded into `pre-tool-gate-v2.sh`** — "has rm -rf already run this session" is a narrow, orthogonal bookkeeping concern, not a cross-cutting security/policy rule. Per convention §1, it gets its own hook file (same precedent as `rtk-rewrite.sh` and the lean-ctx redirect).

**State-file naming** — per convention §5, key the flag file on the effective session id *and* the calling user, in `/tmp`:

```bash
EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"
LOG_FILE="/tmp/.claude-rmrf-once-$(id -u)-${EFFECTIVE_SESSION_ID}"
```

- `$(id -u)` prevents collisions between users on a shared machine (and the permission errors that would follow if another user already owns the file).
- The `SESSION_ID → CLAUDE_SESSION_ID → "default"` fallback chain keeps the hook functional even when the session id isn't populated in some invocation context.
- Reuse this exact pattern — don't invent a new naming scheme.

**Deny mechanism** — a plain `exit 1` does **not** block the tool call. The only thing that blocks is this exact JSON on stdout, emitted with **exit 0** (convention §3), with the reason prefixed `[HARD-BLOCK — DO NOT RETRY]` to match `pre-tool-gate-v2.sh`'s `_deny()` convention (§4):

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[HARD-BLOCK — DO NOT RETRY] ..."}}
```

If the hook has nothing to say (not Bash, no `rm -rf`, or first occurrence), it exits 0 with **no output** so the call passes through.

## The complete hook script

`~/.dotfiles/.claude/hooks/rmrf-once-per-session.sh`:

```bash
#!/usr/bin/env bash
# rmrf-once-per-session.sh — PreToolUse hook
# Allows the Bash tool to run `rm -rf` once per session; denies any
# subsequent `rm -rf` in the same session. Standalone bookkeeping hook —
# intentionally NOT folded into pre-tool-gate-v2.sh (narrow, orthogonal
# concern; see pre-tool-gate-v2.sh header for the precedent).

set -u

# --- Read stdin payload; fall through on any parse failure ---
INPUT=$(cat)
eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "COMMAND=\(.tool_input.command // "")",
  @sh "SESSION_ID=\(.session_id // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

# --- Only care about Bash commands containing rm -rf ---
[ "$TOOL_NAME" = "Bash" ] || exit 0

# Match rm -rf / rm -fr, including combined+split flag spellings
# (rm -rf, rm -fr, rm -r -f, rm -f -r).
if ! echo "$COMMAND" | grep -Eq '(^|[;&|[:space:]])rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*|-r[[:space:]]+-f|-f[[:space:]]+-r)([[:space:]]|$)'; then
  exit 0
fi

# --- Per-session, per-user state file (convention §5 — reuse exactly) ---
EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"
LOG_FILE="/tmp/.claude-rmrf-once-$(id -u)-${EFFECTIVE_SESSION_ID}"

if [ -f "$LOG_FILE" ]; then
  # Second (or later) rm -rf this session — deny with the exact schema
  # that actually blocks the call. exit 0, NOT exit 1.
  REASON="[HARD-BLOCK — DO NOT RETRY] 'rm -rf' has already been run once this session (recorded in ${LOG_FILE}). A second recursive force-delete in the same session is blocked. If another deletion is genuinely required, ask the user to run it manually or start a new session."
  jq -cn --arg r "$REASON" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
fi

# First occurrence: record it and let the call pass through (no output).
printf '%s\n' "$COMMAND" > "$LOG_FILE" 2>/dev/null || true
exit 0
```

Make it executable:

```bash
chmod +x $HOME/.dotfiles/.claude/hooks/rmrf-once-per-session.sh
```

## Wiring into `.claude/settings.json`

Use **shell-form** so `$HOME` expands (convention §6 — exec-form `{"command":"bash","args":[...]}` does *not* expand `$HOME` in args; only `$CLAUDE_PROJECT_DIR`/`$CLAUDE_PLUGIN_ROOT` tokens expand there). Add as its own entry alongside the existing gate, matched to Bash only:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOME/.dotfiles/.claude/hooks/rmrf-once-per-session.sh\""
          }
        ]
      }
    ]
  }
}
```

## Behavior summary

| Attempt | State file | Result |
|---|---|---|
| 1st `rm -rf` in session | absent → created | Passes through (exit 0, no output) |
| 2nd+ `rm -rf`, same session | present | Denied via `permissionDecision:"deny"` JSON, exit 0 |
| New session | different `EFFECTIVE_SESSION_ID` → new file | Counter effectively resets |
| Non-Bash tool / no `rm -rf` / jq parse failure | n/a | Falls through, exit 0 |

Note the two most common mistakes this design avoids: using `exit 1` to deny (it doesn't block — only the JSON schema does), and keying state on a global path like `/tmp/.claude-rmrf-once` (which collides across sessions and across users on a shared machine).
