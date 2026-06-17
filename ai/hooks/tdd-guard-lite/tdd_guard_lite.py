#!/usr/bin/env python3
"""
TDD Guard Lite — deterministic TDD enforcement for Claude Code.

No LLM required. Hybrid of:
  Option 1: test state machine (test.json + modification history)
  Option 4: AST structural diff (tree-sitter; TS/JS/Python/Go)

Flow:
  State machine ALLOW → exit 0
  State machine BLOCK → AST diff
    Pure refactor?   → exit 0 (override)
    New symbol?      → exit 1 (block with message)
"""
import json
import sys
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))

from lib.config import load_config
from lib.state_machine import check as sm_check
from lib import ast_diff


def _load_json(path: str):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Malformed input — fail open

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    config = load_config()

    # Always allow test file edits
    if config.is_test_file(file_path):
        sys.exit(0)

    # Only enforce on tracked source files
    if not config.is_source_file(file_path):
        sys.exit(0)

    test_data = _load_json(config.test_results_path)
    modifications = _load_json(config.modifications_path) or []

    # Step 1: State machine
    sm_result = sm_check(file_path, test_data, modifications, config)
    if sm_result.allowed:
        sys.exit(0)

    # Step 2: AST diff override — maybe it's a pure refactor despite all tests passing
    if config.ast_diff_enabled:
        proposed = ast_diff.reconstruct_proposed(tool_name, tool_input)
        if proposed is not None:
            diff_result = ast_diff.check(file_path, proposed, config)
            if diff_result.is_pure_refactor:
                sys.exit(0)
            # Enrich the block message with what symbols were added
            if diff_result.new_symbols:
                new_sym_list = ", ".join(sorted(diff_result.new_symbols))
                print(
                    f"{sm_result.message}\n"
                    f"  New symbols detected: {new_sym_list}",
                    file=sys.stderr,
                )
                sys.exit(1)

    print(sm_result.message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
