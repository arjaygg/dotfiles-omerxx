---
name: repomix
description: Packs the codebase (or a subset) into an AI-optimized compressed file using Repomix. Use when Claude needs full-repo or multi-package context for exploration, multi-file feature implementation, debugging, or agent-to-agent handoff. Invoked via /repomix or trigger phrases like "pack the repo", "compress codebase", "give Claude context".
triggers:
  - pack the repo
  - repomix
  - compress codebase
  - compress the repo
  - give Claude repo context
  - repo context
  - full codebase context
  - multi-file context
---

# Repomix — Pack Codebase for LLM Context

Compress your entire codebase (or a subset) into a single AI-friendly file using Tree-sitter structural extraction.
No external APIs — runs locally, respects `.gitignore`, includes token counting.

## When to Use

**TRIGGER** when the user's request contains:
- "pack the repo" / "repomix" / "compress codebase"
- "give Claude context" / "repo context"
- "I need full-package context for a multi-file feature"
- "debug across files" / "cross-file understanding"
- Explicit `/repomix` invocation

Good use cases for Repomix:
- **Session start:** New worktree, need codebase overview before diving into specific files
- **Multi-file feature:** Implementing a new transformer/service that touches 5+ files
- **Cross-file debugging:** Bug in FK resolution path spanning querybuilder, conversion, migration loading
- **Code review:** Full-repo architectural review before Claude suggests changes
- **Agent handoff:** Dev agent finishes implementation, passes compressed context to QA agent for test writing

**Do NOT use Repomix for:**
- Single-file edits (use Serena/LSP directly)
- When you only need to edit one or two specific files (too broad; use Read tool on exact files)
- Security-sensitive code (always verify `--exclude` patterns before packing)

## Key Feature: `--compress`

