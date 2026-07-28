---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — agy-cursor-context-hardening

<intent-contract>
Audit and finish the AGY/Antigravity and Cursor portions of the shared large-file/context hardening already in progress. Work only in the listed files. The Coordinator must be able to verify supported pre-tool payload adapters, portable hooks/MCP commands, focused LeanCtx exposure, and no duplicate rewrites.
</intent-contract>

## Task

Review current feature-branch AGY and Cursor changes, correct payload/schema or portability defects, and leave unrelated Gemini/Windsurf behavior untouched.

## Files

- `.gemini/GEMINI.md`
- `.gemini/settings.json`
- `.gemini/mcp.json`
- `.gemini/config/mcp_config.json`
- `.gemini/hooks.json`
- `.gemini/hooks/context-file-gate.sh`
- `ai/config/gemini/settings.base.json`
- `ai/config/gemini/mcp.base.json`
- `.cursor/hooks.json`
- `.cursor/hooks/context-file-gate.sh`
- `.cursor/hooks/lean-ctx-redirect.sh`
- `.cursor/hooks/lean-ctx-redirect-native`
- `.cursor/hooks/lean-ctx-rewrite.sh`
- `.cursor/hooks/lean-ctx-rewrite-native`
- `.cursor/mcp.json`
- `ai/config/cursor/mcp.base.json`

## Acceptance

- AGY run-command and supported file-read payloads use the shared gate and emit AGY's `allow_tool` schema.
- Cursor shell/read hooks register the shared gate plus exactly one portable LeanCtx rewrite/redirect path and emit Cursor's permission schema.
- Owned files contain no supported-machine absolute home paths.
- pctx plus focused direct LeanCtx exposure is present; Headroom MCP is absent.
- JSON/shell syntax and applicable client fixture/config tests pass.

## Constraints

- You are not alone in the codebase; do not revert or overwrite other agents' edits.
- Do not edit shared classifier, shared combined tests, docs, plans outside this spec, Codex/Claude/Windsurf files, or spawn subagents.
- Do not commit.

## Spec Change Log

- 2026-07-29: Initial frozen scope.

## Review Triage Log

