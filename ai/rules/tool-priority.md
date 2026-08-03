# Tool Priority, Batching, and Best Practices

These rules apply to every project on this machine where the MCP servers (`Serena`, `LeanCtx`, `Repomix`, `Graphify`) are configured.

> **Precedence:** Where those servers are configured, these rules supersede `ai/rules/lean-ctx.md` for tool selection (stricter: "Never" vs "Prefer"). `agent-user-global.md` says little about tool selection specifically, so the practical conflict this resolves is with `lean-ctx.md`.
>
> **`lean-ctx.md` is dormant, and the precedence above is therefore mostly moot** (verified 2026-08-03). It is linked into no client's rules directory, so it never loads as a rule; its guidance reaches sessions only via the lean-ctx MCP server's own injected instructions. It also carries a `<!-- lean-ctx-rules-vN -->` marker, meaning the binary regenerates it and edits to it are discarded — so notes about it belong here, not in it. Leaving it unlinked is deliberate: linking it would add a rule to every session for guidance this file already overrides. Do not "fix" the dangling-looking reference by linking it.

---

## 0. ⛔ Pre-Bash Decision Gate — MANDATORY BEFORE EVERY BASH CALL

**Check this map before writing ANY `Bash` command. If a dedicated tool exists, use it — no exceptions, no workarounds.**

| Intent | WRONG (Bash) | RIGHT (Dedicated Tool) |
|---|---|---|
| Understand a file | `cat file` | `ctx_compose`, then `ctx_read(mode="task")` |
| Quote a file | `cat file` | `ctx_read(mode="reference")` |
| Read lines N to M | `sed -n 'N,Mp'`, `awk 'NR>=N && NR<=M'` | `ctx_read(mode="lines:N-M")` |
| Exact/edit-ready read | `cat file` | `ctx_read(mode="raw"|"full"|"anchored")` |
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
| **Explore file structure** | `Serena.getSymbolsOverview` | `LeanCtx.ctxCompose` / focused `ctxRead` | `cat`, unscoped full reads |
| **Find symbol by name** | `Serena.findSymbol` | `LeanCtx.ctxSearch` | `grep`, `rg` |
| **Pattern/regex search** | `LeanCtx.ctxSearch` | — | native `grep`/`rg` over large content |
| **Finding Files** | `Glob` | `LeanCtx.ctxGlob` | `find` |
| **Project knowledge** | `Serena.readMemory` | Read `.serena/memories/*.md` | re-deriving from source |
| **Pre-edit impact analysis** | `Serena.findReferencingSymbols` | `LeanCtx.ctxSearch` with type name | skipping impact check |
| **Editing Code** | `Serena.replaceSymbolBody` | `Edit tool` | `sed`, `awk` |
| **Rename symbol** | `Serena.renameSymbol` | Manual multi-file `Edit` | `sed` across files |

> **Exploration order:** When navigating an unfamiliar area, always `getSymbolsOverview` first (file structure), then `findSymbol` (drill into known names), then `LeanCtx.ctxSearch` (regex fallback). Never skip to `Read` for analysis.

> **Pre-edit ritual:** Before modifying any symbol, run `findReferencingSymbols` to understand blast radius. This catches breaking changes before they happen.

Large-file thresholds, Markdown fidelity rules, and exactness escape hatches are defined once in `context-and-compaction.md`.

---

## 2. Batching

Issue independent Serena/LeanCtx/Repomix calls as **parallel tool calls in one message** — they cannot race, and each extra round-trip re-sends the whole growing context. Batch independent `ctx_read`/`ctx_search`/`ctx_tree` calls instead of chaining native tools. Full routing rules → `tool-routing` skill.

---

## 3. Serena Quirks and Mandatory Rules

Serena is a direct MCP server, so its tools use their native **snake_case** names (`find_symbol`, `search_for_pattern`, `replace_symbol_body`). `initial_instructions` does not cover the quirks below — they are project-specific, not part of Serena's own manual.

- `search_for_pattern` is not exposed in the Serena claude-code context (nor are `find_file`/`list_dir`) — use `ctx_search` for pattern/regex search instead. It has no `restrict_search_to_code_files` flag and handles lock/generated files fine without one.
- `find_symbol` **fails silently** on files inside dot-directories (`.serena/`, `.claude/`, `.cursor/`, `.mcp.json`). Use `read_memory` for Serena memories and focused `ctx_read` for other dot-directory files.
- Serena memory session-init workflow (`listMemories`/`START_HERE`) and memory-naming conventions: **`tool-routing` skill** (`ai/skills/tool-routing/SKILL.md`).

---

## 4. Everything Else → `tool-routing` Skill

Multi-file context selection (5+ files → repomix), the required session-init walkthrough, Qmd-vs-LeanCtx-vs-Serena-vs-Grep decision tables, Graphify's MCP/CLI breakdown, session-continuity tooling, and common tool-selection violations all live in **`ai/skills/tool-routing/SKILL.md`**. Invoke it when unsure which tool fits a docs search, large-file read, shell command, web fetch, or graph query — or after an unexplained hook block.

---

## 5. The generated lean-ctx block in `~/.claude/CLAUDE.md` overstates denials

`~/.claude/CLAUDE.md` carries a `## lean-ctx — Replace Mode` section wrapped in
`<!-- lean-ctx -->` / `<!-- lean-ctx-claude-v6 -->` markers. That block is **generated by the
`lean-ctx` binary** (the marker string is compiled in; it is not stored anywhere in this repo),
so any manual edit to it is discarded the next time lean-ctx regenerates the file. The durable
statement therefore lives here.

Verified 2026-07-26, re-verified 2026-08-03 in a live lean-ctx session (`Read` changed):

| Tool | Generated block claims | Actually observed |
|---|---|---|
| `Grep` | denied | **denied** — hard-blocked by `pre-tool-gate-v2.sh` |
| `Read` | denied | **available** (2026-08-03) — present in the toolset and works; was absent on 2026-07-26. `Edit` likewise. |
| `Glob` | denied | **absent from the session toolset** |
| `Bash` | denied | **available** — works after session init |
| `Write` | "use natively" | **available** — correct |

So the block's blanket "Do NOT attempt native Read, Grep, Glob, or **Bash** — they will be
denied" is wrong about **both `Bash` and `Read`** as of 2026-08-03, and its framing ("denied
by policy") is misleading for `Glob`, which is simply not present rather than policy-blocked.
Do not skip `Bash`, `Read`, `Edit`, or `Write` believing they are forbidden.

Only `Grep` is genuinely denied. Treating the generated block at face value causes real waste:
routing every file read through `ctx_read` when `Read` is available is harmless, but believing
`Bash` is denied leads to contorted workarounds for tasks that a single shell command answers.
The tool-priority stack in §1 still applies on the merits — prefer `ctx_*` for compression and
Serena for symbols — but prefer them because they are better here, not because the alternatives
are blocked.

Section 1's priority stack lists `Glob` first for directory listing and file finding. In
sessions where `Glob` has no schema, that entry is unactionable — fall through to
`ctx_glob` / `ctx_tree` rather than treating the stack as violated.

Upstream fix (not applied here): the generated wording belongs in
`github.com/yvgude/lean-ctx`; this table is the local workaround until then.

---
*Maintained at: `~/.dotfiles/ai/rules/tool-priority.md`*
