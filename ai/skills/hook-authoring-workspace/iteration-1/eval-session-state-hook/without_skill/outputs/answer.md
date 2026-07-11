# PreToolUse Hook: Allow `rm -rf` Once Per Session

## Design summary

- **How the hook knows "this session":** every hook invocation receives a JSON payload on stdin that includes `session_id`. That is the session key — no environment tricks needed.
- **State-file naming:** one marker file per session, keyed by `session_id`, in a dedicated state directory under tmp:

  ```
  ${TMPDIR:-/tmp}/claude-hook-state/rm-rf-used.<session_id>
  ```

  Rationale:
  - `session_id` in the filename makes state naturally session-scoped — a new session gets a fresh file, and concurrent sessions never collide.
  - tmp is the right home for ephemeral per-session state (cleared on reboot; nothing to commit or gitignore). Do **not** put it in the repo or in `~/.claude/` — session state is not configuration.
  - A dedicated `claude-hook-state/` subdirectory keeps hook state greppable and lets you prune stale files in one place (the script prunes files older than 7 days on each run).
  - File **existence** is the flag; the file's contents (timestamp + first command) are only used to make the deny message informative.

- **Exact deny JSON** (stdout, exit 0 — this is the current PreToolUse contract):

  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "rm -rf already ran once this session (first: <ts> <cmd>). Only one rm -rf is allowed per session; delete targets individually or ask the user to run it manually."
    }
  }
  ```

  Notes on the output contract:
  - `permissionDecision` accepts `"allow"`, `"deny"`, or `"ask"`. For deny, `permissionDecisionReason` is shown to Claude so it can adjust instead of retrying.
  - The legacy top-level form `{"decision": "block", "reason": "..."}` still works but the `hookSpecificOutput` form is the current documented one — prefer it.
  - To **allow** (first use, or non-matching command), just `exit 0` with no output.
  - Alternative deny mechanism: `exit 2` with the reason on stderr. It works, but the JSON form is preferred here because it's explicit and lets you switch to `"ask"` later without restructuring.

## Complete hook script

`.claude/hooks/rm-rf-once-per-session.sh`:

```bash
#!/usr/bin/env bash
# PreToolUse hook: allow `rm -rf` once per Claude Code session, deny every
# subsequent attempt in the same session.
#
# Contract:
#   stdin  — JSON: { session_id, tool_name, tool_input: { command, ... }, ... }
#   stdout — empty to allow; hookSpecificOutput JSON to deny
#   exit 0 — decision (or no opinion); non-zero non-2 exits are ignored
set -euo pipefail

input=$(cat)

tool_name=$(jq -r '.tool_name // empty' <<<"$input")
[[ "$tool_name" == "Bash" ]] || exit 0

command=$(jq -r '.tool_input.command // empty' <<<"$input")
[[ -n "$command" ]] || exit 0

# Match rm with combined or split recursive+force flags, anywhere in the
# command line (handles `sudo rm -rf`, `foo && rm -fr x`, `rm -r -f x`).
rm_rf_re='(^|[;&|[:space:]])(sudo[[:space:]]+)?rm[[:space:]]+(-[[:alpha:]]*([rR][[:alpha:]]*f|f[[:alpha:]]*[rR])|-[rR][[:space:]]+-f|-f[[:space:]]+-[rR])([[:space:]]|$)'
if ! grep -qE "$rm_rf_re" <<<"$command"; then
  exit 0  # not an rm -rf — no opinion, let normal permission flow decide
fi

session_id=$(jq -r '.session_id // "unknown-session"' <<<"$input")
state_dir="${TMPDIR:-/tmp}/claude-hook-state"
mkdir -p "$state_dir"
state_file="$state_dir/rm-rf-used.$session_id"

# Prune state from long-dead sessions so the dir doesn't grow forever.
find "$state_dir" -name 'rm-rf-used.*' -mtime +7 -delete 2>/dev/null || true

if [[ ! -f "$state_file" ]]; then
  # First rm -rf this session: record it and stay silent (allow).
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$command" >"$state_file"
  exit 0
fi

# Second (or later) rm -rf this session: deny with context.
first_use=$(head -n 1 "$state_file")
jq -n --arg first "$first_use" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: ("rm -rf already ran once this session (first use: " + $first + "). Only one rm -rf is allowed per session — delete the specific paths with targeted rm/Bash commands, or ask the user to run this manually.")
  }
}'
exit 0
```

Implementation details worth calling out:

- **Deny JSON is built with `jq -n --arg`**, not a heredoc — the recorded first command can contain quotes/backslashes, and string-interpolating it into JSON by hand would produce invalid JSON (which Claude Code treats as a hook error, not a deny).
- **First use writes the marker *before* the command runs.** That means an rm -rf that the user subsequently rejects at the permission prompt still consumes the one allowance. That's the safe bias for a guard hook; if you want "only count executed commands," move the marker write to a PostToolUse hook and have this PreToolUse hook only read it.
- **Non-matching commands exit 0 with no output** — the hook expresses no opinion and normal permission rules apply.
- `chmod +x` the script after creating it.

## Registration in `.claude/settings.json`

Add under the existing `hooks` key (merge with any current `PreToolUse` array — don't clobber the other hooks already registered there):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/rm-rf-once-per-session.sh"
          }
        ]
      }
    ]
  }
}
```

Since this repo's `.claude/settings.json` is the global user settings file (symlinked from `~/.claude/settings.json`), `$CLAUDE_PROJECT_DIR` resolves per-project; if you want the hook active machine-wide regardless of project, use the absolute path `~/.dotfiles/.claude/hooks/rm-rf-once-per-session.sh` instead.

## Verifying

1. In a fresh session, ask Claude to run `rm -rf /tmp/some-scratch-dir` — it should pass through to the normal permission prompt (hook silent), and the state file `rm-rf-used.<session_id>` should appear.
2. Ask for a second `rm -rf` — the tool call should be denied with the "already ran once this session" reason.
3. Start a new session (`/clear` starts a new session id) — the first `rm -rf` is allowed again.
