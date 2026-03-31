# Tool Priority Rules

Universal tool routing rules for all projects on this machine.
For Serena/pctx-specific rules, see `pctx-unified-rules.md`.

## Tool Routing Table

| Intent | Use | Never use in Bash |
|---|---|---|
| Read a file | `Read` (with `limit`/`offset` for large or source files) | `cat`, `head`, `tail` |
| Search file contents | `Grep` (ripgrep-backed, gitignore-aware) | `grep`, `rg` |
| Find files by name | `Glob` | `find`, `ls` |
| List directory contents | `Glob` or `Bash(ls -la)` for symlink inspection | `ls` (without `-l`) |
| Edit a file | `Edit` (after reading it first) | `sed`, `awk` |
| Create a new file | `Write` | `echo >`, `cat <<EOF >` |

## Source Code Files

- `.go`, `.ts`, `.py`, `.rs`, `.java` files: **always** use `Read` with `limit`/`offset` to read specific sections, not the whole file
- If a project has Serena configured (`.serena/` exists): prefer `Serena.getSymbolsOverview` first, then `Read` with `limit`/`offset` for the specific symbol
- Lock files (`package-lock.json`, `yarn.lock`, `Cargo.lock`, `pnpm-lock.yaml`, `composer.lock`, `Gemfile.lock`): **never** read directly. Use `Grep` to search for specific entries.

## Bash: Allowed vs Blocked

**Allowed in Bash:** `git *`, `make *`, `docker *`, `brew *`, `npm/bun/pnpm run *`, test runners, build tools, `ls -l*` (symlink inspection), any command that has no dedicated tool equivalent.

**Blocked in Bash (enforced by hooks and deny patterns):**
`cat`, `head`, `tail`, `grep`, `rg`, `find`, `ls` (without `-l`), `sed` (for file editing), `awk` (for file editing).

## Batching Independent Operations

When you need 2+ independent Read/Grep/Glob calls, fire them in **parallel** (multiple tool calls in one message).

When you need 2+ Serena/pctx operations, batch into one `mcp__pctx__execute_typescript` call:

```typescript
// WRONG: 3 sequential tool calls
Serena.getSymbolsOverview("file.go")
Serena.findSymbol("HandleRequest")
Serena.searchForPattern("TODO")

// RIGHT: 1 batched call
const [overview, symbol, todos] = await Promise.all([
  Serena.getSymbolsOverview("file.go"),
  Serena.findSymbol("HandleRequest"),
  Serena.searchForPattern("TODO")
]);
return { overview, symbol, todos };
```

## Edit Safety

Always `Read` a file before using `Edit` on it. Editing a file you haven't read risks blind changes. Hooks enforce this.

---
*Maintained at: `~/.dotfiles/ai/rules/tool-priority.md`*
