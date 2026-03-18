#!/usr/bin/env bash
# Notification hook: fire desktop alerts at context usage thresholds
# Claude Code passes notification payload as JSON on stdin

set -euo pipefail

INPUT=$(cat)

# Extract context usage percentage remaining from notification
CONTEXT_REMAINING=$(echo "$INPUT" | python3 -c "
import sys, json, re
try:
    d = json.load(sys.stdin)
    message = str(d.get('message', '') or d.get('title', '') or d.get('body', '') or json.dumps(d))
    # Look for patterns like '15% remaining', 'context: 85% used', etc.
    m = re.search(r'(\d+)%\s*remaining', message, re.IGNORECASE)
    if m:
        print(m.group(1))
        sys.exit(0)
    m = re.search(r'context.*?(\d+)%\s*used', message, re.IGNORECASE)
    if m:
        print(100 - int(m.group(1)))
        sys.exit(0)
    print('')
except:
    print('')
" 2>/dev/null || echo "")

notify() {
    local title="$1"
    local message="$2"
    osascript -e "display notification \"$message\" with title \"$title\" sound name \"Glass\"" 2>/dev/null || true
}

if [[ -n "$CONTEXT_REMAINING" ]]; then
    if [[ "$CONTEXT_REMAINING" -le 5 ]]; then
        notify "Claude Code - CRITICAL" "Only ${CONTEXT_REMAINING}% context remaining! Save work and compact NOW."
    elif [[ "$CONTEXT_REMAINING" -le 15 ]]; then
        notify "Claude Code - Low Context" "${CONTEXT_REMAINING}% context remaining. Consider /compact soon."
    elif [[ "$CONTEXT_REMAINING" -le 30 ]]; then
        notify "Claude Code - Context Warning" "${CONTEXT_REMAINING}% context remaining."
    fi
fi

exit 0
