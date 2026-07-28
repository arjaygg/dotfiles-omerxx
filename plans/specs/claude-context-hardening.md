---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — claude-context-hardening

<intent-contract>
Audit and finish the Claude Code portion of the shared large-file/context hardening already in progress. Work only in the listed Claude-owned files. The Coordinator must be able to verify one shared gate, one LeanCtx rewrite/redirect owner, one observe hook per event, portable paths, Headroom provider-only settings, and passing existing hook/config tests.
</intent-contract>

## Task

Review the current feature-branch changes, correct defects, and complete Claude Code integration without redesigning the shared classifier.

## Files

- `.claude/CLAUDE.md`
- `.claude/LEAN_CTX.md`
- `.claude/hooks/pre-tool-gate-v2.sh`
- `.claude/hooks/lean-ctx-observe.sh`
- `.claude/hooks/lean-ctx-redirect.sh`
- `.claude/hooks/lean-ctx-redirect-native`
- `.claude/hooks/lean-ctx-rewrite.sh`
- `.claude/hooks/lean-ctx-rewrite-native`
- `.claude/settings.json`
- `ai/config/claude/settings.base.json`
- `.mcp.json`

## Acceptance

- Huge/generated native full reads block; medium and warning-phase large reads warn; payload/runtime failures fail open.
- Exactly one LeanCtx rewrite, redirect, and observe registration for each applicable Claude event.
- No `/Users/agallentes` or `/Users/axos-agallentes` paths in owned files.
- Headroom MCP is absent; Claude uses the persistent provider proxy with `ENABLE_TOOL_SEARCH=auto`, LeanCtx/pctx exclusions, and Kompress disabled.
- Shell syntax and applicable existing hook/config tests pass.

## Constraints

- You are not alone in the codebase; do not revert or overwrite other agents' edits.
- Do not edit shared classifier, shared tests, docs, plans outside this spec, or any Cursor/Codex/AGY/Windsurf file.
- Do not spawn subagents.
- Do not commit.

## Spec Change Log

- 2026-07-29: Initial frozen scope.

## Review Triage Log

