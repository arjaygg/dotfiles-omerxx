# Tool Priority Stack

These rules apply to every project on this machine where pctx/Serena is configured.

## Tool Priority

Always use tools in this order. Stop at the first that satisfies your need. **Never use Bash for operations that have a dedicated tool.**

```
DIRECTORY LISTING:
  1st: Serena.listDir           — gitignore-aware, project-scoped, recursive
  2nd: Glob                     — flexible patterns, fast
  ✗    Bash ls / find           — never; raw filesystem noise

SEARCHING CODE:
  1st: Serena.findSymbol        — LSP-backed, zero false positives from comments
  2nd: Serena.searchForPattern  — project-scoped, gitignore-aware, LSP context
  3rd: Grep tool                — flexible regex, ripgrep-backed, gitignore-aware
  ✗    Bash grep/rg             — never; no gitignore, 8× slower, token waste

FINDING FILES:
  1st: Serena.findFile          — LSP-aware, project-scoped
  2nd: Glob                     — pattern-based, fast
  ✗    Bash find                — never; no project awareness

READING FILES (stop as soon as you have what you need):
  1st: Serena.getSymbolsOverview    — understand structure WITHOUT reading file
  2nd: Grep / Serena.searchForPattern — find the specific section first
  3rd: Read (with limit/offset)     — targeted read once you know the location
  4th: Read (full file)             — only when entire content is truly needed
  ✗    Bash cat/head/tail           — never; use Read tool

CODE EDITING:
  1st: Serena.replaceSymbolBody / insertAfterSymbol — symbol-aware, precise
  2nd: Edit tool                    — line-based when symbol bounds are unknown
  ✗    Bash sed/awk                 — never for code edits

BATCH / MULTI-STEP:
  1st: pctx execute_typescript      — combine multiple Serena ops in ONE call
  ✗    Multiple sequential calls    — always check if batchable first
```

## Batching Rule

> **Before any tool call that accesses the project, ask: "What else will I need in the next 3 steps?"**
> - If 2+ Serena operations are planned → write ONE `execute_typescript`.
> - If 2+ Read/Grep/Glob ops are independent → fire them in **parallel** (single message, multiple tool calls).
> - Never make a sequential Serena call when a batch would work.

## Serena API Convention

All Serena methods use **camelCase**. Call `mcp__pctx__list_functions` at the start of a new session to confirm current signatures.

| ✅ camelCase (correct) | ✗ snake_case (WRONG) |
|---|---|
| `Serena.listDir(...)` | ~~`Serena.list_dir`~~ |
| `Serena.searchForPattern(...)` | ~~`Serena.search_for_pattern`~~ |
| `Serena.findFile(...)` | ~~`Serena.find_file`~~ |
| `Serena.findSymbol(...)` | ~~`Serena.find_symbol`~~ |
| `Serena.getSymbolsOverview(...)` | ~~`Serena.get_symbols_overview`~~ |
| `Serena.listMemories()` | ~~`Serena.list_memories`~~ |
| `Serena.initialInstructions()` | ~~`Serena.initial_instructions`~~ |
