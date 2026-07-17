# Tool Priority, Batching, and Best Practices

These rules apply to every project on this machine where `pctx` (and its upstream servers like `Serena`) is configured.

> **Precedence:** In pctx-enabled projects, these rules supersede `ai/rules/lean-ctx.md` for tool selection (stricter: "Never" vs "Prefer"). `agent-user-global.md` says little about tool selection specifically, so the practical conflict this resolves is with `lean-ctx.md`.

---

## 0. ⛔ Pre-Bash Decision Gate — MANDATORY BEFORE EVERY BASH CALL

**Check this map before writing ANY `Bash` command. If a dedicated tool exists, use it — no exceptions, no workarounds.**

| Intent | WRONG (Bash) | RIGHT (Dedicated Tool) |
|---|---|---|
| Read a file | `cat file` | `Read(file_path)` |
| Read first N lines | `head -N file` | `Read(file_path, limit: N)` |
| Read from line N onward | `tail -n +N file` | `Read(file_path, offset: N)` |
| Read lines N to M | `sed -n 'N,Mp'`, `awk 'NR>=N && NR<=M'` | `Read(file_path, offset: N, limit: M-N)` |
| Limit any piped output | `cmd \| head -N`, `cmd \| awk 'NR<=N'` | Use the tool's built-in `limit:` param |
| Limit output from external CLI (kubectl, gh, az, docker, jq, curl) | N/A — no agent-accessible `limit:` param | Pipe to `head -N` is correct; this is NOT an anti-pattern |
| Search file contents | `grep pattern`, `rg pattern` | `Grep(pattern, path)` |
| Find files by name/pattern | `find . -name "*.go"` | `Glob("**/*.go")` |
| List directory | `ls dir/` | `Glob("dir/*")` |
| Edit a file in-place | `sed -i`, `awk` rewrite | `Edit(file, old_string, new_string)` |
| Create a file | `echo > file`, `cat <<EOF` | `Write(file_path, content)` |

**External CLI exception:** For commands invoking external tools (kubectl, gh, az, docker, jq, curl) where no agent-accessible `limit:` parameter exists, piping to `head -N` is explicitly permitted and is the correct pattern.

**If a hook fires blocking your Bash command:** switch to the correct dedicated tool immediately (no shell workaround), then write a feedback memory noting what was blocked and the correct tool — don't wait for the user to point it out.

**`[HARD-BLOCK — DO NOT RETRY]` marker:** prefixes every `pre-tool-gate-v2.sh` denial. The block is final for that exact command — retrying it, even reworded, hits the same block again. Switch to the named tool instead of re-attempting. It exists to short-circuit retry loops before `advisor-escalate.py`'s recurrence tracker has to catch them after 3+ repeats.

---

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

---

## 2. Multi-File Context Selection

For **5+ files** across multiple packages, or when full-repo/multi-package context is needed, use the **`repomix` skill** (`ai/skills/repomix/SKILL.md`) rather than sequential Reads — it covers scope selection (full repo vs. focused package `--include`), token-budget targets, and the MCP `@repomix` path. For **<5 files**, plain `Read` + `Serena.findSymbol` (sequential) is faster than packing.

---

## 3. Batching & Code Mode

Use `mcp__pctx__execute_typescript` when 2+ operations are planned, or when output needs filtering before it hits context — never make sequential Serena/LeanCtx/Repomix/Qmd calls when one batch would work.

### Batching Decision Rule
> Before any tool call, ask: **"What else will I need in the next 3 steps?"**
> - 2+ Serena/pctx operations planned → one `execute_typescript` call.
> - 2+ Read/Grep/Glob ops independent → fire in **parallel**.

### lean-ctx: native MCP vs pctx

lean-ctx is registered **both** as a native MCP server (`mcp__lean-ctx__*`) and as a pctx sub-server (`LeanCtx.*`). Serena, Repomix, and Qmd are **pctx-only**.

| Situation | Use |
|---|---|
| Single lean-ctx call, no output filtering needed | `mcp__lean-ctx__ctx_read` / `ctx_search` / `ctx_shell` directly |
| 2+ calls (any mix of LeanCtx / Serena / Repomix / Qmd) | `mcp__pctx__execute_typescript` with `Promise.all()` |
| Need to filter/reduce output before it hits context | `execute_typescript` (filter in TypeScript) |

**Code Mode rules:** MUST define a `run()` function; parallelize with `Promise.all()`; filter/map data inside the script and return only what's needed; do NOT call `JSON.parse()` on results (already objects).

