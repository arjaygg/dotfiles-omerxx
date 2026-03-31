---
name: explore
description: >
  Codebase exploration using pctx/Serena and LeanCtx — the correct first move instead of
  Bash grep/find/cat. Provides a decision tree and ready-to-run batch templates that replace
  ad-hoc shell commands with structured, token-efficient exploration. Invoke proactively when
  you need to understand code before editing, find where something is defined, search for
  usages, or get a project overview. Triggers: "explore", "find", "search", "where is",
  "how does X work", "understand", "look for", "what calls", "show me", "navigate to".
version: 1.0.0
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

# Explore — Codebase Navigation with pctx/Serena

**Replace grep/find/cat with structured Serena + LeanCtx calls.**
Every exploration task maps to a specific tool. Never fall back to Bash for codebase navigation.

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

Use `LeanCtx.ctxIntent` to let the tool auto-select relevant files based on a natural language query.
Follow with `LeanCtx.ctxOverview` for the full project map.

```typescript
// mcp__pctx__execute_typescript
async function run() {
  const [intent, overview] = await Promise.all([
    LeanCtx.ctxIntent({ query: "YOUR QUERY HERE" }),
    LeanCtx.ctxOverview({ task: "YOUR QUERY HERE" }),
  ]);
  return { intent, overview };
}
```

---

## MODE 1 — Find Symbol Definition

```typescript
// mcp__pctx__execute_typescript
async function run() {
  const results = await Serena.findSymbol({
    name_path: "SymbolName",  // e.g. "HandleRequest" or "MyClass/myMethod"
    depth: 1,                 // 0 = symbol only, 1 = include children (e.g. class methods)
  });
  return results;
}
```

**Tips:**
- `name_path: "methodName"` — finds any symbol with that name across all files
- `name_path: "ClassName/methodName"` — scoped to parent
- `name_path: "/ClassName/methodName"` — exact match only
- `depth: 1` — include children (use for classes to get all methods)

---

## MODE 2 — Find All References / Usages

```typescript
// mcp__pctx__execute_typescript
async function run() {
  // Step 1: Locate the symbol first
  const sym = await Serena.findSymbol({ name_path: "SymbolName", depth: 0 });
  
  // Step 2: Find everything that calls/uses it
  const refs = await Serena.findReferencingSymbols({ name_path: "SymbolName" });
  
  return { definition: sym, references: refs };
}
```

---

## MODE 3 — File or Directory Structure

```typescript
// mcp__pctx__execute_typescript
async function run() {
  const [overview, listing] = await Promise.all([
    // Understand what symbols are in the file
    Serena.getSymbolsOverview({ relative_path: "path/to/file.go" }),
    // List what's in a directory
    Serena.listDir({ relative_path: "path/to/dir", recursive: false }),
  ]);
  return { overview, listing };
}
```

**When to use each:**
- `getSymbolsOverview` — before reading a source file; gives structure without full content
- `listDir` — instead of `ls`; structured, gitignore-aware
- `findFile` — instead of `find`; project-indexed search by filename

```typescript
// Find a file by name
async function run() {
  return await Serena.findFile({ file_mask: "worker*.go", relative_path: "." });
}
```

---

## MODE 4 — Pattern Search

```typescript
// mcp__pctx__execute_typescript
async function run() {
  return await Serena.searchForPattern({
    pattern: "YourPattern",           // Regex, DOTALL-enabled
    relative_path: ".",               // Scope: "." = whole project, or a subdir
    restrict_search_to_code_files: true,  // Skip non-code files
    context_lines_before: 2,
    context_lines_after: 2,
    // Optional: restrict by glob
    // include_pattern: "*.go",
    // exclude_pattern: "vendor/**",
  });
}
```

**Tips:**
- Use non-greedy `.*?` not `.*` in patterns spanning lines
- Set `restrict_search_to_code_files: false` to also search markdown, yaml, etc.
- Scope with `relative_path: "src/handlers"` to narrow the search

---

## MODE 5 — Batch Explore (multiple questions at once)

Combine modes when you'll need multiple things. **One `execute_typescript` call = one round trip.**

```typescript
// mcp__pctx__execute_typescript — example: understand a handler and its callers
async function run() {
  const [symbol, refs, fileStructure, relatedFiles] = await Promise.all([
    Serena.findSymbol({ name_path: "ProcessPayment", depth: 1 }),
    Serena.findReferencingSymbols({ name_path: "ProcessPayment" }),
    Serena.getSymbolsOverview({ relative_path: "src/payments/handler.go" }),
    Serena.findFile({ file_mask: "*payment*.go", relative_path: "." }),
  ]);
  
  return {
    symbol,
    calledBy: refs,
    fileStructure,
    relatedFiles,
  };
}
```

---

## Anti-Patterns — What NOT to Do

| Instead of... | Use... |
|---|---|
| `Bash: grep -r "FuncName" .` | `Serena.searchForPattern` or `Serena.findSymbol` |
| `Bash: find . -name "*.go"` | `Serena.findFile` or `Glob` |
| `Bash: ls src/handlers/` | `Serena.listDir` |
| `Bash: cat src/handler.go` | `Serena.getSymbolsOverview` then `Read` with `limit/offset` |
| `Bash: head -50 file.go` | `Read` with `limit: 50` |
| Multiple sequential Serena calls | One `mcp__pctx__execute_typescript` with `Promise.all` |
| `Grep` for a PascalCase identifier | `Serena.findSymbol` |

---

## LeanCtx Alternatives

When Serena is unavailable or for non-code files:

| Task | LeanCtx tool |
|---|---|
| Read file (token-efficient) | `LeanCtx.ctxRead({ path, mode: "signatures" })` |
| Read many files | `LeanCtx.ctxMultiRead({ paths: [...], mode: "map" })` |
| Directory tree | `LeanCtx.ctxTree({ path: "." })` |
| Intent-driven exploration | `LeanCtx.ctxIntent({ query: "..." })` |
| Project overview | `LeanCtx.ctxOverview({ task: "..." })` |
| Dependency graph | `LeanCtx.ctxGraph({ action: "related", file: "path/to/file" })` |

---

## Instructions

When this skill is invoked:

1. **Parse the user's request** to determine which mode applies (0–5)
2. **Run the batch template** — adapt symbol names, paths, patterns from the request
3. **Report findings** concisely: what was found, where it lives, who calls it
4. Do NOT run multiple sequential `execute_typescript` calls when one batch would cover it
5. Do NOT fall back to Bash, Grep, or Glob for operations Serena can handle

**If Serena returns empty results:**
- Try a broader `name_path` (remove the class prefix)
- Try `searchForPattern` with the name as a literal string
- Check if the project is indexed: run `Serena.getCurrentConfig()`
