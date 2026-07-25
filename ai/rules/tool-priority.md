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
| **Directory Listing** | `Glob` | — | `ls`, `find`, `Serena.listDir` (excluded in claude-code context) |
| **Explore file structure** | `Serena.getSymbolsOverview` | `Read (limit/offset)` | `cat`, `head`, `tail` |
| **Find symbol by name** | `Serena.findSymbol` | `LeanCtx.ctxSearch` | `grep`, `rg` |
| **Pattern/regex search** | `LeanCtx.ctxSearch` | — | `grep`, `rg`, `Grep tool` (hard-blocked), `Serena.searchForPattern` (not exposed in this context) |
| **Finding Files** | `Glob` | `LeanCtx.ctxGlob` | `find` |
| **Project knowledge** | `Serena.readMemory` | Read `.serena/memories/*.md` | re-deriving from source |
| **Pre-edit impact analysis** | `Serena.findReferencingSymbols` | `LeanCtx.ctxSearch` with type name | skipping impact check |
| **Editing Code** | `Serena.replaceSymbolBody` | `Edit tool` | `sed`, `awk` |
| **Rename symbol** | `Serena.renameSymbol` | Manual multi-file `Edit` | `sed` across files |

> **Exploration order:** When navigating an unfamiliar area, always `getSymbolsOverview` first (file structure), then `findSymbol` (drill into known names), then `LeanCtx.ctxSearch` (regex fallback). Never skip to `Read` for analysis.

> **Pre-edit ritual:** Before modifying any symbol, run `findReferencingSymbols` to understand blast radius. This catches breaking changes before they happen.

---

## 2. Batching

Use `mcp__pctx__execute_typescript` when 2+ Serena/LeanCtx/Repomix/Qmd operations are planned, or when output needs filtering before it hits context. Fire independent Read/Grep/Glob calls in parallel instead of sequentially. Full schema guardrails and Code Mode rules → `tool-routing` skill.

---

## 3. Serena Quirks and Mandatory Rules

All Serena methods use **camelCase** (`findSymbol`, not `find_symbol`; `searchForPattern`, not `search_for_pattern`). `Serena.initialInstructions()` does not cover any of this — these are project-specific quirks, not part of Serena's own manual.

- `searchForPattern` is not exposed in this session's Serena claude-code context (nor are `findFile`/`listDir`) — use `LeanCtx.ctxSearch` for pattern/regex search instead. It has no `restrict_search_to_code_files` flag and handles lock/generated files fine without one.
- `findSymbol` **fails silently** on files inside dot-directories (`.serena/`, `.claude/`, `.cursor/`, `.mcp.json`). Use `Serena.readMemory()` for Serena memories, `Read` for other dot-directory files.
- Serena memory session-init workflow (`listMemories`/`START_HERE`) and memory-naming conventions: **`tool-routing` skill** (`ai/skills/tool-routing/SKILL.md`).

---

## 4. Everything Else → `tool-routing` Skill

Multi-file context selection (5+ files → repomix), the full pctx `execute_typescript` schema-guardrails table, the required session-init walkthrough, Qmd-vs-LeanCtx-vs-Serena-vs-Grep decision tables, Graphify's pctx/CLI breakdown, session-continuity tooling, and common tool-selection violations all live in **`ai/skills/tool-routing/SKILL.md`**. Invoke it when unsure which tool fits a docs search, large-file read, shell command, web fetch, or graph query — or after an unexplained hook block.

---
*Maintained at: `/Users/axos-agallentes/.dotfiles/ai/rules/tool-priority.md`*
