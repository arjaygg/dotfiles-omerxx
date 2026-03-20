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

artifact_status() {
    local cwd
    cwd=$(pwd)
    local today
    today=$(date '+%Y-%m-%d')
    [[ -d "$cwd/plans" ]] || { echo ""; return; }
    local issues=()
    for rel in "active-context.md" "decisions.md" "progress.md"; do
        local fp="$cwd/plans/$rel"
        if [[ ! -f "$fp" ]]; then
            issues+=("$rel")
        else
            local fdate
            fdate=$(date -r "$fp" '+%Y-%m-%d' 2>/dev/null || echo "")
            [[ "$fdate" != "$today" ]] && issues+=("$rel")
        fi
    done
    local IFS=','
    echo "${issues[*]:-}"
}

ARTIFACT_ISSUES=$(artifact_status)

if [[ -n "$CONTEXT_REMAINING" ]]; then
    if [[ "$CONTEXT_REMAINING" -le 5 ]]; then
        if [[ -n "$ARTIFACT_ISSUES" ]]; then
            notify "Claude Code - ARTIFACT RISK" "${CONTEXT_REMAINING}% left + missing: ${ARTIFACT_ISSUES}. Update NOW then /compact."
        else
            notify "Claude Code - CRITICAL" "Only ${CONTEXT_REMAINING}% context remaining! Save work and compact NOW."
        fi
    elif [[ "$CONTEXT_REMAINING" -le 15 ]]; then
        if [[ -n "$ARTIFACT_ISSUES" ]]; then
            notify "Claude Code - ARTIFACT RISK" "${CONTEXT_REMAINING}% left. Missing: ${ARTIFACT_ISSUES}. Update before compacting!"
        else
            notify "Claude Code - Low Context" "${CONTEXT_REMAINING}% context remaining. Consider /compact soon."
        fi
    elif [[ "$CONTEXT_REMAINING" -le 30 ]]; then
        if [[ -n "$ARTIFACT_ISSUES" ]]; then
            notify "Claude Code - ARTIFACT RISK" "${CONTEXT_REMAINING}% left. Missing: ${ARTIFACT_ISSUES}."
        else
            notify "Claude Code - Context Warning" "${CONTEXT_REMAINING}% context remaining."
        fi
    fi
fi

exit 0