---


### pctx execute_typescript Schema Guardrails

Common failures seen in session logs are schema-name drift, not pctx runtime instability. Use these exact names unless `get_function_details` says otherwise:

| Function | Correct pctx SDK call | Common failing call |
|---|---|---|
| `get_function_details` tool | `{"functions":["Serena.findSymbol"]}` | `{"function_name":"Serena.findSymbol"}` |
| `Serena.readMemory` | `{ memory_name: "START_HERE" }` | `{ name: "START_HERE" }` |
| `Serena.findSymbol` | `{ name_path_pattern: "Symbol", depth: 0 }` | `{ name_path: "Symbol" }` |
| `Serena.searchForPattern` | `{ substring_pattern: "regex" }` | `{ pattern: "regex" }` |
| `LeanCtx.ctxSearch` | `{ pattern: "regex", path: "/abs/path" }` | `{ query: "regex" }` |
| `LeanCtx.ctxRead/ctxTree/ctxCall` | camelCase SDK methods | `ctx_read` / `ctx_tree` / `ctx_call` |

If an `execute_typescript` batch mixes successful results with `.catch(() => ({error}))`, normalize/cast before reading fields; the sandbox type-checks unions strictly.

---

## 4. Serena API Convention
All Serena methods use **camelCase**.
- `Serena.listDir` (NOT `list_dir`)
- `Serena.findSymbol` (NOT `find_symbol`)
- `Serena.searchForPattern` (NOT `search_for_pattern`)

---

## 5. Serena Quirks and Mandatory Rules

`Serena.initialInstructions()` does not cover any of this — these are project-specific quirks, not part of Serena's own manual.

- Always pass `restrict_search_to_code_files: true` to `searchForPattern` — otherwise lock files (`go.sum`, `package-lock.json`) and generated files flood results.
- `findSymbol` **fails silently** on files inside dot-directories (`.serena/`, `.claude/`, `.cursor/`, `.mcp.json`). Use `Serena.readMemory()` for Serena memories, `Read` for other dot-directory files.
- If `.serena/memories/` exists, call `Serena.listMemories()` at session start and read `START_HERE` before touching source files.
- Memory naming: `architecture/<topic>`, `story_<N>_<sprint>/<topic>`, `workflows/<process>`. Don't duplicate to markdown what's already in `.serena/memories/`.
- gopls LSP timeout (SolidLSP issue #634): call `Serena.restartLanguageServer()` — do not retry the failed call, the server needs to reinitialize first.

---

## 6. Session Start (Required)
Run `mcp__pctx__list_functions` before the first project access in a session. Write results to `plans/pctx-functions.md` and check its timestamp (TTL: 1 day).

**Enforcement:** `pre-tool-gate-v2.sh` Section 0 will **block** any Grep call until this sequence completes. Skipping this step means Grep calls will be blocked mid-task — complete the init sequence first to avoid interruption.

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

Skip the full sequence only if `plans/pctx-functions.md` already exists and was written today.

---

## 7. Extended Tool Ecosystem Routing

Beyond §0/§1 above: the full Qmd-vs-LeanCtx-vs-Serena-vs-Grep decision tables, the Graphify pctx/CLI two-interface breakdown, the Qmd/LeanCtx API-consolidation notes, session-continuity tooling, and the complete list of common tool-selection violations all live in the **`tool-routing` skill** (`ai/skills/tool-routing/SKILL.md`). Invoke it when unsure which tool fits a docs search, large-file read, shell command, web fetch, or graph query — or after a hook block you don't understand.

Quick digest:
- **Docs/knowledge lookup:** by concept → `Qmd.query` (`hyde`/`vec` sub-query); by keyword → `Qmd.query` (`lex`). Never Grep/`LeanCtx.ctxSearch` on `docs/**/*.md`.
- **Code navigation** ("where is X", "what calls Y", "what's in this package") → Serena, never LeanCtx (it has no symbol index).
- **Shell output >20 lines** → `LeanCtx.ctxShell`; simple git/mkdir/rm → plain `Bash`.
- **`WebFetch`** always needs a focused `prompt` param; `WebSearch` is preferred for discovery.
- **Code health** → `/code-health` skill. **PR/graph queries** → `Graphify` (pctx namespace) or the `graphify` CLI.

---
*Maintained at: `/Users/axos-agallentes/.dotfiles/ai/rules/tool-priority.md`*
