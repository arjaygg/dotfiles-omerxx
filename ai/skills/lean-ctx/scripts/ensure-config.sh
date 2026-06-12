#!/usr/bin/env bash
# Ensure deliberate lean-ctx settings survive tool-driven config rewrites.
#
# ~/.lean-ctx/config.toml is rewritten by lean-ctx itself (setup, doctor --fix,
# install --repair, update), so the live file is NOT symlinked into dotfiles —
# a symlink would either keep the repo dirty or be silently replaced by an
# atomic rewrite. This script asserts the settings we care about instead.
# Idempotent — safe to run any time; install.sh calls it on every invocation.
#
# allow_auto_reroot = true:
#   The lean-ctx daemon is shared across all sessions via Unix socket. Without
#   auto-reroot it stays pinned to whichever project directory it was started
#   from, and every other session (main repo vs .trees/ worktrees) resolves
#   the wrong project root. Incident 2026-06-12: MCP LeanCtx rooted at a stale
#   worktree; agents fell back to raw sed edits.
set -euo pipefail

CONFIG="${LEAN_CTX_DATA_DIR:-$HOME/.lean-ctx}/config.toml"

if [[ ! -f "$CONFIG" ]]; then
    echo "lean-ctx: config not found at $CONFIG — run 'lean-ctx setup' first; nothing to ensure." >&2
    exit 0
fi

if grep -qE '^allow_auto_reroot[[:space:]]*=[[:space:]]*true[[:space:]]*$' "$CONFIG"; then
    exit 0
fi

# Flip an existing top-level key in place, or insert it before the first
# [section] header so it stays in the top-level TOML table.
tmp="$(mktemp "${CONFIG}.XXXXXX")"
awk '
    !done && /^allow_auto_reroot[[:space:]]*=/ { print "allow_auto_reroot = true"; done=1; next }
    !done && /^\[/                             { print "allow_auto_reroot = true"; print ""; done=1 }
                                               { print }
    END { if (!done) print "allow_auto_reroot = true" }
' "$CONFIG" > "$tmp"
chmod 644 "$tmp"
mv "$tmp" "$CONFIG"
echo "lean-ctx: set allow_auto_reroot = true in $CONFIG"

# A running daemon keeps the old setting until restarted.
if command -v lean-ctx >/dev/null 2>&1 && lean-ctx daemon status 2>/dev/null | grep -q running; then
    lean-ctx restart >/dev/null 2>&1 || true
    echo "lean-ctx: daemon restarted to apply config"
fi
