#!/usr/bin/env bash
# TDD Guard Lite — PreToolUse hook for Claude Code
# Reads hook JSON from stdin; exits 1 to block, 0 to allow.
# No LLM required: uses test state machine + AST structural diff.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HOOK_DIR/tdd_guard_lite.py"
