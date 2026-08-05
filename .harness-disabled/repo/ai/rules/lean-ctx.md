# lean-ctx — Context Engineering Layer
<!-- lean-ctx-rules-v10 -->

**Scope:** lean-ctx is a file-access/compression layer — reading, shell-output compression, and non-code text/pattern search. It has no symbol index. For code navigation, symbol lookup, referencing, and editing, `ai/rules/tool-priority.md`'s routing table takes precedence (Serena first). The modes and defaults below apply to analysis-only reads of already-known files, shell-output compression, and non-code/text pattern search — not a blanket "always prefer lean-ctx" default for code work.

## Mode Selection
1. Editing the file? → `full` first, then `diff` for re-reads
2. Need API surface only? → `map` or `signatures`
3. Large file, context only? → `entropy` or `aggressive`
4. Specific lines? → `lines:N-M`
5. Active task set? → `task`
6. Unsure? → `auto` (system selects optimal mode)

Anti-pattern: NEVER use `full` for files you won't edit — use `map` or `signatures`.

## File Editing
Use native Edit/StrReplace if available. If Edit requires Read and Read is unavailable, use ctx_edit.
Write, Delete, Glob → use normally. NEVER loop on Edit failures — switch to ctx_edit immediately.

## Proactive (use without being asked)
- `ctx_overview(task)` at session start
- `ctx_compress` when context grows large

Fallback only if a lean-ctx tool is unavailable: use native equivalents.
<!-- /lean-ctx -->
