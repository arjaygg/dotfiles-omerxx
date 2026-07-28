---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — codex-context-hardening

<intent-contract>
Audit and finish the Codex portion of the shared large-file/context hardening already in progress. Work only in the listed Codex-owned files. The Coordinator must be able to verify fail-open payload parsing, warn/deny enforcement, portable pctx/LeanCtx launchers, focused direct tools, and persistent Headroom provider configuration without a Headroom MCP server.
</intent-contract>

## Task

Review the current feature-branch changes, correct defects, and complete Codex integration while preserving the shared classifier contract.

## Files

- `.codex/AGENTS.md`
- `.codex/config.toml`
- `.codex/hooks.json`
- `.codex/hooks/pre-bash-guard.sh`
- `ai/config/codex/config.base.toml`
- `scripts/test_codex_pctx_startup.py`

## Acceptance

- Common native full-read shell/direct-tool bypasses warn or deny according to the shared gate; parse failures and unrelated commands pass.
- Runtime and template pctx/LeanCtx commands work for both supported home paths with no baked username.
- Direct LeanCtx exposure covers compose/read/search/tree/expand while pctx remains the deferred gateway.
- Codex retains the Headroom provider proxy and has no `mcp_servers.headroom`.
- TOML parses and applicable startup/hook/config tests pass.

## Constraints

- You are not alone in the codebase; do not revert or overwrite other agents' edits.
- Do not edit shared classifier, shared tests beyond the listed startup test, docs, plans outside this spec, or other client files.
- Do not spawn subagents.
- Do not commit.

## Spec Change Log

- 2026-07-29: Initial frozen scope.

## Review Triage Log

