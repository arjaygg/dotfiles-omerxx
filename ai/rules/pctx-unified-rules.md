# pctx Unified Rules: Tool Priority, Batching, and Best Practices

These rules apply to every project on this machine where `pctx` (and its upstream servers like `Serena`) is configured.

> **Precedence:** In pctx-enabled projects, these rules supersede `agent-user-global.md` for tool selection (stricter: "Never" vs "Prefer").

## 1. Tool Priority Stack
Always use tools in this order. Stop at the first that satisfies your need. **Never use Bash for operations that have a dedicated tool.**

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **Directory Listing** | `Serena.listDir` | `Glob` | `ls`, `find` |
| **Code Search** | `Serena.findSymbol` | `Serena.searchForPattern` | `grep`, `rg` |
| **Finding Files** | `Serena.findFile` | `Glob` | `find` |
| **Reading Files** | `Serena.getSymbolsOverview` | `Read (limit/offset)` | `cat`, `head`, `tail` |
| **Editing Code** | `Serena.replaceSymbolBody` | `Edit tool` | `sed`, `awk` |

## 2. Batching & Code Mode
Use `pctx execute_typescript` when 2+ operations are planned or when data processing should happen in the sandbox.

> **MCP tool name:** `mcp__pctx__execute_typescript` (call this directly when batching)

### Batching Decision Rule
> Before any tool call, ask: **"What else will I need in the next 3 steps?"**
> - If 2+ Serena operations are planned → write ONE `execute_typescript`.
> - If 2+ Read/Grep/Glob ops are independent → fire them in **parallel**.
> - Never make a sequential Serena call when a batch would work.

### Code Mode Usage (pctx)
- MUST define a `run()` function.
- Parallelize independent ops with `Promise.all()`.
- Filter/map data inside the script; return only final results to the agent.
- Do NOT call `JSON.parse()` on results (already objects).

## 3. Serena API Convention
All Serena methods use **camelCase**.
- `Serena.listDir` (NOT `list_dir`)
- `Serena.findSymbol` (NOT `find_symbol`)
- `Serena.searchForPattern` (NOT `search_for_pattern`)

## 4. Session Start (Required)
Run `mcp__pctx__list_functions` before the first project access in a session. Write results to `plans/pctx-functions.md` and check its timestamp (TTL: 1 day).

---
*Maintained at: `/Users/axos-agallentes/.dotfiles/ai/rules/pctx-unified-rules.md`*
