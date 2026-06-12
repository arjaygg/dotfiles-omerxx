#!/bin/bash
# Session Start Initialization — Initialize turn counter
# Fires on SessionStart hook event

# Initialize turn counter for this session
COUNTER_FILE="/tmp/.claude-turn-count-${UID}"
echo "0" > "$COUNTER_FILE" 2>/dev/null || true

# Superpowers 1% Rule Injection
echo "SYSTEM PROTOCOL (SUPERPOWERS): Before taking any action, you must assess if a generalized skill applies (e.g., stark for planning, fury for testing, strange for debugging, cap for orchestration). If there is even a 1% chance it applies, you must invoke it."

exit 0
