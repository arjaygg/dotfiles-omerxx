#!/usr/bin/env bash
# _session-hub-done.sh — Mark a session as done
#
# Writes "status: complete" to plans/session-handoff.md of the given cwd.
# Called by session-hub.sh on Ctrl-D. The fzf window stays open (caller uses reload).
#
# Args: $1 = cwd of the session to mark done

set -euo pipefail

TARGET_CWD="${1:-}"

if [[ -z "$TARGET_CWD" || ! -d "$TARGET_CWD" ]]; then
    # No-op for header lines or invalid paths
    exit 0
fi

HANDOFF_FILE="$TARGET_CWD/plans/session-handoff.md"
NOW=$(date '+%Y-%m-%d %H:%M')

if [[ -f "$HANDOFF_FILE" ]]; then
    # Update existing status line in place
    if grep -q '^status:' "$HANDOFF_FILE"; then
        # Replace status line
        local_tmp=$(mktemp)
        sed "s/^status:.*$/status: complete/" "$HANDOFF_FILE" > "$local_tmp"
        # Append done timestamp if not already there
        if ! grep -q "^marked_done:" "$local_tmp"; then
            echo "marked_done: $NOW" >> "$local_tmp"
        fi
        mv "$local_tmp" "$HANDOFF_FILE"
    else
        # Prepend status line
        local_tmp=$(mktemp)
        { echo "status: complete"; echo "marked_done: $NOW"; echo ""; cat "$HANDOFF_FILE"; } > "$local_tmp"
        mv "$local_tmp" "$HANDOFF_FILE"
    fi
else
    # Create minimal handoff file
    mkdir -p "$(dirname "$HANDOFF_FILE")"
    BRANCH=$(git -C "$TARGET_CWD" branch --show-current 2>/dev/null || echo "unknown")
    cat > "$HANDOFF_FILE" << EOF
# Session Handoff — ${NOW}
status: complete
marked_done: ${NOW}

**Branch:** ${BRANCH}
**Project:** $(basename "$TARGET_CWD")

*Marked done via session-hub.sh*
EOF
fi
