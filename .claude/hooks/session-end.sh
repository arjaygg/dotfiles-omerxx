#!/usr/bin/env bash
# Stop hook: write plans/session-handoff.md for the next session
# Fires when Claude finishes a turn (approximates session end)

set -euo pipefail

CWD=$(pwd)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
HANDOFF="$CWD/plans/session-handoff.md"

# Only write if plans/ directory exists (opt-in per project)
[[ -d "$CWD/plans" ]] || exit 0

# Read artifact files
ACTIVE_CTX=""
[[ -f "$CWD/plans/active-context.md" ]] && ACTIVE_CTX=$(cat "$CWD/plans/active-context.md")

PROGRESS=""
[[ -f "$CWD/plans/progress.md" ]] && PROGRESS=$(cat "$CWD/plans/progress.md")

# Recent git commit
RECENT_COMMIT=$(git -C "$CWD" log -1 --oneline 2>/dev/null || echo "")
GIT_BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null || echo "")
GIT_STATE=$(git -C "$CWD" status --short 2>/dev/null | head -5 | tr '\n' '; ' | sed 's/; $//' || true)

# Seed skeleton files if ALL THREE artifact files are absent (so next session sees "stale" not "missing")
if [[ ! -f "$CWD/plans/active-context.md" ]] && \
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

# Skip writing handoff if nothing meaningful to record
if [[ -z "$ACTIVE_CTX" ]] && [[ -z "$PROGRESS" ]]; then
    exit 0
fi

python3 - "$TIMESTAMP" "$GIT_BRANCH" "$GIT_STATE" "$RECENT_COMMIT" \
    "$ACTIVE_CTX" "$PROGRESS" "$HANDOFF" <<'PYEOF'
import sys

(timestamp, branch, git_state, recent_commit,
 active_ctx, progress, handoff_path) = sys.argv[1:8]

lines = [
    f'# Session Handoff — {timestamp}',
    '',
    f'**Branch:** {branch}' if branch else '',
    f'**Uncommitted:** {git_state}' if git_state else '',
    f'**Last commit:** {recent_commit}' if recent_commit else '',
]
lines = [l for l in lines if l is not None]

if active_ctx:
    lines.append('')
    lines.append('## Active Context')
    lines.append(active_ctx)

if progress:
    lines.append('')
    lines.append('## Task State')
    lines.append(progress)

lines.append('')
lines.append('---')
lines.append('*Written by session-end.sh hook. Delete when no longer relevant.*')

with open(handoff_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
PYEOF

exit 0
