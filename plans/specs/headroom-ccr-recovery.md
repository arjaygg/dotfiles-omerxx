# Headroom CCR Recovery — Frozen Specification

## Ownership

- `scripts/headroom_hardening.py`
- `scripts/test_headroom_hardening.py`
- `ai/rules/context-and-compaction.md`

## Task

Provide a safe local recovery path for provider-history CCR references after removing the Headroom MCP server from normal client sessions.

1. Add a standard-library CLI subcommand that retrieves an exact `original_content` value by hash from the local CCR SQLite database.
2. Fail clearly and without partial output for missing, malformed, nested, or self-referential entries.
3. Preserve exact bytes/text, including final-newline behavior, and use parameterized SQL.
4. Add one concise shared-policy sentence showing the portable recovery command; do not duplicate it in client adapters.
5. Add tests for exact recovery and rejected invalid/missing entries.
6. Verify targeted unit tests, Python compilation, instruction budgets, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not restore or register a Headroom MCP server.
- Do not edit client configs, setup, shared gate, or benchmark files.
- Do not spawn subagents.
- Do not commit.
