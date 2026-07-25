---
name: tool-routing
description: Extended tool-routing reference — Qmd vs LeanCtx vs Serena vs Grep decision tables, Graphify's two interfaces, pctx execute_typescript batching + schema guardrails, the full session-init walkthrough, Serena memory-naming conventions, session-continuity tooling, and common tool-selection violations. Invoke on phrases like "which tool should I use", "tool routing", "qmd vs leanctx", "graphify", "hook blocked my command", "session init", "execute_typescript schema", "5+ files" / "many files" / "multiple files", "symbol lookup", "rename symbol", "find references", "docs search" / "documentation search", "dependency graph" / "call graph" / "who calls" — or after an unexplained hook block.
---

# Extended Tool Ecosystem Routing

This is the detailed reference behind `ai/rules/tool-priority.md` §7's quick digest. Load this skill when the digest isn't specific enough — e.g. deciding between Qmd sub-query types, tracing a Graphify call, or working out why a hook blocked something.

## Code Exploration (browsing source, finding symbols, tracing references)

**Priority order: Serena → Repomix → LeanCtx**

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **"Where is X defined?"** | `Serena.findSymbol` | `Serena.searchForPattern` | `LeanCtx.ctxSearch` |
| **"What calls Y?"** | `Serena.findReferencingSymbols` | `Serena.searchForPattern` | `LeanCtx.ctxSearch` |
| **"What's in this package?"** | `Serena.getSymbolsOverview` | `Serena.listDir` | `LeanCtx.ctxTree` |
| **"Show me how X is used broadly"** | `Repomix --compress --include "pkg/X/**"` | `Serena.findReferencingSymbols` | `LeanCtx.ctxRead` on every file |
| **Text pattern across non-code files** | `LeanCtx.ctxSearch` | `Grep tool` | — |

**Rule:** lean-ctx is a file-access layer (read, compress, cache). It has no symbol index. For any task phrased as navigation ("where", "what calls", "what's in"), Serena is the correct first call. LeanCtx is correct for text patterns and file reads — not code structure exploration.

## Code/PR Graph Tooling (Graphify — two real interfaces)

`Graphify` is a real pctx namespace, exposing `queryGraph`, `getNode`, `getNeighbors`, `getCommunity`, `godNodes`, `graphStats`, `shortestPath`, `listPrs`, `getPrImpact`, `triagePrs`. It's backed by `/Users/axos-agallentes/.local/bin/graphify-mcp-conditional` — registers only when a project has `graphify-out/graph.json` (the same per-project scoping as the CLI below). Both interfaces likely serve the same underlying graph data via different access paths.

