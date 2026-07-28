# Claude/Codex Post-Tool Metrics — Frozen Specification

## Ownership

- `.claude/hooks/lean-ctx-observe.sh`
- `.codex/hooks/post-bash-observe.sh`
- `scripts/test_context_hook_adapters.py`

## Task

Feed supported Claude and Codex post-tool payloads into the shared context gate for privacy-safe returned-token/reference metrics.

1. Tee the already-buffered hook payload into `context-file-gate --event post_tool_use` with the correct client name.
2. Keep observation fail-open, silent, and non-mutating; preserve existing observer behavior and payload.
3. Resolve the gate portably relative to the tracked repository, with the existing override convention where useful.
4. Add hook tests proving a post payload creates metrics without storing contents, commands, or paths.
5. Verify targeted unit tests, shell syntax, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not edit hook registrations, client settings/config, the shared gate, or other clients.
- Do not spawn subagents.
- Do not commit.
