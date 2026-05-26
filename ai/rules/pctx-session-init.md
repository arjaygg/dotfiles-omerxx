# pctx Session Init

This rule applies to all projects that use pctx (Serena + LeanCtx + Repomix + Qmd).
pctx is a user-installed tool (`~/.cargo/bin/lean-ctx`), not a project dependency.

## When This Applies

When a `.serena/` config dir is present in the project tree and
`~/.config/pctx/pctx.json` exists.

## Required Init Sequence

**Before any project file access** (Read/Grep/Glob/Serena), run this three-step sequence:

**Step 1:** Call `mcp__pctx__list_functions` to unlock the session init gate.

**Step 2:** Run this init batch via `mcp__pctx__execute_typescript`:

```typescript
async function run() {
  await Promise.all([
    Serena.initialInstructions(),
    LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "<describe your task here>" } })
  ]);
}
```

**Step 3:** Write `plans/pctx-functions.md` with today's date (via the Write tool):

```
# pctx functions reference
date: YYYY-MM-DD
```

This file must exist with today's date for the pre-tool gate to unlock.

## Why Each Step Matters

- `list_functions` → sets the session init temp flag (`/tmp/.claude-serena-init-*`)
- `Serena.initialInstructions()` → loads project-specific Serena memories and config
- `LeanCtx.ctxCall({ name: "ctx_intent" })` → indexes live project context; required to unlock Grep
- `plans/pctx-functions.md` → file-based gate that survives compaction restarts

## Skip Condition

Skip this ONLY if `plans/pctx-functions.md` already exists and was written today.
The pre-tool gate auto-detects this and will not re-block.