| Interface | Access path | Use when |
|---|---|---|
| **pctx `Graphify` namespace** | `mcp__pctx__execute_typescript` (`Graphify.queryGraph`, `.getNode`, `.getNeighbors`, `.getCommunity`, `.godNodes`, `.graphStats`, `.shortestPath`, `.listPrs`, `.getPrImpact`, `.triagePrs`) | Already inside an `execute_typescript` batch with other Serena/Qmd/LeanCtx/Repomix calls — combine into one round-trip |
| **Standalone `graphify` CLI** | Shell: `graphify query/path/explain/update` (see the per-project `CLAUDE.md`'s `# graphify` section, e.g. `auc-conversion/CLAUDE.md`) | Standalone shell check, no batching need |

Both operate on the same project-local `graphify-out/graph.json`:

| Task | Command |
|---|---|
| **Scoped question about the codebase** | `graphify query "<question>"` |
| **Relationship between two files/symbols** | `graphify path "<A>" "<B>"` |
| **Focused concept lookup** | `graphify explain "<concept>"` |
| **Broad navigation** | `graphify-out/wiki/index.md` (if present) |
| **Full architecture review** | `graphify-out/GRAPH_REPORT.md` (only when query/path/explain don't surface enough) |
| **Keep graph current after edits** | `graphify update .` (AST-only, no API cost) |

**Rule:** Graphify is per-project either way. Prefer the pctx namespace when already batching other pctx calls; prefer the CLI for a one-off shell check.

## Documentation & Knowledge Lookup

**API note:** Qmd's `search`/`vectorSearch`/`deepSearch` were consolidated into a single `Qmd.query({ searches: [{type: "lex"|"vec"|"hyde", query}] })` call — the typed sub-query replaces the old separate function names. `Qmd.get`/`multiGet`/`status` are unchanged.

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **Find docs by concept/meaning** | `Qmd.query` with a `hyde` or `vec` sub-query | — | `LeanCtx.ctxSearch` on .md files |
| **Find docs by keyword** | `Qmd.query` with a `lex` sub-query | `LeanCtx.ctxSearch` | `Grep` on docs/ |
| **Retrieve a known doc** | `Qmd.get` | `Read(path)` | — |
| **Project knowledge (structured)** | `Serena.readMemory` | `Qmd.query` | Re-deriving from source |

**Decision rule:** Know the doc path → `Qmd.get` or `Read`. Searching by concept, don't know where it lives → `Qmd.query` (`hyde` for fuzzy/semantic, `lex` for exact keywords — combine both in one call if unsure). About project architecture/patterns/decisions → `Serena.readMemory` first, then `Qmd.query` as semantic fallback.

**QMD scope:** indexes `docs/**/*.md` from the main repo plus the current worktree. Does NOT index source code — use Serena for that.

## File Reading

**API note:** LeanCtx consolidated from 23 standalone functions to 11 core functions. `ctxRead`, `ctxSearch`, `ctxShell`, `ctxTree`, `ctxSession` remain direct calls. Former standalone tools `ctxMultiRead` and `ctxSmartRead` are no longer top-level — reach them via `LeanCtx.ctxCall({ name: "ctx_multi_read"|"ctx_smart_read", args: {...} })` dispatch.

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **Read file for editing** | `Read(path)` | — | `LeanCtx.ctxRead` (use Read before Edit) |
| **Read file for analysis** | `LeanCtx.ctxRead(mode: "signatures"\|"map"\|"aggressive")` | `Read` with limit/offset | Uncached full `Read` on large files |
| **Read many files at once** | `LeanCtx.ctxCall({name: "ctx_multi_read", args: {...}})` | Sequential `Read` calls | Calling `ctxMultiRead` directly (removed) |
| **Read with smart compression** | `LeanCtx.ctxCall({name: "ctx_smart_read", args: {...}})` | `LeanCtx.ctxRead` | Calling `ctxSmartRead` directly (removed) |

**Rule:** Always `Read` before `Edit` (required by the Edit tool). For analysis-only reads of large files, use `LeanCtx.ctxRead` with a compression mode to save tokens.

## Shell Commands

| Task | 1st Priority | Avoid |
|---|---|---|
| **Run command, capture output** | `LeanCtx.ctxShell` (compresses output) | `Bash` for commands producing >20 lines |
| **git/mkdir/rm/mv** | `Bash` (simple, low-output) | `LeanCtx.ctxShell` (overkill for 1-line output) |

## Web Research

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **Search for external info** | `WebSearch` | — | — |
| **Fetch a known URL** | `WebFetch(url, prompt)` | — | Fetching without a focused prompt (floods context) |

**Rule:** Always pass a focused `prompt` to `WebFetch` — this uses Claude's built-in summarization to keep output tight. `WebSearch` returns snippets and is preferred for discovery.

## Session Context & Continuity

| Task | Tool |
|---|---|
| **What did I work on before?** | `LeanCtx.ctxSession(action: "load")` |
| **What did a previous agent find?** | `Serena.readMemory` or `LeanCtx.ctxSession(action: "load")` |
| **Persist finding across sessions** | `LeanCtx.ctxSession(action: "finding")` + `Serena.writeMemory` |

## Code Health Routing

| Task | Tool |
|---|---|
| **Assess code maintainability / code health score** | `/code-health` skill |
| **Quick complexity check on a single file** | `/code-health <file>` (pass path as argument) |
| **Code health as part of code review** | `/hawk` (Quality agent runs code health automatically) |
| **CI code health gate** | `make code-health` or `make code-health-json` + scorer script |

## Batching & Code Mode (execute_typescript)

Use `mcp__pctx__execute_typescript` when 2+ operations are planned, or when output needs filtering before it hits context — never make sequential Serena/LeanCtx/Repomix/Qmd calls when one batch would work.

**Batching decision rule:** before any tool call, ask "what else will I need in the next 3 steps?" 2+ Serena/pctx operations planned → one `execute_typescript` call. 2+ Read/Grep/Glob ops independent → fire in parallel instead.

**lean-ctx: native MCP vs pctx.** lean-ctx is registered both as a native MCP server (`mcp__lean-ctx__*`) and as a pctx sub-server (`LeanCtx.*`). Serena, Repomix, and Qmd are pctx-only.

| Situation | Use |
|---|---|
| Single lean-ctx call, no output filtering needed | `mcp__lean-ctx__ctx_read` / `ctx_search` / `ctx_shell` directly |
| 2+ calls (any mix of LeanCtx / Serena / Repomix / Qmd) | `mcp__pctx__execute_typescript` with `Promise.all()` |
| Need to filter/reduce output before it hits context | `execute_typescript` (filter in TypeScript) |

**Code Mode rules:** MUST define a `run()` function; parallelize with `Promise.all()`; filter/map data inside the script and return only what's needed; do NOT call `JSON.parse()` on results (already objects).

**Schema guardrails.** Common failures seen in session logs are schema-name drift, not pctx runtime instability. Use these exact names unless `get_function_details` says otherwise:

| Function | Correct pctx SDK call | Common failing call |
|---|---|---|
| `get_function_details` tool | `{"functions":["Serena.findSymbol"]}` | `{"function_name":"Serena.findSymbol"}` |
| `Serena.readMemory` | `{ memory_name: "START_HERE" }` | `{ name: "START_HERE" }` |
| `Serena.findSymbol` | `{ name_path_pattern: "Symbol", depth: 0 }` | `{ name_path: "Symbol" }` |
| `Serena.searchForPattern` | `{ substring_pattern: "regex" }` | `{ pattern: "regex" }` |
| `LeanCtx.ctxSearch` | `{ pattern: "regex", path: "/abs/path" }` | `{ query: "regex" }` |
| `LeanCtx.ctxRead/ctxTree/ctxCall` | camelCase SDK methods | `ctx_read` / `ctx_tree` / `ctx_call` |

If an `execute_typescript` batch mixes successful results with `.catch(() => ({error}))`, normalize/cast before reading fields — the sandbox type-checks unions strictly.

## Session Start (Required Init Sequence)

Run `mcp__pctx__list_functions` before the first project access in a session. Write results to `plans/pctx-functions.md` and check its timestamp (TTL: 1 day). Skip the full sequence below only if `plans/pctx-functions.md` already exists and was written today.

**Enforcement:** `pre-tool-gate-v2.sh` Section 0 blocks any Grep call until this sequence completes — skipping it means Grep calls get blocked mid-task, so complete init first to avoid interruption.

**Full init sequence** (applies only when a project has both a `.serena/` config dir and `~/.config/pctx/pctx.json`):
1. Call `mcp__pctx__list_functions` — unlocks the session init gate.
2. Run this batch via `mcp__pctx__execute_typescript`:
   ```typescript
   async function run() {
     await Promise.all([
       Serena.initialInstructions(),
       LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "<describe your task here>" } })
     ]);
   }
   ```
3. Write `plans/pctx-functions.md` with today's date (via the Write tool).

**Why each step matters:**
- `list_functions` → sets the session init temp flag
- `Serena.initialInstructions()` → loads project-specific Serena memories and config
- `LeanCtx.ctxCall({ name: "ctx_intent" })` → indexes live project context; required to unlock Grep
- `plans/pctx-functions.md` → file-based gate that survives compaction restarts

## Common Violations

| Violation | Correct replacement |
|---|---|
| `Grep(pattern: "WorkerPool")` — PascalCase lookup | `Serena.findSymbol("WorkerPool")` |
| `Grep(pattern: "func New")` — symbol definition search | `Serena.findSymbol("New*")` or `Serena.searchForPattern` |
| `Read("pkg/worker/pool.go")` without limit — whole file read | `Serena.getSymbolsOverview("pkg/worker/pool.go")`, then Read with limit/offset |
| Multiple sequential `Serena.*` calls (no batch) | `mcp__pctx__execute_typescript` with `Promise.all()` |
| Starting session with Grep/Read before Serena init | Call `mcp__pctx__list_functions` → write `plans/pctx-functions.md` → `Serena.initialInstructions()` |
| `Bash(grep ...)` or `Bash(rg ...)` | Blocked by `permissions.deny`; use `Grep` tool or `Serena.searchForPattern` |
| `Bash(cat file)` / `head -N` / `tail -n +N` / `sed`/`awk` on limits | Blocked; use `Read` with `limit`/`offset`, or `Edit` |
| `Bash(find . -name ...)` | Blocked; use `Glob` |
| `Bash(ls dir/)` | Use `Glob("dir/*")` |
| `LeanCtx.ctxSearch` for "where is X?", "what calls Y?" | `Serena.findSymbol` / `Serena.findReferencingSymbols` |
| `LeanCtx.ctxRead` to browse a package | `Serena.getSymbolsOverview` first, then `Read` with limit if needed |
| Defaulting to lean-ctx for any code navigation | lean-ctx has no symbol index — use Serena for code, lean-ctx for text |
| `Grep` or `LeanCtx.ctxSearch` on `docs/**/*.md` | `Qmd.query` (lex or hyde sub-query) |
| `WebFetch(url)` without a prompt | Pass a focused `prompt` to `WebFetch` |
| `Read(large_file)` for analysis (no edit intent) | `LeanCtx.ctxCall({name: "ctx_smart_read", ...})` or `ctxRead(mode: "signatures")` |
| Multiple `Read` calls in sequence | `LeanCtx.ctxCall({name: "ctx_multi_read", ...})` |

If you find yourself reaching for Grep, ask: **"Is this a symbol lookup or a pattern search?"** Symbol lookup (known name) → `Serena.findSymbol`. Structural pattern → `Serena.searchForPattern`. Text pattern, non-code → `Grep tool` is acceptable. Finding a file → `Serena.findFile` or `Glob`.
