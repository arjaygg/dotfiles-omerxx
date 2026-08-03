---
name: tool-routing
description: Extended tool-routing reference — Qmd vs LeanCtx vs Serena vs Grep decision tables, Graphify's two interfaces, parallel tool-call batching, the full session-init walkthrough, Serena memory-naming conventions, session-continuity tooling, and common tool-selection violations. Invoke on phrases like "which tool should I use", "tool routing", "qmd vs leanctx", "graphify", "hook blocked my command", "session init", "batching", "5+ files" / "many files" / "multiple files", "symbol lookup", "rename symbol", "find references", "docs search" / "documentation search", "dependency graph" / "call graph" / "who calls" — or after an unexplained hook block.
---

# Extended Tool Ecosystem Routing

This is the detailed reference behind `ai/rules/tool-priority.md` §7's quick digest. Load this skill when the digest isn't specific enough — e.g. deciding between Qmd sub-query types, tracing a Graphify call, or working out why a hook blocked something.

## Code Exploration (browsing source, finding symbols, tracing references)

**Priority order: Serena → Repomix → LeanCtx**

| Task | 1st Priority | 2nd Priority | Avoid |
|---|---|---|---|
| **"Where is X defined?"** | `Serena.findSymbol` | `LeanCtx.ctxSearch` | — |
| **"What calls Y?"** | `Serena.findReferencingSymbols` | `LeanCtx.ctxSearch` | — |
| **"What's in this package?"** | `Serena.getSymbolsOverview` | `LeanCtx.ctxTree` | — |
| **"Show me how X is used broadly"** | `Repomix --compress --include "pkg/X/**"` | `Serena.findReferencingSymbols` | `LeanCtx.ctxRead` on every file |
| **Text pattern across non-code files** | `LeanCtx.ctxSearch` | `Grep tool` | — |

**Rule:** lean-ctx is a file-access layer (read, compress, cache). It has no symbol index. For any task phrased as navigation ("where", "what calls", "what's in"), Serena is the correct first call. LeanCtx is correct for text patterns and file reads — not code structure exploration.

## Code/PR Graph Tooling (Graphify — two real interfaces)

`graphify` is a direct MCP server exposing `query_graph`, `get_node`, `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`. It's backed by `$HOME/.dotfiles/.local/bin/graphify-mcp-conditional` — responds as a no-op unless the project has `graphify-out/graph.json` (the same per-project scoping as the CLI below). Both interfaces serve the same underlying graph data via different access paths.

| Interface | Access path | Use when |
|---|---|---|
| **`graphify` MCP server** | `mcp__graphify__query_graph`, `__get_node`, `__get_neighbors`, `__get_community`, `__god_nodes`, `__graph_stats`, `__shortest_path`, `__list_prs`, `__get_pr_impact`, `__triage_prs` | Inside an agent turn, especially alongside other Serena/Qmd/LeanCtx/Repomix calls issued in parallel |
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

**Rule:** Graphify is per-project either way. Prefer the MCP server inside an agent turn; prefer the CLI for a one-off shell check.

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

## Batching (parallel tool calls)

Every server is a direct MCP server, so batching means **issuing independent calls as parallel tool calls in a single message** — not wrapping them in a sandbox. Never make sequential Serena/LeanCtx/Repomix/Qmd calls when they could go out together.

**Batching decision rule:** before any tool call, ask "what else will I need in the next 3 steps?" Anything independent goes in the same message. Only chain when one call's arguments genuinely depend on another's result.

Serena executes its calls one at a time internally even when several arrive together, so parallel issue is safe: the calls apply in the order issued and cannot race. Each extra round-trip re-sends the whole growing context, which makes batching the single biggest cost lever.

| Situation | Use |
|---|---|
| Single lean-ctx call | `mcp__lean-ctx__ctx_read` / `ctx_search` / `ctx_shell` |
| 2+ independent calls (any mix of LeanCtx / Serena / Repomix / Qmd) | All of them in one message |
| Result feeds the next call's arguments | Sequential — unavoidable |
| Output too large for context | Narrow at the source: `ctx_read` modes, `ctx_search` limits, Serena symbol scoping |

**Schema guardrails.** Common failures are argument-name drift. Use these exact names:

