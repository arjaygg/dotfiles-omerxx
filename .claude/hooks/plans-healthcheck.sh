#!/usr/bin/env bash
# UserPromptSubmit hook: warn Claude when session artifact files are missing or stale
# Silent when healthy; outputs a structured warning (becomes system-reminder) when action needed

set -euo pipefail

CWD=$(pwd)
TODAY=$(date '+%Y-%m-%d')

# Opt-in: only run if plans/ directory exists
[[ -d "$CWD/plans" ]] || exit 0

ARTIFACT_FILES=(
    "plans/active-context.md"
    "plans/decisions.md"
    "plans/progress.md"
)

MISSING=()
STALE=()

for rel in "${ARTIFACT_FILES[@]}"; do
    fp="$CWD/$rel"
    if [[ ! -f "$fp" ]]; then
        MISSING+=("$rel")
    else
        FILE_DATE=$(date -r "$fp" '+%Y-%m-%d' 2>/dev/null || echo "")
        if [[ "$FILE_DATE" != "$TODAY" ]]; then
            STALE+=("$rel")
        fi
    fi
done

HANDOFF_EXISTS=0
[[ -f "$CWD/plans/session-handoff.md" ]] && HANDOFF_EXISTS=1

# All healthy and no handoff → silent exit
if [[ ${#MISSING[@]} -eq 0 ]] && [[ ${#STALE[@]} -eq 0 ]] && [[ "$HANDOFF_EXISTS" -eq 0 ]]; then
    exit 0
fi

# Build and output warning
python3 - "${MISSING[*]:-}" "${STALE[*]:-}" "$HANDOFF_EXISTS" <<'PYEOF'
import sys

missing_str, stale_str, handoff_exists = sys.argv[1], sys.argv[2], sys.argv[3]
missing = [f for f in missing_str.split() if f]
stale = [f for f in stale_str.split() if f]
has_handoff = handoff_exists == "1"

lines = ["[PLANS HEALTH] Session artifact status:", ""]

if missing:
    lines.append("MISSING (must create before compaction):")
    for f in missing:
        lines.append(f"  - {f}")
    lines.append("Action: Create missing files now per CLAUDE.md instructions.")
    lines.append("  active-context.md — current focus/learnings, ≤30 lines")
    lines.append("  decisions.md      — append-only ADL log")
    lines.append("  progress.md       — task state in checkbox format")

if stale:
    if missing:
        lines.append("")
    lines.append("STALE (exist but not updated today):")
    for f in stale:
        lines.append(f"  - {f}")
    lines.append("Action: Update stale files to reflect current session state.")

if has_handoff:
    if missing or stale:
        lines.append("")
    lines.append("HANDOFF AVAILABLE: plans/session-handoff.md exists from a prior session.")
    lines.append("Action: Read plans/session-handoff.md to restore prior session context, then delete it.")

print("\n".join(lines))
PYEOF

exit 0
