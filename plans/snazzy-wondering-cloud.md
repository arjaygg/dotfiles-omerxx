# Serena Enforcement Improvements: auc-conversion

**Date:** 2026-04-02  
**Project:** `/Users/axos-agallentes/git/auc-conversion`  
**Goal:** Add concrete Serena best-practice rules to AGENTS.md, CLAUDE.md, and hooks

---

## Context

The `auc-conversion` project has a solid governance layer (AGENTS.md, CLAUDE.md, 4 hooks, architecture validator) but is missing explicit Serena usage rules. Agents working in this project know to use Serena but have no guidance on *how* — which tools to use in what order, what to avoid, and what the project-specific quirks are. This plan adds targeted enforcement.

---

## What's Missing Today

| Gap | Impact |
|---|---|
| No Serena tool priority rules in AGENTS.md | Agents read full files instead of using `getSymbolsOverview` |
| No `restrict_search_to_code_files: true` mandate | Pattern searches return `go.sum` noise |
| No dot-directory workaround documented | `findSymbol` silently fails on `.serena/`, `.claude/` |
| No memory-first rule | Agents re-discover things already captured in 40+ memories |
| No session start ritual for Serena | `START_HERE.md` exists but is never mentioned in AGENTS.md |
| No pctx batching guidance | Sequential Serena calls waste round-trips and tokens |
| No hook to catch direct file reads that have symbolic alternatives | Agents use `Read`/`cat` when `getSymbolsOverview` would suffice |

---

## Changes to Make

### 1. `AGENTS.md` — Add Serena Section

**Add after the existing "Key Files" section:**

```markdown
## Serena MCP Usage

Serena is configured for this project. Use it as the **primary tool for all code navigation and symbol editing**. 

### Session Start

Before any code work, run in order:
1. `Serena.listMemories()` — scan what's available  
2. `Serena.readMemory({ name: "START_HERE" })` — get routed to the right context  
3. `Serena.readMemory({ name: "START_HERE_story_4_2" })` — active sprint state  

### Tool Priority (strictly ordered)

| Task | Use | Never use |
|---|---|---|
| Explore a file | `getSymbolsOverview` | `Read` for analysis, `cat` |
| Find a symbol | `findSymbol` | `grep`, `rg` |
| Search by pattern | `searchForPattern` (with `restrict_search_to_code_files: true`) | raw `grep` |
| Impact analysis | `findReferencingSymbols` | manual search |
| Replace a method | `replaceSymbolBody` | `Edit` for full-body replacements |
| Rename a symbol | `renameSymbol` | manual multi-file edits |
| Project knowledge | `readMemory` | re-reading source to re-derive known facts |

**Never read a full file for analysis** when `getSymbolsOverview` or `findSymbol` can provide the needed information.

### Known Quirks

- `findSymbol` **fails silently** on dot-directories (`.serena/`, `.claude/`, `.mcp.json`) — use `readMemory()` or the `Read` tool instead
- Always add `restrict_search_to_code_files: true` to `searchForPattern` — otherwise `go.sum` floods results
- If gopls LSP times out: call `Serena.restartLanguageServer()` — do not retry the failed call directly

### Memory Naming (when writing new memories)

- `architecture/<topic>` — cross-cutting decisions  
- `story_<N>_<sprint>/<topic>` — sprint-specific context  
- `workflows/<process>` — repeatable processes  

Do not duplicate to local markdown what is already in `.serena/memories/`.

### Batching with pctx

Fire all independent Serena calls in a single `Promise.all()` via `mcp__pctx__execute_typescript`. Never make sequential Serena calls when parallel is possible.
```

**Critical files reference to add (augment existing list):**

```markdown
- `pkg/contract/contract.go` — QueryBuilder, ValueBuilder, Tracer interfaces
- `pkg/repo/source_repo.go` — SourceRepository (pattern for all repos)
- `pkg/app/worker/worker.go` — Worker struct (ETL orchestration)
- `pkg/conversion/conversion_internal_nofk.go` — ETL engine (no-FK path)
- `.serena/memories/START_HERE.md` — Serena session routing entry point
```

---

### 2. `CLAUDE.md` — Add Claude-Specific Serena Rules

**Add after existing content:**

