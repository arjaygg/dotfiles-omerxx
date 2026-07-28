# Serena execution log investigation — 2026-07-28

## Scope

Diagnosis only. No hook, rule, or skill behavior changed.

## Checked

- Codex session JSONL transcripts under `~/.codex/sessions/2026/07/28/`.
- Live pctx TypeScript SDK surface via `mcp__pctx.execute_typescript`.
- Live Serena startup/runtime logs under `~/.serena/mcp_stderr.log` and `~/.serena/logs/2026-07-28/`.
- Dotfiles guidance sources that teach Serena/pctx calls.

## Findings

1. `TS2339: Property 'initialInstructions' does not exist on type '{}'` is caused by TypeScript inference on an untyped accumulator object:
   - Failing shape: `const result = {}; result.initialInstructions = ...`
   - Working shape: `const result: any = {}; result.initialInstructions = ...`
   - This is a pctx sandbox compile-time error, not a Serena runtime failure.

2. `TS2339: Property 'searchForPattern' does not exist on type 'typeof Serena'` is valid for the current pctx SDK surface:
   - Current `Object.keys(Serena)` does not include `searchForPattern`, `findFile`, or `listDir`.
   - Current replacement for regex/text search is `LeanCtx.ctxSearch(...)`.
   - Several main-branch guidance files still recommend `Serena.searchForPattern`.

3. `TS2561: 'memory_file_name' does not exist in type 'ReadMemoryInput'` is valid for the current pctx SDK surface:
   - Correct current call is `Serena.readMemory({ memory_name: "START_HERE" })`.
   - `Serena.readMemory({ name: "START_HERE" })` compiles as an error without casts and fails at runtime with casts.
   - `.claude/hooks/session-init.sh` currently emits the stale hint `Serena.readMemory({ name: "START_HERE" })`.

4. Serena server logs show repeated normal startups for `.dotfiles` and no corresponding server crash/traceback for these TypeScript errors.

## Root cause

The observed errors are primarily stale local guidance and pctx SDK-call snippets colliding with the current pctx-generated TypeScript types. The errors are client-side compile-time validation failures before the intended Serena calls run.

## Proposed fixes

- Update `.claude/hooks/session-init.sh` to emit `Serena.readMemory({ memory_name: "START_HERE" })`.
- Update `ai/rules/tool-priority.md`, `ai/skills/tool-routing/SKILL.md`, and affected skills to remove `Serena.searchForPattern` references in the current `claude-code` pctx context.
- Add/extend a validation script that fails on stale pctx SDK examples such as `Serena.searchForPattern`, `Serena.readMemory({ name:`, and `memory_file_name`.
- Prefer typed-safe snippets in `execute_typescript`: either return directly or declare accumulators as `Record<string, unknown>` / `any` before assigning dynamic fields.
