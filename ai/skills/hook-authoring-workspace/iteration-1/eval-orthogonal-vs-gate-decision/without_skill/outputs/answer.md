# git status throttle hook — separate file, not pre-tool-gate-v2.sh

## Recommendation: its own file

Put this in a new standalone hook (`.claude/hooks/git-status-throttle.sh`), not inside `pre-tool-gate-v2.sh`. Reasons:

1. **Different concern class.** The gate is a consolidated *safety/policy* enforcer (git safety, PR conventions, plan scope, session-init gating) with `set -euo pipefail`, metrics finalization via EXIT trap, and `[HARD-BLOCK — DO NOT RETRY]` semantics meaning "never retry this command." A throttle is the opposite: the same command becomes *valid again in 10 seconds*. Mixing "retry never" and "retry soon" messaging inside one script muddies the gate's contract with the model (and with `advisor-escalate.py`'s recurrence tracker, which keys off that marker).
2. **The gate's own precedent.** Its header explicitly documents leaving hooks standalone when folding is risky or the concern is orthogonal (`rtk-rewrite.sh`, `lean-ctx hook rewrite` were "conservatively left separate"). A stateful timestamp throttle is orthogonal noise-reduction, not policy.
3. **Independent lifecycle.** As a separate file you can disable/tune/delete the throttle by removing one settings entry, without touching (and risking) a load-bearing safety script that already replaced nine hooks.
4. **Cost is negligible.** The only argument for folding is saving one process spawn + jq parse (~3ms). settings.json already stacks four PreToolUse entries; one more is idiomatic here.

## The hook script

`/Users/axos-agallentes/.dotfiles/.claude/hooks/git-status-throttle.sh` (then `chmod +x` it):

```bash
#!/usr/bin/env bash
# git-status-throttle.sh — PreToolUse (Bash) hook
# Blocks re-running `git status` more than once per 10s per session, to cut
# transcript noise. NOT a safety gate — kept out of pre-tool-gate-v2.sh
# deliberately (see that file's header for the fold/no-fold precedent).
#
# Blocking semantics (same contract as pre-tool-gate-v2.sh): a block requires
# emitting {"permissionDecision":"deny"} JSON on stdout with exit 0. A plain
# non-zero exit is a NON-BLOCKING error — the tool runs anyway. Every
# pass-through path must exit 0 with no stdout output.

set -uo pipefail

THROTTLE_SECS=10

INPUT=$(cat)
command -v jq >/dev/null 2>&1 || exit 0

TOOL_NAME=$(jq -r '.tool_name // ""' <<<"$INPUT" 2>/dev/null) || exit 0
[[ "$TOOL_NAME" == "Bash" ]] || exit 0

CMD=$(jq -r '.tool_input.command // ""' <<<"$INPUT" 2>/dev/null) || exit 0
SESSION_ID=$(jq -r '.session_id // "default"' <<<"$INPUT" 2>/dev/null) || SESSION_ID=default
SESSION_ID=${SESSION_ID//[^a-zA-Z0-9_-]/}

# Compound commands / pipelines do more than re-poll status — leave them alone.
case "$CMD" in
    *'&&'*|*'||'*|*'|'*|*';'*) exit 0 ;;
esac

# Match a bare `git status` invocation: optional rtk prefix (rtk-rewrite.sh
# rewrites `git status` -> `rtk git status`; hook ordering means we may see
# either form), optional `-C <dir>`, optional trailing flags (-sb, --porcelain).
if ! [[ "$CMD" =~ ^[[:space:]]*(rtk[[:space:]]+)?git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?status([[:space:]]|$) ]]; then
    exit 0
fi

STAMP_FILE="/tmp/.claude-git-status-throttle-$(id -u)-${SESSION_ID:-default}"
NOW=$(date +%s)
LAST=$(cat "$STAMP_FILE" 2>/dev/null || echo 0)
[[ "$LAST" =~ ^[0-9]+$ ]] || LAST=0
ELAPSED=$(( NOW - LAST ))

if (( ELAPSED < THROTTLE_SECS )); then
    # Intentionally NOT the "[HARD-BLOCK — DO NOT RETRY]" marker: that marker
    # means the command is permanently invalid; this one is fine in a moment.
    REASON="THROTTLED (retry ok after ${THROTTLE_SECS}s): git status ran ${ELAPSED}s ago in this session. Reuse the previous output — nothing has changed the working tree since unless you changed it yourself."
    printf '%s\n' "$REASON" >&2
    jq -cn --arg r "$REASON" \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
    exit 0
fi

printf '%s' "$NOW" > "$STAMP_FILE" 2>/dev/null || true
exit 0
```

Design notes:

- **State** is a per-uid, per-session epoch-seconds stamp file in `/tmp`, matching the gate's existing `/tmp/.claude-last-block-$(id -u)-<session>` pattern. Session-scoped means two concurrent sessions don't throttle each other.
- **The deny reason is fed back to the model**, telling it to reuse prior output — that, not the block itself, is what actually cuts the noise.
- **The stamp is written at pre-tool time**, so a `git status` that subsequently fails still starts the window. Acceptable for a noise throttle; doing better would need a PostToolUse companion, which isn't worth it.
- `set -u` but not `-e`: in a hook where non-zero exit is a *non-blocking* red error banner, `-e` on an incidental failure just produces UI noise without blocking anything. Every path exits 0 explicitly.

## Wiring into .claude/settings.json

Add one entry to the existing `hooks.PreToolUse` array. Place it **before** the `rtk-rewrite.sh` entry (the regex tolerates either ordering since it matches the `rtk `-prefixed form too, but seeing the pre-rewrite command is the cleaner contract):

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "bash",
      "args": [
        "/Users/axos-agallentes/.dotfiles/.claude/hooks/git-status-throttle.sh"
      ]
    }
  ]
}
```

i.e. the `PreToolUse` array becomes: `pre-tool-gate-v2.sh` entry → `graphify-redirect.sh` entry → **this new entry** → `rtk-rewrite.sh` entry → `lean-ctx hook redirect` entry → `scratchpad-reread-guard.sh` entry.

Caveats:

- Edit the **tracked repo file** `~/.dotfiles/.claude/settings.json` (it's the source; `~/.claude/settings.json` is the symlink), and note it currently has uncommitted modifications — don't clobber them. Per repo policy, land this via a stack branch, not directly on `main`.
- Since this is the **global** settings file, the throttle applies to every project on the machine — which matches the intent, but be aware it's not dotfiles-scoped.
- Claude Code snapshots hook config at session start, so the new hook takes effect in the **next** session (or after `/hooks` review/reload), not the one where you edit settings.
