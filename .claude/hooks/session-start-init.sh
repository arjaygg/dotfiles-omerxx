#!/bin/bash
# Session Start Initialization — Initialize turn counter
# Fires on SessionStart hook event

# Initialize turn counter for this session
COUNTER_FILE="/tmp/.claude-turn-count-${UID}"
echo "0" > "$COUNTER_FILE" 2>/dev/null || true

exit 0
