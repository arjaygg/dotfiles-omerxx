# AGY/Cursor Post-Tool Metrics — Frozen Specification

## Ownership

- `.gemini/hooks/context-observe.sh`
- `.gemini/hooks.json`
- `.cursor/hooks/context-observe.sh`
- `.cursor/hooks.json`
- `scripts/test_context_hook_adapters.py`

## Task

Register thin fail-open post-tool observers for AGY/Antigravity and Cursor that feed payload metadata into the shared context gate.

1. Resolve the shared gate portably relative to the tracked repository.
2. Call it with the correct client and `--event post_tool_use`; never mutate tool output or block execution.
3. Register exactly one supported post-tool observer per client while preserving existing post hooks.
4. Add hook tests proving post payloads create privacy-safe returned-token/reference metrics and preserve unrelated behavior.
5. Verify targeted unit tests, shell syntax, JSON parsing, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not edit pre-tool adapters, settings/MCP configs, the shared gate, or Claude/Codex files.
- Coordinate edits to `scripts/test_context_hook_adapters.py`; do not overwrite concurrent additions.
- Do not spawn subagents.
- Do not commit.
