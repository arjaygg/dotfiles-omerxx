#!/usr/bin/env bash
# SessionStart: warn if a substantial session already ran in this directory recently.
# Helps prevent accidentally restarting work that's already in progress or was recently done.
#
# Configuration (hook-config.yaml):
#   duplicate-session-check: warn   # active (default)
#   duplicate-session-check: off    # disabled

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
_HOOK_NAME="duplicate-session-check"
_EXIT_CODE=$(hook_exit_code "$_HOOK_NAME" 2>/dev/null || echo 2)
[[ "$_EXIT_CODE" -eq 0 ]] && exit 0  # disabled

export _DUP_CWD="$(pwd)"
export _DUP_PROJECTS="${HOME}/.claude/projects"
export _DUP_HOURS=12    # look back this many hours
export _DUP_MSGS=30     # minimum messages to consider a session "substantial"

RESULT=$(python3 <<'PYEOF'
import json, os, glob
from datetime import datetime, timezone, timedelta

cwd = os.environ['_DUP_CWD']
projects_dir = os.environ['_DUP_PROJECTS']
lookback_h = int(os.environ['_DUP_HOURS'])
min_msgs = int(os.environ['_DUP_MSGS'])

cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_h)
recent = []

for idx in glob.glob(os.path.join(projects_dir, '*/sessions-index.json')):
    try:
        with open(idx) as f:
            data = json.load(f)
        entries = data.get('entries', []) if isinstance(data, dict) else data
        for e in entries:
            if not isinstance(e, dict):
                continue
            if e.get('projectPath') != cwd:
                continue
            if e.get('messageCount', 0) < min_msgs:
                continue
            if e.get('isSidechain'):
                continue
            try:
                created = datetime.fromisoformat(e['created'].replace('Z', '+00:00'))
                if created >= cutoff:
                    summary = (e.get('summary') or e.get('firstPrompt') or '')[:80]
                    recent.append({
                        'id': e['sessionId'][:8],
                        'ts': e['created'][:16].replace('T', ' '),
                        'msgs': e['messageCount'],
                        'summary': summary,
                    })
            except Exception:
                pass
    except Exception:
        pass

if recent:
    recent.sort(key=lambda x: x['ts'], reverse=True)
    print('FOUND')
    for s in recent[:3]:
        print(f"  [{s['ts']}] {s['id']}... ({s['msgs']} msgs) — {s['summary']}")
PYEOF
2>/dev/null || true)

if [[ "${RESULT%%$'\n'*}" == "FOUND" ]]; then
    echo "[DUPLICATE SESSION WARNING] Recent sessions found in this directory (last ${_DUP_HOURS}h):"
    echo "${RESULT#*$'\n'}"
    echo "  Use /session-picker to resume an existing session instead of starting fresh."
    hook_metric "$_HOOK_NAME" "SessionStart" "$_EXIT_CODE" 2>/dev/null || true
fi

exit 0
