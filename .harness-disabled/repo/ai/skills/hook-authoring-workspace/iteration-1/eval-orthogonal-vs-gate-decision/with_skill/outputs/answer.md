# Throttling `git status` re-runs: standalone hook, not pre-tool-gate-v2.sh

## Decision: its own file

This is a **standalone hook**, not an addition to `pre-tool-gate-v2.sh`.

The consolidated gate covers cross-cutting security/policy concerns (git safety, PR conventions, plan scope, session-init gating, tool-priority enforcement). "Track when `git status` last ran and throttle it" is exactly the kind of narrow, orthogonal *bookkeeping* concern that gets its own hook file with its own PreToolUse entry and a narrow matcher — the same precedent already set by `rtk-rewrite.sh` and the lean-ctx redirect living as separate entries rather than being folded into the gate. It has no security or policy dimension; it's session-scoped noise reduction. When unsure, the default is standalone anyway — and here we're not even unsure.

## The hook script

Save as `~/.dotfiles/.claude/hooks/git-status-throttle.sh` and `chmod +x` it:

```bash
#!/usr/bin/env bash
# git-status-throttle.sh — PreToolUse hook (matcher: Bash)
# Blocks re-running `git status` more than once every 10 seconds per session.
# Standalone by design: narrow bookkeeping concern, kept out of pre-tool-gate-v2.sh.

INPUT=$(cat)
eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "COMMAND=\(.tool_input.command // "")",
  @sh "SESSION_ID=\(.session_id // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

# Only care about Bash tool calls
[ "$TOOL_NAME" = "Bash" ] || exit 0

# Match `git status` anywhere in the command, including the rtk-rewritten
# form (`rtk git status`) produced by the rtk shell-rewrite hook.
echo "$COMMAND" | grep -Eq '(^|[;&| ])(rtk +)?git +status([^[:alnum:]-]|$)' || exit 0

# Per-session state file: uid avoids cross-user collisions on a shared
# machine; SESSION_ID -> CLAUDE_SESSION_ID -> "default" keeps it functional
# even if the session id isn't populated.
EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"
STATE_FILE="/tmp/.claude-git-status-throttle-$(id -u)-${EFFECTIVE_SESSION_ID}"

NOW=$(date +%s)
LAST=0
if [ -f "$STATE_FILE" ]; then
  LAST=$(cat "$STATE_FILE" 2>/dev/null)
fi
case "$LAST" in
  ''|*[!0-9]*) LAST=0 ;;   # corrupt/empty state file -> treat as never run
esac

ELAPSED=$((NOW - LAST))
if [ "$ELAPSED" -lt 10 ]; then
  REASON="[HARD-BLOCK — DO NOT RETRY] git status ran ${ELAPSED}s ago in this session (limit: once per 10s). Reuse the earlier output — the working tree has not been touched since."
  jq -cn --arg r "$REASON" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
fi

# Allowed: record this run and let the call through.
echo "$NOW" > "$STATE_FILE"
exit 0
```

Notes on why it's shaped this way:

- **Fall-through on parse failure** (`|| exit 0` on the `eval`/`jq` block): a broken payload must never block tool calls.
- **A plain `exit 1` would NOT block the call.** The only thing that blocks is the exact `hookSpecificOutput.permissionDecision: "deny"` JSON on stdout with exit 0 — that's what the deny branch emits. When the hook has nothing to say (not Bash, not `git status`, outside the throttle window), it exits 0 with no output.
- **`[HARD-BLOCK — DO NOT RETRY]` prefix** matches the `_deny()` convention in `pre-tool-gate-v2.sh`, so the agent's retry-loop short-circuit behavior applies to this hook's denials too.
- The regex also catches the `rtk git status` form, since the rtk-rewrite hook rewrites `git status` before this repo's shell commands actually run.

## Wiring into `.claude/settings.json`

Add a new entry under `hooks.PreToolUse` (alongside the existing gate entry — do not touch the gate's own entry):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -lc '$HOME/.dotfiles/.claude/hooks/git-status-throttle.sh'"
          }
        ]
      }
    ]
  }
}
```

Two wiring points that matter:

1. **Shell-form, not exec-form.** The command is a single string run through a real shell, so `$HOME` expands normally. In exec-form (`"command":"bash","args":[...]`) only Claude's own `$CLAUDE_PROJECT_DIR`/`$CLAUDE_PLUGIN_ROOT` tokens expand — a bare `$HOME` in the args array is passed literally and breaks. And `$CLAUDE_PROJECT_DIR` is the wrong token here anyway: this is the global settings file, and that variable resolves to whatever project is open, not the fixed `~/.dotfiles` location. `$HOME/.dotfiles/...` via shell-form is the correct portable form.
2. **Narrow matcher.** `"matcher": "Bash"` keeps the hook from firing on every tool call; the script itself narrows further to `git status`.

## Verify after wiring

Add this one entry, then live-test before touching anything else (a bad entry silently disables enforcement):

1. Restart or start a new Claude Code session so settings reload.
2. Ask Claude to run `git status` — it should succeed and write the state file.
3. Immediately ask again — the call should be denied with the `[HARD-BLOCK — DO NOT RETRY]` reason.
4. Wait 10+ seconds and run once more — it should succeed again.