```markdown
## Serena Tool Rules (Claude-Specific)

These supplement AGENTS.md. Claude Code adds pctx batching as the preferred multi-call pattern.

### Mandatory tracing pattern

Every new public method in this codebase requires:
```go
func (r *Repo) MethodName(ctx context.Context, ...) (..., err error) {
    ctx, span, err := r.tracer.StartSpanWithAttributes(ctx, map[string]interface{}{
        "operation": "MethodName",
    }, "Repo.MethodName")
    defer func() { span.End(err) }()
}
```
Before writing a new method, find an existing one with `findSymbol` and copy the pattern.

### Pre-edit ritual

Before any edit to `pkg/`:
1. `getSymbolsOverview` on the target file
2. `findReferencingSymbols` on the symbol being changed
3. Check if the change violates architecture rules (domain layer imports infra = blocked)

### Read vs Serena decision

- Use `Read` only when you intend to `Edit` the file (requires reading first per tool rules)
- Use `Serena.getSymbolsOverview` for understanding structure
- Use `Serena.findSymbol` with `include_body: true` for reading a specific method
```

---

### 3. `.claude/hooks/user-prompt-submit.sh` — Add Serena Reminder

**Add to the existing hook script (after existing reminders):**

```bash
# Serena memory reminder — prompt if START_HERE hasn't been accessed this session
SERENA_MEMORIES_DIR="$(pwd)/.serena/memories"
if [ -d "$SERENA_MEMORIES_DIR" ]; then
  echo ""
  echo "── Serena ───────────────────────────────────────"
  echo "📚 Memory system active. Start with:"
  echo "   Serena.readMemory({ name: \"START_HERE\" })"
  echo "   then: readMemory({ name: \"START_HERE_story_4_2\" })"
  echo "   Always: restrict_search_to_code_files: true"
  echo "─────────────────────────────────────────────────"
fi
```

---

### 4. `.claude/hooks/post-tool-use.sh` — Warn on Full File Reads of Key Files

**Add to existing post-tool-use hook:**

```bash
# Warn when agent reads a large Go file that has Serena alternatives
if [ "$CLAUDE_TOOL_NAME" = "Read" ] && [[ "$CLAUDE_TOOL_INPUT" == *"pkg/"* ]]; then
  LINES=$(wc -l < "$CLAUDE_TOOL_INPUT" 2>/dev/null || echo 0)
  if [ "$LINES" -gt 100 ]; then
    echo "⚠️  SERENA HINT: $CLAUDE_TOOL_INPUT has $LINES lines."
    echo "   Prefer: Serena.getSymbolsOverview or Serena.findSymbol"
    echo "   Only use Read if you plan to Edit this file."
  fi
fi
```

---

### 5. `.claude/hooks/session-start.sh` — Add Serena Memory Inventory

**Add to existing session start output:**

```bash
# Show Serena memory count to prompt agent to use them
MEMORIES_COUNT=$(find "$(pwd)/.serena/memories" -name "*.md" ! -path "*/_archive/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$MEMORIES_COUNT" -gt 0 ]; then
  echo ""
  echo "── Serena Memories ──────────────────────────────"
  echo "📚 $MEMORIES_COUNT memories available."
  echo "   First step: Serena.readMemory({ name: \"START_HERE\" })"
  echo "─────────────────────────────────────────────────"
fi
```

---

## Files to Modify

| File | Change |
|---|---|
| `AGENTS.md` | Add full "Serena MCP Usage" section + critical files list additions |
| `CLAUDE.md` | Add "Serena Tool Rules (Claude-Specific)" section with tracing pattern + pre-edit ritual |
| `.claude/hooks/user-prompt-submit.sh` | Add Serena memory reminder block |
| `.claude/hooks/post-tool-use.sh` | Add large-file read warning |
| `.claude/hooks/session-start.sh` | Add memory inventory count display |

---

## What NOT to Change

- Architecture validator hook — already enforces structural rules; Serena usage is a different concern
- `settings.json` — no tool permissions changes needed; Serena is already allowed
- `.mcp.json` — already has Serena configured correctly
- `.serena/memories/` — do not add files here; this is Serena's territory, not governance docs

---

## Verification

After implementing:

1. Start a new Claude Code session in `auc-conversion`
2. Session start hook should show Serena memory count
3. Prompt hook should show `START_HERE` reminder on first message
4. Try `Read pkg/app/worker/worker.go` (>100 lines) — post-tool-use should warn with Serena alternative
5. Try `findSymbol` on `.serena/memories/START_HERE.md` — AGENTS.md quirk section should be consulted
6. Run `make pr-check` after a change — confirm no regressions from hook additions
