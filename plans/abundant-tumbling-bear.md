# Plan: Universal Agent Constitution Loading from Dotfiles

## Context

The dotfiles repo is intended to be the **single source of truth** for all AI agent constitution files. The architecture has two layers:

1. **User-global** — rules that apply to every project on this machine
2. **Project-scoped** — rules specific to the dotfiles repo itself

**The Problem:**
The Tool Priority Stack (Serena > native tools > Bash), Batching Rule, and Serena API Convention are defined in `AGENTS.md`, which is only loaded when working inside the dotfiles repo. These rules are universal — pctx/Serena is configured for all projects via dotfiles MCP configs — but agents in other repos never see them.

Additionally, `context-and-compaction.md` and `global-developer-guidelines.md` exist in `ai/rules/` but are not imported by any user-global adapter, making them dead weight.

**Intended Outcome:**
Every agent (Claude, Gemini, Codex) loads ALL universal constitution rules from `ai/rules/` regardless of which project they're working in.

---

## Architecture After Fix

```
ai/rules/
├── agent-user-global.md           ← working style, git safety, file discipline (exists)
├── tool-priority.md               ← NEW: tool priority stack + batching rule + Serena convention
├── context-and-compaction.md      ← session discipline, Claude hooks (exists)
├── global-developer-guidelines.md ← worktree conventions, AI hub structure (exists)
└── agent-universal.md             ← NEW: combined file for Codex (single-file limitation)

User-global adapters load:
  Claude:  agent-user-global + tool-priority + global-developer-guidelines + context-and-compaction
  Gemini:  agent-user-global + tool-priority + global-developer-guidelines
  Codex:   agent-universal (combined: agent-user-global + tool-priority + global-developer-guidelines)
```

---

## Key Insight: Three Loading Mechanisms, One Source

| Category | Agents | Mechanism | Staleness risk |
|---|---|---|---|
| **@-import** | Claude, Gemini | `@` a list of source files at runtime | None — reads source directly |
| **Single-file** | Codex | One `model_instructions_file` path | Eliminated by merging into existing working file |
| **Project-root** | Cursor, Windsurf | `.cursorrules`/`.windsurfrules` | Verify `~/` scope works before investing |

`ai/rules/` files are the **source of truth**. Where generation is required, it is protected by a **pre-commit hook** that auto-regenerates before any commit.

---

## Steps

### 1. Create `ai/rules/tool-priority.md`

Extract verbatim from `AGENTS.md` the three universal sections:
- **Tool Priority Stack** (the full table: DIRECTORY LISTING, SEARCHING CODE, etc.)
- **Batching Rule** (the "Before any tool call…" block)
- **Serena API Convention** (the camelCase vs snake_case table)

These are universal because pctx/Serena is configured for all projects via dotfiles MCP configs.

### 2. Update `.claude/CLAUDE.md`

```markdown
@../ai/rules/agent-user-global.md
@../ai/rules/tool-priority.md
@../ai/rules/global-developer-guidelines.md
@../ai/rules/context-and-compaction.md
```

### 3. Update `.gemini/GEMINI.md`

```markdown
@../ai/rules/agent-user-global.md
@../ai/rules/tool-priority.md
@../ai/rules/global-developer-guidelines.md
```

(`context-and-compaction` is Claude hook-specific — skip for Gemini)

### 4. Handle Codex — no generated file needed

Codex already loads `agent-user-global.md` via `model_instructions_file` and `~/` expansion is confirmed working. Instead of creating a new combined file, append the tool priority content **into `agent-user-global.md`** directly (or keep it as a separate `@`-imported section in comments).

> **Why**: avoids introducing any generated file for Codex. One source file, already loading, no new staleness surface.

No change to `.codex/config.toml` needed.

### 5. Handle Cursor and Windsurf — verify scope first

