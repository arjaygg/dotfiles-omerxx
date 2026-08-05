---
name: explore
description: >
  Codebase exploration using Serena and LeanCtx — the correct first move instead of
  Bash grep/find/cat. Provides a decision tree and ready-to-run call templates that replace
  ad-hoc shell commands with structured, token-efficient exploration. Invoke proactively when
  you need to understand code before editing, find where something is defined, search for
  usages, or get a project overview. Triggers: "explore", "find", "search", "where is",
  "how does X work", "understand", "look for", "what calls", "show me", "navigate to".
version: 1.1.0
triggers:
  - explore
  - find symbol
  - where is
  - how does
  - search for
  - look for
  - what calls
  - show me the code
  - understand the codebase
  - navigate to
  - find usages
  - find references
---

# Explore — Codebase Navigation with Serena

**Replace grep/find/cat with structured Serena + LeanCtx calls.**
Every exploration task maps to a specific tool. Never fall back to Bash for codebase navigation.

Serena and LeanCtx are direct MCP servers. Independent calls go out as **parallel tool calls
in a single message** — Serena serialises internally, so they cannot race, and each extra
round-trip re-sends the whole growing context.

---

## Decision Tree — Pick Your Mode

```
What do you need?
│
├── Unfamiliar area / no specific target  →  MODE 0: Project Overview
│
├── Know a symbol name (function/class/type)?
│   ├── Want its definition               →  MODE 1: Find Symbol
│   └── Want all usages                  →  MODE 2: Find References
│
├── Know a file or directory path?        →  MODE 3: File/Dir Structure
│
├── Have a code pattern / text to find?  →  MODE 4: Pattern Search
│
└── Complex task (multiple of the above) →  MODE 5: Batch Explore
```

---

## MODE 0 — Project Overview (unfamiliar area)

Call `ctx_intent` with `{ query }` to let lean-ctx auto-select relevant files, and
`ctx_overview` with `{ task }` for the full project map. Issue both in one message.

---

## MODE 1 — Find Symbol Definition

`find_symbol` with `{ name_path_pattern: "SymbolName", depth: 1 }`.

**Tips:**
- `name_path_pattern: "methodName"` — finds any symbol with that name across all files
- `name_path_pattern: "ClassName/methodName"` — scoped to parent
- `name_path_pattern: "/ClassName/methodName"` — exact match only
- `depth: 0` — symbol only; `depth: 1` — include children (use for classes to get all methods)

---

## MODE 2 — Find All References / Usages

Two calls, and they must be sequential — the second needs the file path from the first:

1. `find_symbol` with `{ name_path_pattern: "SymbolName", depth: 0 }` to locate it.
2. `find_referencing_symbols` with `{ name_path: "SymbolName", relative_path: "path/to/file.go" }`
   — `relative_path` must be the file containing the definition.

---

## MODE 3 — File or Directory Structure

Independent; issue together in one message:

- `get_symbols_overview` with `{ relative_path: "path/to/file.go" }`
- `ctx_tree` with `{ path: "path/to/dir" }`
- `ctx_glob` with `{ pattern: "**/worker*.go", path: "." }` to find a file by name

**When to use each:**
- `get_symbols_overview` — before reading a source file; gives structure without full content
- `ctx_tree` — instead of `ls`; structured, token-efficient
- `ctx_glob` / `Glob` — instead of `find`; gitignore-aware filename matching

---

## MODE 4 — Pattern Search

`ctx_search` with:

```json
{
  "pattern": "YourPattern",
  "path": ".",
  "max_results": 50
}
```

Optional narrowing: `"include": "**/*.go"`, `"exclude": "vendor/**"`.

**Tips:**
- Use non-greedy `.*?` not `.*` in patterns spanning lines
- Scope with `path: "src/handlers"` or `include`/`exclude` globs to narrow the search

---

## MODE 5 — Batch Explore (multiple questions at once)

Combine modes when you'll need multiple things. Put every independent call in **one message**.

Example — understand a handler and its callers, once you already know the file path:

- `find_symbol` `{ name_path_pattern: "ProcessPayment", depth: 1 }`
- `find_referencing_symbols` `{ name_path: "ProcessPayment", relative_path: "src/payments/handler.go" }`
- `get_symbols_overview` `{ relative_path: "src/payments/handler.go" }`
- `ctx_glob` `{ pattern: "**/*payment*.go", path: "." }`

If you do *not* yet know the file path, MODE 2's two steps must run in order first.

---

## Anti-Patterns — What NOT to Do

| Instead of... | Use... |
|---|---|
| `Bash: grep -r "FuncName" .` | `find_symbol` or `ctx_search` |
| `Bash: find . -name "*.go"` | `ctx_glob` or `Glob` |
| `Bash: ls src/handlers/` | `ctx_tree` or `Glob` |
| `Bash: cat src/handler.go` | `get_symbols_overview` then `Read` with `limit/offset` |
| `Bash: head -50 file.go` | `Read` with `limit: 50` |
| Multiple sequential independent Serena calls | All of them in one message |
| `Grep` for a PascalCase identifier | `find_symbol` |

---

## LeanCtx Alternatives

When Serena is unavailable or for non-code files:

| Task | LeanCtx tool |
|---|---|
| Read file (token-efficient) | `ctx_read` `{ path, mode: "signatures" }` |
| Directory tree | `ctx_tree` `{ path: "." }` |
| Intent-driven exploration | `ctx_intent` `{ query: "..." }` |
| Project overview | `ctx_overview` `{ task: "..." }` |
| Dependency graph | `ctx_graph` `{ action: "related", file: "path/to/file" }` |

---

## Instructions

When this skill is invoked:

1. **Parse the user's request** to determine which mode applies (0–5)
2. **Run the template** — adapt symbol names, paths, patterns from the request
3. **Report findings** concisely: what was found, where it lives, who calls it
4. Do NOT issue independent calls in separate messages when one message would cover them
5. Do NOT fall back to Bash, Grep, or Glob for operations Serena can handle

**If Serena returns empty results:**
- Try a broader `name_path_pattern` (remove the class prefix)
- Try `ctx_search` with the name as a literal string
- Check that the project is activated — `initial_instructions` reports the active project