| Tool | Correct arguments | Common failing call |
|---|---|---|
| `read_memory` | `{ memory_name: "START_HERE" }` | `{ name: "START_HERE" }` |
| `find_symbol` | `{ name_path_pattern: "Symbol", depth: 0 }` | `{ name_path: "Symbol" }` |
| `ctx_search` | `{ pattern: "regex", path: "/abs/path" }` | `{ query: "regex" }` |

## Session Start (Required Init Sequence)

**Enforcement:** `pre-tool-gate-v2.sh` Section 0 blocks Grep and Bash until this sequence completes — skipping it means calls get blocked mid-task, so complete init first.

**Full init sequence** (applies to any project with a `.serena/` config dir):
1. Call `mcp__serena__initial_instructions` — loads project-specific Serena memories and config, and unlocks the session init gate.
2. Call `ctx_intent` with `{ query: "<describe your task here>" }` — indexes live project context.

Steps 1 and 2 are independent; issue them as parallel tool calls in one message.

## Common Violations

| Violation | Correct replacement |
|---|---|
| `Grep(pattern: "WorkerPool")` — PascalCase lookup | `find_symbol("WorkerPool")` |
| `Grep(pattern: "func New")` — symbol definition search | `find_symbol("New*")` |
| `Read("pkg/worker/pool.go")` without limit — whole file read | `get_symbols_overview("pkg/worker/pool.go")`, then Read with limit/offset |
| Multiple sequential independent `find_symbol` calls | Issue them as parallel tool calls in one message |
| Starting session with Grep/Read before Serena init | `initial_instructions` + `ctx_intent` first |
| `Bash(grep ...)` or `Bash(rg ...)` | Blocked by `permissions.deny`; use `Grep` tool or `LeanCtx.ctxSearch` |
| `Bash(cat file)` / `head -N` / `tail -n +N` / `sed`/`awk` on limits | Blocked; use `Read` with `limit`/`offset`, or `Edit` |
| `Bash(find . -name ...)` | Blocked; use `Glob` |
| `Bash(ls dir/)` | Use `Glob("dir/*")` |
| `ctx_search` for "where is X?", "what calls Y?" | `find_symbol` / `find_referencing_symbols` |
| `ctx_read` to browse a package | `get_symbols_overview` first, then `Read` with limit if needed |
| Defaulting to lean-ctx for any code navigation | lean-ctx has no symbol index — use Serena for code, lean-ctx for text |
| `Grep` or `LeanCtx.ctxSearch` on `docs/**/*.md` | `Qmd.query` (lex or hyde sub-query) |
| `WebFetch(url)` without a prompt | Pass a focused `prompt` to `WebFetch` |
| `Read(large_file)` for analysis (no edit intent) | `LeanCtx.ctxCall({name: "ctx_smart_read", ...})` or `ctxRead(mode: "signatures")` |
| Multiple `Read` calls in sequence | `LeanCtx.ctxCall({name: "ctx_multi_read", ...})` |

If you find yourself reaching for Grep, ask: **"Is this a symbol lookup or a pattern search?"** Symbol lookup (known name) → `Serena.findSymbol`. Structural pattern → `LeanCtx.ctxSearch`. Text pattern, non-code → `Grep tool` is acceptable. Finding a file → `Glob`.

## Task Tracking Discipline (Multi-Agent)

When spawning subagents for multi-step work:
1. Create the task list first: `TaskCreate` with all subtasks.
2. Export `CLAUDE_CODE_TASK_LIST_ID=<id>` in each subagent's environment.
3. Each subagent uses `TaskUpdate` (not a new `TaskCreate`) to report progress.
4. The orchestrator polls `TaskGet` before aggregating results.

Never abandon a `TaskCreate` list — orphaned lists accumulate across sessions. Mark cancelled
tasks with status `cancelled`. This is a shared task-list system for coordinating *multiple*
agents — single-agent step tracking uses `TodoWrite` instead (see `agent-user-global.md` §
TodoWrite Mandate).

## Serena Memory Session-Init Workflow

If `.serena/memories/` exists, call `Serena.listMemories()` at session start and read
`START_HERE` before touching source files.

Memory naming: `architecture/<topic>`, `story_<N>_<sprint>/<topic>`, `workflows/<process>`.
Don't duplicate to markdown what's already in `.serena/memories/`.
