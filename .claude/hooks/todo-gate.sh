#!/usr/bin/env bash
# Stop hook: block/warn if TodoWrite has incomplete items in the current transcript.
#
# Integrates with hook-config.yaml enforcement levels:
#   todo-gate: warn   → prints to stderr, allows stop (default, burn-in phase)
#   todo-gate: block  → returns {"decision":"block",...} to stdout, prevents stop
#   todo-gate: off    → exits immediately, no-op
#
# Guards:
#   - stop_hook_active: true  → skip (prevents infinite loop on repeated blocks)
#   - no transcript_path      → skip
#   - no TodoWrite in session  → skip (task didn't use todos — not our concern)
#   - all todos completed      → allow stop normally

set -euo pipefail

SCRIPT_NAME="todo-gate"
HOOK_CONFIG="$HOME/.dotfiles/.claude/hooks/hook-config.yaml"

# Read enforcement level
LEVEL=$(grep "^${SCRIPT_NAME}:" "$HOOK_CONFIG" 2>/dev/null | awk '{print $2}' || echo "warn")
[ "$LEVEL" = "off" ] && exit 0

# Parse Stop hook stdin payload
INPUT=$(cat)

# Guard: stop_hook_active prevents infinite loop
STOP_HOOK_ACTIVE=$(echo "$INPUT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d.get('stop_hook_active', False))" \
  2>/dev/null || echo "False")
[ "$STOP_HOOK_ACTIVE" = "True" ] && exit 0

# Get transcript path
TRANSCRIPT=$(echo "$INPUT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d.get('transcript_path', ''))" \
  2>/dev/null || echo "")
[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

# Parse transcript JSONL for the latest TodoWrite state
RESULT=$(python3 - "$TRANSCRIPT" <<'PYEOF'
import json, sys

transcript_path = sys.argv[1]
latest_todos = None

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        msg = entry.get('message', {})
        if msg.get('role') != 'assistant':
            continue
        for item in msg.get('content', []):
            if (isinstance(item, dict)
                    and item.get('type') == 'tool_use'
                    and item.get('name') == 'TodoWrite'):
                latest_todos = item.get('input', {}).get('todos', [])

# No TodoWrite found — nothing to gate on
if latest_todos is None:
    sys.exit(0)

incomplete = [t for t in latest_todos if t.get('status') != 'completed']

if not incomplete:
    sys.exit(0)

print(json.dumps({
    "count": len(incomplete),
    "items": [t.get('content', '(no content)') for t in incomplete[:5]],
    "has_more": len(incomplete) > 5
}))
PYEOF
)

[ -z "$RESULT" ] && exit 0

COUNT=$(echo "$RESULT" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "0")
[ "$COUNT" -eq 0 ] && exit 0

ITEMS=$(echo "$RESULT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for item in d['items']:
    print(f'  • {item}')
if d.get('has_more'):
    print('  • ...(and more)')
" 2>/dev/null || echo "")

REASON="$COUNT incomplete TodoWrite item(s) remain — do not stop until all are completed:
$ITEMS"

if [ "$LEVEL" = "block" ]; then
    python3 -c "
import json, sys
reason = sys.argv[1]
print(json.dumps({'decision': 'block', 'reason': reason}))
" "$REASON"
    exit 0
else
    # warn: print to stderr so user sees it, but allow stop
    echo "" >&2
    echo "TODO-GATE [warn]: $COUNT incomplete todo(s) remain:" >&2
    echo "$ITEMS" >&2
    echo "Upgrade to 'block' in hook-config.yaml when ready to enforce." >&2
    exit 0
fi
