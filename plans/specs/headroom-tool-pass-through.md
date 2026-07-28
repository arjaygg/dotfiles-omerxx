# Headroom Tool-Result Pass-Through — Frozen Specification

## Ownership

- `scripts/headroom_hardening.py`
- `scripts/test_headroom_hardening.py`
- `.claude/settings.json`
- `ai/config/claude/settings.base.json`
- `setup.sh`
- `zshrc/.zshrc`
- `nushell/env.nu`

## Task

Ensure Headroom 0.27.0 remains a provider-history optimizer and does not become a second compressor for file, search, or shell tool results.

1. Expand the canonical exclusion set to cover common native shell/file/search tool names used by Claude, Codex, Cursor, and AGY plus direct LeanCtx shell/call/glob names and all exposed pctx gateway functions.
2. Keep matching compatible with Headroom's case-insensitive exact-name behavior; do not rely on unsupported wildcards.
3. Synchronize every tracked environment copy with the canonical sorted set.
4. Keep provider-history compression enabled; do not disable the Headroom proxy or restore the Headroom MCP server.
5. Add tests that pin the required client/native and LeanCtx/pctx names and exact environment-copy parity.
6. Verify targeted unit/config tests, JSON parsing, shell syntax, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not edit client hooks/MCP configs, shared routing gate/benchmark, or policy prose.
- Do not spawn subagents.
- Do not commit.
