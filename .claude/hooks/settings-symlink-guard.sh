#!/usr/bin/env bash
# SessionStart hook: self-heal the ~/.claude/settings.json symlink.
#
# Claude Code persists in-session settings changes (/model, plugin installs,
# permission prompts) with an atomic temp-file+rename write. A rename replaces
# a symlink with a regular file, severing the link to the dotfiles copy — after
# which dotfiles edits silently stop taking effect (observed 2026-07-06:
# advisorModel change never applied). lean-ctx hook auto-install rewrites the
# file the same way.
#
# Heal strategy: the severed file is always "dotfiles content at sever time +
# CC's delta", so fold it back into dotfiles and restore the symlink. Refuse
# only when dotfiles was edited AFTER the sever (true divergence -> warn, human
# merges). Advisory sibling: config-integrity.sh (ConfigChange, detect-only).
#
# Always exits 0 -- never blocks the session.
set -euo pipefail
trap 'exit 0' ERR

LIVE="$HOME/.claude/settings.json"
SRC="$HOME/.dotfiles/.claude/settings.json"

[ -L "$LIVE" ] && exit 0            # symlink intact -- nothing to do
[ -f "$LIVE" ] || exit 0            # nothing there -- leave to dotfiles install
[ -f "$SRC" ] || exit 0             # no dotfiles copy -- nothing to link to

warn() {
    python3 - "$1" <<'PYEOF'
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": sys.argv[1]}}))
PYEOF
    exit 0
}

# Regular file's birth time ~= when the symlink was severed (macOS %B; Linux %W)
live_birth=$(stat -f %B "$LIVE" 2>/dev/null || stat -c %W "$LIVE" 2>/dev/null || echo 0)
src_mtime=$(stat -f %m "$SRC" 2>/dev/null || stat -c %Y "$SRC" 2>/dev/null || echo 0)

if [ "$live_birth" -gt 0 ] && [ "$src_mtime" -gt "$live_birth" ]; then
    warn "settings-symlink-guard: ~/.claude/settings.json symlink is severed AND ~/.dotfiles/.claude/settings.json was edited after the split — both sides changed. Not auto-healing; merge manually, then: ln -sf ~/.dotfiles/.claude/settings.json ~/.claude/settings.json"
fi

# Never adopt a corrupt file into dotfiles
if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$LIVE" 2>/dev/null; then
    warn "settings-symlink-guard: severed ~/.claude/settings.json is invalid JSON — not syncing to dotfiles."
fi

cp "$LIVE" "$SRC"
ln -sf "$SRC" "$LIVE"

warn "settings-symlink-guard: healed severed settings.json symlink — in-session changes folded into ~/.dotfiles/.claude/settings.json (uncommitted; commit when convenient)."
