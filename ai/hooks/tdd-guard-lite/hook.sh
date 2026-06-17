#!/usr/bin/env bash
# TDD Guard Lite — PreToolUse hook for Claude Code
# Reads hook JSON from stdin; exits 1 to block, 0 to allow.
# No LLM required: uses test state machine + AST structural diff.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Use the bundled venv (Python 3.12 + tree-sitter-languages) when available,
# falling back to system python3 (state-machine-only mode).
VENV_PY="$HOOK_DIR/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" "$HOOK_DIR/tdd_guard_lite.py"
else
    exec python3 "$HOOK_DIR/tdd_guard_lite.py"
fi
