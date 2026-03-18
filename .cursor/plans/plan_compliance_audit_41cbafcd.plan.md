---
name: Plan Compliance Audit
overview: Audit the executed "Balanced Plan" against official 2026 documentation from Anthropic, Google (Gemini CLI), Cursor, OpenAI (Codex), and Windsurf. Identify compliance gaps, misalignments, and improvement opportunities.
todos:
  - id: fix-windsurf-ignore
    content: Rename .windsurfignore to .codeiumignore (Windsurf's actual ignore filename per official docs)
    status: pending
  - id: fix-gemini-import
    content: Update GEMINI.md to use @AGENTS.md import syntax instead of text instruction; add AGENTS.md to Gemini settings.json context.fileName
    status: pending
  - id: fix-claude-import
    content: Update CLAUDE.md to use @AGENTS.md import syntax instead of text instruction
    status: pending
  - id: fix-claude-rules
    content: "Create .claude/rules/ with path-scoped rules (rust-standards.md, testing.md) using paths: frontmatter"
    status: pending
  - id: fix-windsurf-rules
    content: Update .windsurf/rules/ files to match slimmed content
    status: pending
  - id: fix-cursor-descriptions
    content: Improve description fields on Apply Intelligently rules for better activation reliability
    status: pending
  - id: verify-codexignore
    content: Verify if .codexignore is actually read by Codex CLI; document findings
    status: pending
isProject: false
---

# Compliance Audit: Context Optimization Plan vs. Official Documentation

## Research Sources Consulted

- **Claude Code**: [docs.anthropic.com/claude-code/memory](https://docs.anthropic.com/en/docs/claude-code/memory), [hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks), [hooks guide](https://docs.anthropic.com/en/docs/claude-code/hooks-guide)
- **Cursor**: [cursor.com/docs/context/rules](https://cursor.com/docs/context/rules) (official rules docs, March 2026)
- **Gemini CLI**: [gemini-cli docs: GEMINI.md](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html), [ignoring files](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-ignore.html), [hooks](https://geminicli.com/docs/hooks/)
- **Codex**: [developers.openai.com/codex/guides/agents-md](https://developers.openai.com/codex/guides/agents-md), [advanced config](https://developers.openai.com/codex/config-advanced)
- **Windsurf**: [docs.windsurf.com/cascade/memories](https://docs.windsurf.com/windsurf/cascade/memories), [windsurf-ignore](https://docs.windsurf.com/context-awareness/windsurf-ignore)
- **Community**: SmartScope (5x AGENTS.md optimization), PromptXL (Cursor Rules 2026), DatalakehouseHub (Gemini context strategies)

---

## COMPLIANT (No Changes Needed)

### 1. AGENTS.md Structure -- COMPLIANT

- Official Codex docs recommend **under 50 lines** for project-layer AGENTS.md. Ours is **47 lines** (perfect).
- Modular `docs/standards/` pattern aligns with OpenAI's "Progressive Disclosure" and "Three-Layer Hierarchy" patterns.
- Safety kernel (ALWAYS/ASK/NEVER) is inline, matching the principle that critical guardrails should not be deferred.

### 2. CLAUDE.md Size -- COMPLIANT

- Anthropic docs explicitly say: **"target under 200 lines per CLAUDE.md file"**. Ours is **28 lines** (excellent).
- The `@path/to/import` syntax is available if we ever need to pull in more context on demand.

### 3. GEMINI.md -- COMPLIANT

- Google docs confirm GEMINI.md loads at every session and supports **hierarchical context** and `**@file.md` imports**.
- Our 15-line file is well within efficient bounds.
- The `/compress` instruction guidance aligns with the official `/compress [instruction]` feature.

### 4. Cursor Rule Tiering -- COMPLIANT

- Official Cursor docs (March 2026) confirm four modes: `Always Apply`, `Apply Intelligently`, `Apply to Specific Files`, `Apply Manually`.
- Our Tier 1 rules (`alwaysApply: true`) for guardrails and security match the "Always Apply" pattern.
- Our Tier 2 rules (`alwaysApply: false` with `description`) match the "Apply Intelligently" pattern.
- Official guidance: **"Keep rules under 500 lines"**. All our rules are under 30 lines each.

### 5. Cursor Ignore Files -- COMPLIANT

- `.cursorignore` uses gitignore syntax as documented.
- Conservative exclusions (build artifacts, lockfiles, logs, IDE internals) match best practices.

### 6. Codex AGENTS.md Discovery -- COMPLIANT

- Codex walks from project root to current directory, includes at most one file per directory, stops at `project_doc_max_bytes` (32KB default). Our lean 47-line AGENTS.md is well within limits.

---

## GAPS FOUND -- Fixes Needed

### Gap 1: Windsurf Ignore File Name is Wrong

**Issue**: We created `.windsurfignore`, but Windsurf uses `**.codeiumignore`** (not `.windsurfignore`).

- Official docs: *"You can add a `.codeiumignore` file to your repo root, with the same syntax as `.gitignore`"*
- Our `.windsurfignore` file is **inert** -- Windsurf won't read it.
**Fix**: Rename `.windsurfignore` to `.codeiumignore`, or create `.codeiumignore` as the canonical file.

### Gap 2: Gemini CLI Supports `@import` Syntax in GEMINI.md

**Issue**: Our GEMINI.md says "Read `AGENTS.md` first" but doesn't use the official `@AGENTS.md` import syntax.

- Official docs: *"You can break down large GEMINI.md files into smaller components using the `@file.md` syntax."*
- Using `@AGENTS.md` would **automatically inline** the AGENTS.md content into Gemini's context, rather than hoping the model reads it.
**Fix**: Replace "Read `AGENTS.md` first." with `@AGENTS.md` import syntax.

### Gap 3: Gemini CLI Can Load AGENTS.md Natively

**Issue**: Gemini supports configuring fallback filenames via `settings.json`:

```json
{ "context": { "fileName": ["AGENTS.md", "GEMINI.md"] } }
```

This means AGENTS.md can be auto-loaded by Gemini alongside GEMINI.md without manual import.
**Fix**: Add `AGENTS.md` to Gemini's `context.fileName` list in `.gemini/settings.json`.

### Gap 4: Claude Code Supports `@path` Imports in CLAUDE.md

**Issue**: Our CLAUDE.md says "Read `AGENTS.md` first" as a text instruction. Claude Code supports `@AGENTS.md` import syntax that would **automatically inline** the AGENTS.md content.

- Official docs: *"CLAUDE.md files can import additional files using `@path/to/import` syntax. Imported files are expanded and loaded into context at launch."*
**Fix**: Replace the text "Read `AGENTS.md` first." with `@AGENTS.md` import.

### Gap 5: Claude Code Has Path-Scoped `.claude/rules/` (Not Used)

**Issue**: Claude Code now supports `.claude/rules/*.md` with `paths:` frontmatter for file-scoped rules. We're not using this feature.

- Official docs: Rules with `paths: ["src/**/*.rs"]` frontmatter only load when Claude works with matching files.
- This mirrors Cursor's glob-based rule scoping but for Claude Code.
**Fix**: Consider creating `.claude/rules/rust-standards.md` with `paths: ["src/**/*.rs"]` frontmatter, and `.claude/rules/testing.md` with `paths: ["tests/**/*.rs"]` to reduce always-on noise in Claude Code too.

### Gap 6: "Apply Intelligently" Rules Have Known Reliability Issues

**Issue**: Community reports (Cursor forum) indicate that `alwaysApply: false` rules with descriptions **may not reliably activate**. The agent may ignore them.

- This affects our Testing, SOLID, OOP, and Task Routing rules.
**Fix**: For critical agent-requested rules (Testing, Security), ensure the `description` field is very explicit about when to use them. Add a fallback: the `AGENTS.md` references to `docs/standards/` serve as a secondary discovery path. Monitor in Phase 4.

### Gap 7: `.windsurf/rules/` Files Not Updated After Slimming

**Issue**: We updated `.cursor/rules/` but the old `.windsurf/rules/agent-guardrails.md` (1873 bytes) and `.windsurf/rules/rust-standards.md` (822 bytes) still contain the **pre-optimization** content.
**Fix**: Update `.windsurf/rules/` files to match the slimmed content.

### Gap 8: Codex Has No `.codexignore` Documentation

**Issue**: We created `.codexignore`, but the official Codex docs don't mention this filename. Codex uses its own sandboxing model and `project_doc_max_bytes` config, not an ignore file.

- The file is harmless but likely inert.
**Fix**: Keep it (no harm), but note in the plan that Codex context exclusion is managed via sandbox config, not ignore files. Check if Codex now reads `.codexignore` or a different mechanism.

---

## IMPROVEMENTS SUGGESTED BY RESEARCH

### Improvement 1: Use Claude Code `/init` for CLAUDE.md Validation

Anthropic docs: *"Run `/init` to generate a starting CLAUDE.md. If one already exists, `/init` suggests improvements."*
This can validate our slimmed CLAUDE.md.

### Improvement 2: Gemini `/memory show` for Verification

Gemini docs: *"`/memory show` displays the full concatenated content of the current hierarchical memory."*
Use this to verify exactly what Gemini loads.

### Improvement 3: Consider Claude Code `claudeMdExcludes` for Monorepo Safety

Not needed now (small project), but worth noting for future scale.

### Improvement 4: Cursor "Reference Files Instead of Copying"

Official Cursor best practice: *"Reference files with `@filename` rather than copying code."*
Our rules already point to `docs/standards/` rather than duplicating content. This is compliant.

---

## Execution Plan for Fixes

All fixes are small, targeted changes to align with official documentation.