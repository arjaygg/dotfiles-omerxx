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

Use `LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query } })` to let lean-ctx auto-select relevant files.
Follow with `LeanCtx.ctxOverview` for the full project map.

```typescript
// mcp__pctx__execute_typescript
async function run() {
  const [intent, overview] = await Promise.all([
    LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "YOUR QUERY HERE" } }),
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
    name_path_pattern: "SymbolName",  // e.g. "HandleRequest" or "MyClass/myMethod"
    depth: 1,                 // 0 = symbol only, 1 = include children (e.g. class methods)
  });
  return results;
}
```

**Tips:**
- `name_path_pattern: "methodName"` — finds any symbol with that name across all files
- `name_path_pattern: "ClassName/methodName"` — scoped to parent
- `name_path_pattern: "/ClassName/methodName"` — exact match only
- `depth: 1` — include children (use for classes to get all methods)

---

## MODE 2 — Find All References / Usages

```typescript
// mcp__pctx__execute_typescript
async function run() {
  // Step 1: Locate the symbol first
  const sym = await Serena.findSymbol({ name_path_pattern: "SymbolName", depth: 0 });
  
  // Step 2: Find everything that calls/uses it; relative_path must be the file containing the symbol
  const refs = await Serena.findReferencingSymbols({ name_path: "SymbolName", relative_path: "path/to/file.go" });
  
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
    LeanCtx.ctxTree({ path: "path/to/dir" }),
  ]);
  return { overview, listing };
}
```

**When to use each:**
- `getSymbolsOverview` — before reading a source file; gives structure without full content
- `LeanCtx.ctxTree` — instead of `ls`; structured, token-efficient
- `LeanCtx.ctxGlob` / `Glob` — instead of `find`; gitignore-aware filename matching

```typescript
// Find a file by name
async function run() {
  return await LeanCtx.ctxGlob({ pattern: "**/worker*.go", path: "." });
}
```

---

## MODE 4 — Pattern Search

```typescript
// mcp__pctx__execute_typescript
async function run() {
  return await LeanCtx.ctxSearch({
    pattern: "YourPattern", // Regex/text pattern
    path: ".",              // Scope: "." = whole project, or a subdir
    max_results: 50,
    // Optional: restrict by glob
    // include: "**/*.go",
    // exclude: "vendor/**",
  });
}
```

**Tips:**
- Use non-greedy `.*?` not `.*` in patterns spanning lines
- Scope with `path: "src/handlers"` or `include` / `exclude` globs to narrow the search

---

## MODE 5 — Batch Explore (multiple questions at once)

Combine modes when you'll need multiple things. **One `execute_typescript` call = one round trip.**

```typescript
// mcp__pctx__execute_typescript — example: understand a handler and its callers
async function run() {
  const [symbol, refs, fileStructure, relatedFiles] = await Promise.all([
    Serena.findSymbol({ name_path_pattern: "ProcessPayment", depth: 1 }),
    Serena.findReferencingSymbols({ name_path: "ProcessPayment", relative_path: "src/payments/handler.go" }),
    Serena.getSymbolsOverview({ relative_path: "src/payments/handler.go" }),
    LeanCtx.ctxGlob({ pattern: "**/*payment*.go", path: "." }),
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
| `Bash: grep -r "FuncName" .` | `Serena.findSymbol` or `LeanCtx.ctxSearch` |
| `Bash: find . -name "*.go"` | `LeanCtx.ctxGlob` or `Glob` |
| `Bash: ls src/handlers/` | `LeanCtx.ctxTree` or `Glob` |
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
| Directory tree | `LeanCtx.ctxTree({ path: "." })` |
| Intent-driven exploration | `LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "..." } })` |
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
- Try a broader `name_path_pattern` (remove the class prefix)
- Try `LeanCtx.ctxSearch` with the name as a literal string
- Check if the project is indexed: run `Serena.getCurrentConfig()`
