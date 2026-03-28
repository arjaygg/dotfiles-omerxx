---
name: pctx-code-mode
description: Use pctx Code Mode to batch multiple Serena/MCP operations into a single TypeScript script instead of making sequential tool calls. Trigger when 2+ file operations, agent config checks, directory listings, or data processing steps are needed in one request.
triggers:
  - process data
  - batch process
  - run a script
  - complex extraction
  - bulk data
  - use pctx
  - multiple files
  - read several
  - check all agents
  - explore the project
  - list and read
  - gather information
  - collect data from
---

# pctx Code Mode

You have access to the `pctx` MCP gateway. Instead of making sequential tool calls
(like reading 20 files one by one, or checking each agent config separately), write a
single Deno-compatible TypeScript script and execute it via `mcp__pctx__execute_typescript`.

## Batching Decision Rule

> Before any tool call that accesses the project, ask: "What else will I need in the
> next 3 steps?" If 2+ Serena operations are planned → batch them into ONE
> `execute_typescript`. If 2+ Read/Grep/Glob ops are independent → fire them in parallel.
> Never make a sequential Serena call when a batch would work.

## Tool Priority Stack

Use tools in this order — stop at the first that satisfies your need:

```
DIRECTORY LISTING:
  1st: Serena.listDir           — gitignore-aware, project-scoped, recursive
  2nd: Glob                     — flexible patterns, fast
  ✗    Bash ls                  — never; raw filesystem noise

SEARCHING CODE:
  1st: Serena.findSymbol        — LSP-backed, zero false positives from comments
  2nd: Serena.searchForPattern  — project-scoped, gitignore-aware, LSP context
  3rd: Grep tool                — flexible regex, ripgrep-backed, gitignore-aware
  ✗    Bash grep/rg             — never; no gitignore, token waste

FINDING FILES:
  1st: Serena.findFile          — LSP-aware, project-scoped
  2nd: Glob                     — pattern-based, fast
  ✗    Bash find                — never; no project awareness

READING FILES (stop as soon as you have what you need):
  1st: Serena.getSymbolsOverview    — understand structure WITHOUT reading the file
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

## Serena API Naming Convention

All Serena methods use **camelCase**. Common methods:

| camelCase (correct) | snake_case (WRONG) |
|---|---|
| `Serena.listDir(...)` | ~~`Serena.list_dir`~~ |
| `Serena.searchForPattern(...)` | ~~`Serena.search_for_pattern`~~ |
| `Serena.findFile(...)` | ~~`Serena.find_file`~~ |
| `Serena.findSymbol(...)` | ~~`Serena.find_symbol`~~ |
| `Serena.getSymbolsOverview(...)` | ~~`Serena.get_symbols_overview`~~ |
| `Serena.listMemories()` | ~~`Serena.list_memories`~~ |
| `Serena.initialInstructions()` | ~~`Serena.initial_instructions`~~ |
| `Serena.readMemory(...)` | ~~`Serena.read_memory`~~ |
| `Serena.writeMemory(...)` | ~~`Serena.write_memory`~~ |

**Always call `mcp__pctx__list_functions` at the start of a new session to confirm
current signatures before writing execute_typescript scripts.**

## When to Use

- You need to loop over multiple files or directories
- You need to check 2+ agent configs in one go
- You need to perform data extraction or transformation across files
- You are hitting context limits by dumping raw file contents into chat
- Any request that implies 2+ file/MCP operations

## How to Write Scripts

Scripts run in a Deno sandbox. All registered SDK namespaces (`Serena`, `Exa`, etc.)
are available globally — no imports needed.

```typescript
async function run() {
  // Batch multiple operations in parallel where possible
  const [topDirs, memories] = await Promise.all([
    Serena.listDir({ relative_path: ".", recursive: false }),
    Serena.listMemories(),
  ]);

  // Search for patterns across the project
  const results = await Serena.searchForPattern({
    substring_pattern: "mcpServers",
    relative_path: ".",
  });

  // Return only what you need — filter in the script, not in chat
  return {
    dirs: topDirs,
    memories: memories,
    searchResults: results,
  };
}
```

**Rules:**
- MUST define a `run()` function — it is called automatically
- Use `await` for every async call
- Return only the data you need (filter/map before returning)
- Use `Promise.all()` to parallelize independent operations
- Do NOT call `JSON.parse()` on results — they are already objects

**Anti-patterns that break namespace injection (`Serena` will be `undefined` at runtime):**

```typescript
// ❌ WRONG — bare top-level await (TS1378 compile error)
const result = await Serena.listDir({ relative_path: ".", recursive: false });

// ❌ WRONG — IIFE (executes before namespace injection; Serena is undefined)
(async () => {
  const result = await Serena.listDir({ relative_path: ".", recursive: false });
})();

// ✅ CORRECT — define run(); the sandbox injects all namespaces before calling it
async function run() {
  const result = await Serena.listDir({ relative_path: ".", recursive: false });
  return result;
}
```