**Before generating `.cursorrules`/`.windsurfrules`**: confirm that Cursor actually reads `~/.cursorrules` as a user-global rule (Cursor's documented scope for `.cursorrules` is project root, not `~`). If `~/` scope doesn't work, skip Cursor/Windsurf for this PR and track as a separate investigation.

If `~/` scope IS confirmed: create `ai/scripts/generate-constitutions.sh` and add a **pre-commit hook** that auto-runs it. This prevents stale generated files from ever being committed.

```bash
# .claude/hooks/pre-commit-generate-constitutions.sh (or add to existing pre-commit)
bash "$(git rev-parse --show-toplevel)/ai/scripts/generate-constitutions.sh"
git add .cursorrules .windsurfrules
```

If `~/` scope is NOT confirmed: leave `.cursorrules`/`.windsurfrules` as-is and note Cursor/Windsurf as needing a different mechanism (e.g., `.cursor/rules/` MDC directory with symlinks).

### 6. Update `AGENTS.md`

Remove: Tool Priority Stack, Batching Rule, Serena API Convention sections.
Replace with one-line reference:

> Tool priority, batching, and Serena conventions are universal — see `ai/rules/tool-priority.md`.

Keep: Repo Purpose, Precedence, Working Rules, Branch Workflow, Project Structure, MCP Gateway, plans/ convention.

### 7. Update `validate-agent-guidance.sh`

Add checks:
- `ai/rules/tool-priority.md` exists
- `agent-user-global.md` contains tool priority content (grep for "Tool Priority Stack")
- `.claude/CLAUDE.md` imports all 4 rules files
- `.gemini/GEMINI.md` imports tool-priority.md and global-developer-guidelines.md
- If `ai/scripts/generate-constitutions.sh` exists: hash check that `.cursorrules`/`.windsurfrules` match current generation

### 8. Update `docs/agent-configuration-architecture.md`

Update Tool Loading Model table. Add a **Generated Artifacts** section explaining the generation script and when to re-run it.

### 9. Record the decision

- Append ADL-005 to `plans/decisions.md`
- Create `decisions/0003-universal-constitution-loading.md`

### 10. Cleanup

- Delete `plans/session-handoff.md` (already read at session start)

---

## Files Modified

| File | Action |
|------|--------|
| `ai/rules/tool-priority.md` | **CREATE** — extracted from AGENTS.md |
| `ai/rules/agent-user-global.md` | Update — append tool priority content (Codex reads this already) |
| `.claude/CLAUDE.md` | Update — add 3 `@` imports |
| `.gemini/GEMINI.md` | Update — add 2 `@` imports |
| `AGENTS.md` | Update — remove 3 extracted sections, add reference |
| `.claude/scripts/validate-agent-guidance.sh` | Update — add new checks |
| `docs/agent-configuration-architecture.md` | Update — loading model table |
| `plans/decisions.md` | Update — append ADL-005 |
| `decisions/0003-universal-constitution-loading.md` | **CREATE** — durable ADR |
| `plans/session-handoff.md` | **DELETE** |
| `ai/scripts/generate-constitutions.sh` + `.cursorrules`/`.windsurfrules` | **CONDITIONAL** — only if Cursor `~/` scope is verified |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `.cursorrules` current content not fully in `global-developer-guidelines.md` | Silently drop worktree-specialist content | Diff `.cursorrules` vs `global-developer-guidelines.md` before regenerating; merge any gaps first |
| Generated files go stale when source files change | Codex/Cursor/Windsurf get outdated constitution | `validate-agent-guidance.sh` must compare content hash of generated file vs what would be generated; add pre-commit hook to auto-regenerate |
| Codex `~/` path expansion untested | Codex silently loads nothing | Test immediately after `.codex/config.toml` change; the handoff flagged this as pending |
| `generate-constitutions.sh` not called on fresh machine | Stow symlinks stale generated files | Wire script into `setup.sh` after the `stow .` step |
| Gemini multiple `@` imports untested | Gemini gets only some rules | Verify by asking Gemini (in a non-dotfiles repo) to describe the tool priority stack after the change |

---

## Verification

1. **Validate script**: `bash .claude/scripts/validate-agent-guidance.sh` → all checks pass
2. **Claude Code** (in a non-dotfiles repo): Open Claude, ask it to describe the tool priority stack — it should cite Serena/pctx rules even outside the dotfiles project
3. **Gemini**: Same test in a different project
4. **Codex**: Verify `model_instructions_file` file loads without error and contains Serena rules

---

## Branch

Use stack workflow — create a branch `feat/universal-constitution-loading` from `main`.
