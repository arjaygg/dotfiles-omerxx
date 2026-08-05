#!/usr/bin/env bash
# Stop hook: session cleanup
# Fires when Claude finishes a turn.

set -euo pipefail
trap 'echo "HOOK CRASH (session-end.sh line $LINENO): $BASH_COMMAND" >&2; exit 0' ERR

# Restore tmux window name on session end
"$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh" activity-stop >/dev/null 2>&1 || true

CWD=$(pwd)

# Seed skeleton files if plans/ exists but ALL THREE artifact files are absent
if [[ -d "$CWD/plans" ]] && \
   [[ ! -f "$CWD/plans/active-context.md" ]] && \
   [[ ! -f "$CWD/plans/decisions.md" ]] && \
   [[ ! -f "$CWD/plans/progress.md" ]]; then
    python3 - "$CWD" <<'SKELEOF' || true
import sys, os
base = sys.argv[1] + "/plans"
skeletons = {
    "active-context.md": "# Active Context\n<!-- SKELETON — Claude: update with current session focus (≤30 lines per CLAUDE.md) -->\n",
    "decisions.md":      "# Decisions\n<!-- SKELETON — Claude: append ADL entries as architectural decisions are made -->\n",
    "progress.md":       "# Progress\n<!-- SKELETON — Claude: update task state using checkbox format per CLAUDE.md -->\n",
}
for fname, content in skeletons.items():
    path = os.path.join(base, fname)
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
SKELEOF
fi

# Flush hook metrics to SQLite
"${BASH_SOURCE[0]%/*}/hook-metrics.sh" flush >/dev/null 2>&1 || true

# Clean up session-duration-guard counter
rm -f "/tmp/.claude-turn-count-${UID}" 2>/dev/null || true

exit 0
