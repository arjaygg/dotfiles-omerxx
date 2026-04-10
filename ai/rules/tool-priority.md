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

## 2. Multi-File Context Selection Rule

When working with **5+ files** across multiple packages, choose your approach based on scope and token budget:

| Scope | Approach | Why |
|---|---|---|
| < 5 files | `Read` + `Grep` / `findSymbol` (sequential) | Individual files are faster than full packing |
| 5–20 files, full context needed | `Repomix --compress` (full scope) | Compresses 300K+ tokens to 40–80K; fits Claude's window |
| 3–4 specific packages, debug focus | `Repomix --compress --include "pkg/foo/**,pkg/bar/**"` | Focused compression; traces data flows without noise |
| Single deep file | `Read` (one-shot) or `Serena.getSymbolsOverview` | No packing needed |

### Decision Triggers
- **"Implement a new transformer following existing patterns"** → Use Repomix (architecture context)
- **"Trace the FK resolution path across 3+ files"** → Use Repomix (focused scope)
- **"Debug this cross-file bug"** → Use Repomix if span > 4 files
- **"Find all usages of symbol X"** → Use `Serena.findReferencingSymbols` (no packing needed)

### Token Budgets (Validated)
- Full code (pkg/** + cmd/**): ~357K tokens → compress to ~50–70K ✅
- Specific packages (3–4): ~18–50K tokens (already tight) ✅
- Keep total context < 180K to leave room for reasoning

> **MCP Tool:** For projects with registered Repomix MCP, use `@repomix` in Claude Code prompts. No manual file generation needed.

## 4. Batching & Code Mode
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

```typescript
// Example: explore a package before editing
const result = await mcp__pctx__execute_typescript(`
async function run() {
  const [overview, refs, file] = await Promise.all([
    Serena.getSymbolsOverview("pkg/worker/"),
    Serena.findReferencingSymbols("WorkerPool"),
    Serena.findFile("config.go"),
  ]);
  // Filter only what matters — don't return everything
  return {
    exports: overview.symbols?.filter(s => s.exported),
    usageSites: refs.locations?.length,
    configPath: file.path,
  };
}
`);
```

## 5. Serena API Convention
All Serena methods use **camelCase**.
- `Serena.listDir` (NOT `list_dir`)
- `Serena.findSymbol` (NOT `find_symbol`)
- `Serena.searchForPattern` (NOT `search_for_pattern`)

## 6. Serena Quirks and Mandatory Rules

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

## 7. Session Start (Required)
Run `mcp__pctx__list_functions` before the first project access in a session. Write results to `plans/pctx-functions.md` and check its timestamp (TTL: 1 day).

**Enforcement:** `pre-tool-gate-v2.sh` Section 0 will **block** any Grep call until this sequence completes. The gate checks for a session-scoped flag set by `post-tool-analytics.sh` when a Serena or pctx tool is first called. Skipping this step means Grep calls will be blocked mid-task — complete the init sequence first to avoid interruption.

## 8. Why Serena Over Grep/Read

This is not stylistic preference — it is a token budget constraint.

**Grep returns raw text lines. Serena returns structured symbol metadata.**

| Operation | Grep result | Serena result |
|---|---|---|
| Find function `NewWorker` | Entire file lines matching the regex, including comments and strings | One entry: file path + line + full signature |
| Find all usages of `WorkerPool` | All lines containing the string across all files | Structured list of reference sites with context type |
| Explore a package | N/A | Symbol tree: all exported types, funcs, consts in one call |

Grep results flood context. A single Grep for a common symbol name across a Go repo can return 50–200 lines. Serena's `findSymbol` returns 1–5 structured entries. Over a session, this compounds: each Grep that could have been a `findSymbol` wastes 40–200 tokens. At 300+ tool calls per session, the accumulated waste forces early compaction and loses context.

**Secondary reason:** Grep is gitignore-unaware by default and will match lock files, generated code, and vendor directories unless `glob` is carefully restricted. Serena's `searchForPattern` with `restrict_search_to_code_files: true` is filtered by construction.

## 9. Common Violations (How Drift Happens)

Watch for these patterns — they indicate the tool priority rules are being ignored:

| Violation | Correct replacement |
|---|---|
| `Grep(pattern: "WorkerPool")` — PascalCase lookup | `Serena.findSymbol("WorkerPool")` |
| `Grep(pattern: "func New")` — symbol definition search | `Serena.findSymbol("New*")` or `Serena.searchForPattern` |
| `Read("pkg/worker/pool.go")` without limit — whole file read | `Serena.getSymbolsOverview("pkg/worker/pool.go")`, then Read with limit/offset |
| Multiple sequential `Serena.*` calls (no batch) | `mcp__pctx__execute_typescript` with `Promise.all()` |
| Starting session with Grep/Read before Serena init | Call `mcp__pctx__list_functions` → write `plans/pctx-functions.md` → `Serena.initialInstructions()` |
| `Bash(grep ...)` or `Bash(find ...)` | Blocked by `permissions.deny`; use Serena or Glob |

If you find yourself reaching for Grep, ask: **"Is this a symbol lookup or a pattern search?"**
- Symbol lookup (known name) → `Serena.findSymbol`
- Pattern search (structural) → `Serena.searchForPattern`
- Pattern search (text, non-code) → `Grep tool` is acceptable
- Finding a file → `Serena.findFile` or `Glob`

---
*Maintained at: `/Users/axos-agallentes/.dotfiles/ai/rules/tool-priority.md`*