Repomix's `--compress` flag uses **Tree-sitter** to extract only structural elements (function signatures, type definitions, interface declarations) and strip function bodies. For auc-conversion's 209 Go files:
- **Full dump:** ~300K+ tokens (exceeds Claude's 200K window)
- **Compressed:** ~40-80K tokens (fits comfortably, preserves structure)

## Instructions

### 1. Check Repomix is available

```bash
if ! command -v repomix &>/dev/null; then
    echo "Installing Repomix..."
    brew install repomix
fi
repomix --version
```

If installation fails, inform the user and stop.

### 2. Determine scope

**Full repo:**
```bash
repomix --compress --output repomix-output.xml
```
Uses `.repomixignore` and `repomix.config.json` defaults.

**Specific packages (focused context):**
```bash
repomix --compress \
  --include "pkg/model/**,pkg/contract/**,pkg/conversion/**" \
  --output transformer-context.xml
```

**Exclude tests (lighter output):**
```bash
repomix --compress \
  --ignore "**/*_test.go" \
  --output repomix-output.xml
```

### 3. Run and capture token count

```bash
repomix --compress --output repomix-output.xml
```

Repomix prints per-file and **total token count** at the end. Example:
```
✓ Repository packed successfully
Total tokens: 68,432
Output file: repomix-output.xml
```

### 4. Verify token budget

- **Target:** < 180K tokens (leaves room for Claude's own response and multi-turn conversation)
- **If over:** Narrow the `--include` scope, add patterns to `.repomixignore`, or run with `--ignore "**/*_test.go"`
- **Report:** Tell the user the token count and output file path

### 5. MCP path (preferred in Claude Code)

If `@repomix` MCP is registered in `.mcp.json`, Claude Code will call it automatically:

```
User: "@repomix show me the conversion and model packages"
→ Claude Code queries Repomix MCP directly
→ Returns compressed context without manual file generation
```

For manual execution or outside Claude Code, reference the output file:
```
User: [uploads repomix-output.xml] "Using this context, implement a new transformer..."
```

## Examples

### Example 1: Session Start — Full Repo Overview

**User:** "Pack the repo so I can understand the architecture"

```bash
# Run skill
repomix --compress --output repomix-output.xml

# Output:
# ✓ Repository packed successfully
# Total tokens: 65,204
# Output file: repomix-output.xml

# Tell user
echo "Repomix complete: 65,204 tokens. Ready for Claude review."
```

**User then:** "Using this context, explain the data flow from worker polling to ETL transformation"
→ Claude answers with full-repo awareness

---

### Example 2: Multi-file Feature — Transformer Implementation

**User:** "I'm implementing a new transformer for TableFoo. Pack the relevant packages."

```bash
# Focused pack: model + contract + conversion
repomix --compress \
  --include "pkg/model/**,pkg/contract/**,pkg/conversion/**" \
  --output transformer-context.xml

# Output:
# ✓ Repository packed successfully
# Total tokens: 42,156
# Output file: transformer-context.xml
```

**User then:** "Here's the compressed context. Implement a new transformer for TableFoo following existing patterns."
→ Claude identifies the transformer pattern → generates all 5 files (model, transformer, impl, test, route)

---

### Example 3: Cross-file Debug

**User:** "There's a bug in the FK resolution. Debug the path from DetermineLoadingSequence through querybuilder."

```bash
# Pack only the relevant files
repomix --compress \
  --include "pkg/repo/querybuilder/**,pkg/conversion/conversion.go,pkg/model/migration_loading_sequence.go" \
  --output debug-context.xml

# Output:
# ✓ Repository packed successfully
# Total tokens: 18,943
# Output file: debug-context.xml
```

**User then:** "Trace the data flow in this subset. Find where AccountID references are resolved."
→ Claude traces without needing 3 separate Read tool calls

---

### Example 4: Dev → QA Agent Handoff

**Dev Agent context:**
```bash
# At end of implementation session, narrow pack to changed packages
repomix --compress \
  --include "pkg/conversion/**,pkg/model/transformers/**" \
  --output handoff-context.xml

# Add to plans/active-context.md:
# handoff: handoff-context.xml (conversion + transformers, post-implementation)
```

**QA Agent session start:**
```bash
# Read plans/active-context.md → find handoff-context.xml
# Load it and query: "Using this context, write mutation-verified tests for the new transformer"
→ QA agent understands structure, writes tests with zero cold-start Serena reads
```

---

## Configuration Files

### `.repomixignore` (project root)

```
_bmad-output/
plans/
docs/drafts/
.trees/
```

### `repomix.config.json` (project root)

```json
{
  "output": {
    "filePath": "repomix-output.xml",
    "style": "xml",
    "compress": true,
    "showLineNumbers": false,
    "showFileSummary": true
  },
  "ignore": {
    "customPatterns": [
      "_bmad-output/**",
      "plans/**",
      "docs/drafts/**",
      "db/migrations/**",
      ".trees/**"
    ]
  }
}
```

### `.gitignore` entry

```
repomix-output.xml
transformer-context.xml
handoff-context.xml
debug-context.xml
```

(Generated artifacts, never committed)

## Relationship to Other Tools

| Tool | Repomix Role |
|---|---|
| **Serena** | Serena does precise symbol navigation (find references, rename, semantic search). Repomix gives Claude a snapshot of multiple packages at once. Use Serena for targeted navigation; use Repomix for multi-file context. |
| **LeanCtx (ctx_read)** | LeanCtx reads individual files with compression modes. Repomix packs the entire repo at once. Complementary: use LeanCtx for single-file reads, Repomix for multi-package exploration. |
| **CodeQL** | CodeQL enforces exhaustive architectural rules (batch, zero false positives). Repomix enables fast LLM architectural review. Use together: Repomix for fast iteration, CodeQL for CI enforcement. |

## Token Counting

Repomix automatically counts tokens:
- Per-file breakdown (shown during pack)
- **Total tokens** (shown at end) — this is what matters for Claude's context window
- Recommend: keep total < 180K to leave room for Claude's reasoning and conversation

If token count is too high:
1. Use `--include` to narrow scope to specific packages
2. Add patterns to `.repomixignore`
3. Use `--ignore "**/*_test.go"` to exclude test files
4. Rerun and check token count again
