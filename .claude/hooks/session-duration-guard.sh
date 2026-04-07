#!/bin/bash
# Session Duration Guard — Prevents marathon sessions
# Fires on UserPromptSubmit hook
# Increments turn counter, warns at thresholds, blocks at 500 turns

# CRITICAL: Drain stdin — all UserPromptSubmit hooks must consume stdin to prevent buffering issues
cat > /dev/null

# Turn counter file (initialized by session-start-init.sh at SessionStart)
COUNTER_FILE="/tmp/.claude-turn-count-${UID}"

# Determine enforcement level from hook-config
CONFIG_FILE="${HOME}/.dotfiles/.claude/hooks/hook-config.yaml"
ENFORCEMENT="block"  # default
if [ -f "$CONFIG_FILE" ]; then
    ENFORCEMENT=$(grep "^session-duration-guard:" "$CONFIG_FILE" 2>/dev/null | sed 's/.*:[[:space:]]*//; s/[[:space:]]*#.*//' | xargs)
    [ -z "$ENFORCEMENT" ] && ENFORCEMENT="block"
fi

# Only proceed if enforcement is enabled
if [ "$ENFORCEMENT" = "off" ]; then
    exit 0
fi

# Read current count or initialize to 0
CURRENT_COUNT=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")
NEW_COUNT=$((CURRENT_COUNT + 1))

# Write new count
echo "$NEW_COUNT" > "$COUNTER_FILE" 2>/dev/null || true

# Decision logic
if [ "$NEW_COUNT" -ge 500 ]; then
    # HARD BLOCK at 500 turns
    {
        echo ""
        echo "🛑 SESSION DURATION LIMIT REACHED"
        echo ""
        echo "This session has reached 500 turns. To maintain context quality and prevent"
        echo "compaction fatigue, you must checkpoint your work and start a new session."
        echo ""
        echo "Next steps:"
        echo "  1. Run /session-done to save session artifacts (active-context.md, decisions.md)"
        echo "  2. Review and commit any work: git add . && git commit -m 'checkpoint: ...'"
        echo "  3. Start a fresh session: /session-next"
        echo ""
        echo "Current turn: $NEW_COUNT"
        echo ""
    } >&2
    exit 1
elif [ "$NEW_COUNT" -ge 400 ]; then
    # WARNING at 400 (every turn from here)
    echo "[session-guard] 🟠 WARNING: $NEW_COUNT turns — session getting long. Plan to checkpoint soon." >&2
elif [ "$NEW_COUNT" -ge 300 ]; then
    # INFO at 300, then every 25 turns
    if [ $((NEW_COUNT % 25)) -eq 0 ]; then
        echo "[session-guard] ℹ️  $NEW_COUNT turns — consider /compact or planning a checkpoint." >&2
    fi
elif [ "$NEW_COUNT" -ge 100 ]; then
    # INFO at 100, then every 50 turns
    if [ $((NEW_COUNT % 50)) -eq 0 ]; then
        echo "[session-guard] ℹ️  $NEW_COUNT turns in this session." >&2
    fi
fi

exit 0
