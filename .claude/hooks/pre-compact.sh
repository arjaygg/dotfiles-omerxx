#!/usr/bin/env bash
# PreCompact hook: inject session state summary before compaction
# so the compacted context retains orientation

set -euo pipefail

CWD=$(pwd)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# Find active plan file (most recently modified in plans/)
PLAN_FILE=""
PLAN_SUMMARY=""
if [[ -d "$CWD/plans" ]]; then
    PLAN_FILE=$(ls -t "$CWD/plans/"*.md 2>/dev/null | head -1 || echo "")
fi
if [[ -n "$PLAN_FILE" ]]; then
    PLAN_SUMMARY="Active plan: $PLAN_FILE"
    # Extract first heading as plan title
    PLAN_TITLE=$(grep -m1 '^#' "$PLAN_FILE" 2>/dev/null | sed 's/^#* *//' || echo "")
    [[ -n "$PLAN_TITLE" ]] && PLAN_SUMMARY="Active plan: $PLAN_FILE — $PLAN_TITLE"
fi

# Find recently modified files (last 30 min, excluding .git)
RECENT_FILES=$(find "$CWD" -newer "$CWD/.git/index" -type f \
    ! -path '*/.git/*' \
    ! -path '*/node_modules/*' \
    ! -path '*/target/*' \
    2>/dev/null | head -20 | sed "s|$CWD/||" | tr '\n' ', ' | sed 's/,$//')

# Emit state summary as a message Claude Code will inject before compaction
python3 -c "
import sys, json

plan = sys.argv[1]
recent = sys.argv[2]
timestamp = sys.argv[3]
cwd = sys.argv[4]

lines = [
    f'[PRE-COMPACT CHECKPOINT — {timestamp}]',
    f'Working directory: {cwd}',
]
if plan:
    lines.append(plan)
if recent:
    lines.append(f'Recently edited files: {recent}')
lines.append('Context is about to be compacted. Resume from this state after compaction.')

print(json.dumps({'type': 'text', 'text': chr(10).join(lines)}))
" "$PLAN_SUMMARY" "$RECENT_FILES" "$TIMESTAMP" "$CWD"

exit 0
