# Tool Priority, Batching, and Best Practices

These rules apply to every project on this machine where `pctx` (and its upstream servers like `Serena`) is configured.

> **Precedence:** In pctx-enabled projects, these rules supersede `agent-user-global.md` for tool selection (stricter: "Never" vs "Prefer").

## 1. Tool Priority Stack
Always use tools in this order. Stop at the first that satisfies your need. **Never use Bash for operations that have a dedicated tool.**

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **Directory Listing** | `Serena.listDir` | `Glob` | `ls`, `find` |
| **Explore file structure** | `Serena.getSymbolsOverview` | `Read (limit/offset)` | `cat`, `head`, `tail` |
| **Find symbol by name** | `Serena.findSymbol` | `Serena.searchForPattern` | `grep`, `rg` |
| **Pattern/regex search** | `Serena.searchForPattern` (+ `restrict_search_to_code_files: true`) | `Grep tool` | `grep`, `rg` |
| **Finding Files** | `Serena.findFile` | `Glob` | `find` |
| **Project knowledge** | `Serena.readMemory` | Read `.serena/memories/*.md` | re-deriving from source |
| **Pre-edit impact analysis** | `Serena.findReferencingSymbols` | `searchForPattern` with type name | skipping impact check |
| **Editing Code** | `Serena.replaceSymbolBody` | `Edit tool` | `sed`, `awk` |
| **Rename symbol** | `Serena.renameSymbol` | Manual multi-file `Edit` | `sed` across files |

> **Exploration order:** When navigating an unfamiliar area, always `getSymbolsOverview` first (file structure), then `findSymbol` (drill into known names), then `searchForPattern` (regex fallback). Never skip to `Read` for analysis.

> **Pre-edit ritual:** Before modifying any symbol, run `findReferencingSymbols` to understand blast radius. This catches breaking changes before they happen.

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

## 4. Serena Quirks and Mandatory Rules

### searchForPattern: always restrict to code files
Always pass `restrict_search_to_code_files: true` to `searchForPattern`. Without it, lock files (`go.sum`, `package-lock.json`) and generated files flood results.

### findSymbol: dot-directory limitation (issue #853)
`findSymbol` **fails silently** on files inside dot-directories (`.serena/`, `.claude/`, `.cursor/`, `.mcp.json`). Use `Serena.readMemory()` for Serena memories, and the `Read` tool for other dot-directory files.

### readMemory: memory-first before code exploration
If a `.serena/memories/` directory exists in the project, call `Serena.listMemories()` at session start and read `START_HERE` (or equivalent entry-point memory) before touching source files. Project knowledge in memories prevents re-deriving facts already captured.

### Memory naming (when writing new memories)
- `architecture/<topic>` — cross-cutting technical decisions
- `story_<N>_<sprint>/<topic>` — sprint-specific context
- `workflows/<process>` — repeatable process documentation

Do not duplicate to local markdown what is already in `.serena/memories/`.

### gopls LSP timeout
If Serena's Go LSP times out (SolidLSP repeated-init issue #634): call `Serena.restartLanguageServer()`. Do not retry the failed call — the server needs to reinitialize first.

## 5. Session Start (Required)
Run `mcp__pctx__list_functions` before the first project access in a session. Write results to `plans/pctx-functions.md` and check its timestamp (TTL: 1 day).

---
*Maintained at: `/Users/axos-agallentes/.dotfiles/ai/rules/tool-priority.md`*
