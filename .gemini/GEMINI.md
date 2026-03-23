## Tool Priority and Workflow

### Tool Priority Stack

Use tools in this order — stop at the first that satisfies your need:

```
DIRECTORY LISTING:
  1st: pctx Serena.listDir      — gitignore-aware, project-scoped
  2nd: Native glob              — flexible patterns
  ✗    Shell ls/find            — avoid

SEARCHING CODE:
  1st: pctx Serena.findSymbol        — LSP-backed, precise
  2nd: pctx Serena.searchForPattern  — project-scoped, gitignore-aware
  3rd: Native ripgrep               — flexible regex
  ✗    Shell grep                   — avoid; no gitignore

READING FILES:
  1st: pctx Serena.getSymbolsOverview — structure without reading file
  2nd: Targeted read with range       — once location known
  ✗    Full file read                 — only when entire content needed

BATCH / MULTI-STEP:
  1st: pctx execute_typescript   — ONE call for multiple Serena ops
  ✗    Sequential calls          — always check if batchable first
```

### Batching Rule

Before any tool call accessing the project, ask: "What else will I need in the next 3 steps?" If 2+ Serena operations → batch into ONE `execute_typescript`.

### Branch Workflow

Never commit directly to `main`. Always create a feature branch first.

### MCP Config Sources (TWO — both must be aligned)

- `~/.gemini/mcp.json` — dedicated MCP file
- `~/.gemini/settings.json` — also supports `mcpServers`

Both must contain only the `pctx` gateway entry. Check both when validating.

### Serena API Convention

All methods use **camelCase**: `listDir`, `searchForPattern`, `findSymbol`, `getSymbolsOverview`, `listMemories`, `initialInstructions`.

---

## Gemini Added Memories
- basictex is installed
- The files ghostty/config, hammerspoon/init.lua, nvim/after/queries/go/injections.scm, nvim/after/queries/go/locals.scm, nvim/lua/lsp_autocommands.lua, nvim/lua/plugins/lsp.lua, nvim/lua/plugins/syntax.lua, nvim/lua/plugins/telescope.lua, ssh/rc, and tmux/tmux.conf were restored from the upstream (caarlos0/dotfiles) repository, not the user's fork origin.
