# Codex Agent Instructions

## Tool Priority Stack

Always use tools in this order. Stop at the first that satisfies your need.

```
DIRECTORY LISTING:
  1st: pctx Serena.listDir      — gitignore-aware, project-scoped
  2nd: Native glob/ls           — flexible patterns
  ✗    Raw find/ls              — avoid; no project awareness

SEARCHING CODE:
  1st: pctx Serena.findSymbol        — LSP-backed, precise
  2nd: pctx Serena.searchForPattern  — project-scoped, gitignore-aware
  3rd: Native ripgrep               — flexible regex
  ✗    Shell grep                   — avoid; no gitignore

FINDING FILES:
  1st: pctx Serena.findFile    — LSP-aware, project-scoped
  2nd: Native glob             — pattern-based

READING FILES:
  1st: pctx Serena.getSymbolsOverview — structure without reading full file
  2nd: pctx Serena.searchForPattern   — find specific section first
  3rd: Targeted file read (with range) — once location known
  ✗    Full file read           — only when entire content is needed

BATCH / MULTI-STEP:
  1st: pctx execute_typescript  — combine multiple Serena ops in ONE call
  ✗    Multiple sequential calls — always batch when possible
```

## Batching Rule

Before any tool call that accesses the project, ask: "What else will I need in the next 3 steps?"
- If 2+ Serena operations are planned → write ONE `execute_typescript`.
- If 2+ file ops are independent → execute them in parallel.

## Branch Workflow

Never commit directly to `main`. Create a feature branch first using the project's stack workflow.

## MCP Gateway

All MCP traffic routes through `pctx`:
- Gateway config: `/Users/agallentes/.config/pctx/pctx.json`
- Servers: serena, exa, sequential-thinking, notebooklm, markitdown
- Serena API uses **camelCase**: `listDir`, `searchForPattern`, `findSymbol`, `getSymbolsOverview`
