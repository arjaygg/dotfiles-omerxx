#!/usr/bin/env bash
# SessionStart hook: detect a severed ~/.claude/settings.json symlink.
#
# Claude Code may replace a symlink with a regular file when it persists
# in-session settings changes. This hook deliberately reports that condition
# without adopting runtime content into tracked source or changing the live
# file. Reviewers can then decide whether to migrate the runtime file manually.
#
# Always exits 0: this is proposal-only drift detection, not a session blocker.
set -euo pipefail
trap 'exit 0' ERR

LIVE="$HOME/.claude/settings.json"
SRC="$HOME/.dotfiles/.claude/settings.json"

[ -L "$LIVE" ] && exit 0
[ -f "$LIVE" ] || exit 0
[ -f "$SRC" ] || exit 0

warn() {
    python3 - "$1" <<'PYEOF'
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": sys.argv[1]}}))
PYEOF
    exit 0
}

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$LIVE" 2>/dev/null; then
    warn "settings-symlink-guard: severed ~/.claude/settings.json is invalid JSON; no source update or relink performed."
fi

warn "settings-symlink-guard: ~/.claude/settings.json is a regular file instead of a symlink; not auto-syncing or relinking. Review the runtime/source drift manually before migration."
