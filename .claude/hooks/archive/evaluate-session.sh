#!/usr/bin/env bash
INPUT=$(cat)
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")
[[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]] && exit 0

MSG_COUNT=$(python3 -c "
import json, sys
count = 0
with open(sys.argv[1]) as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user' or obj.get('role') == 'user':
                count += 1
        except: pass
print(count)
" "$TRANSCRIPT" 2>/dev/null || echo "0")

if (( MSG_COUNT >= 10 )); then
    echo "[ContinuousLearning] Session has $MSG_COUNT messages - evaluate for extractable patterns." >&2
    echo "[ContinuousLearning] Save learned patterns to: $HOME/.claude/homunculus/instincts/personal/global.json" >&2
    mkdir -p "$HOME/.claude/homunculus/instincts/personal"
fi
exit 0
