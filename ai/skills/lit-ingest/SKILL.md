---
name: lit-ingest
description: >
  Parse a binary document (PDF, DOCX, XLSX, PPTX, image) with LiteParse and ingest it into
  the claude-pdf-context QMD collection so it becomes searchable by all agents via mcp__qmd__*.
  USE THIS SKILL when user says "add this PDF to my docs", "index this file", "make this
  searchable", "ingest this document", "add to my knowledge base", or references a binary file
  that QMD returns no results for.
version: 1.0
triggers:
  - /lit-ingest
  - add this PDF to my docs
  - index this file
  - make this file searchable
  - ingest this document
  - add to my knowledge base
  - add this to my docs
  - ingest this PDF
  - ingest this report
  - add this report to my docs
---

# LiteParse Ingest Skill

Converts a binary document to markdown via LiteParse and adds it to the `claude-pdf-context`
QMD collection at `~/.local/share/claude-pdf-index/`.

After ingestion the document is immediately queryable by Claude Code, Cursor, Gemini, and any
other agent going through the pctx gateway — no config changes needed.

## Prerequisites

LiteParse CLI must be installed:
```
npm i -g @llamaindex/liteparse
```

## Instructions

### When to invoke

- User says "add this PDF/doc to my docs", "index this report", "make this file searchable"
- User references a binary file (PDF, DOCX, XLSX, PPTX, image) and `mcp__qmd__search` returns nothing
- User explicitly runs `/lit-ingest`

### Steps

1. **Identify the file path** from the user's message. If not provided, ask for it.

2. **Determine a slug** — a short, lowercase, hyphenated name for the output file.
   - Default: derive from the filename (e.g., `Q3-Report.pdf` → `q3-report`)
   - User can override: "ingest as 'migration-spec'"

3. **Run the ingest script** (use Bash tool directly — ctxShell allowlist blocks custom scripts):
   ```
   Bash: ~/.dotfiles/scripts/lit-ingest.sh "<file-path>" "<slug>"
   ```

4. **Confirm success** — output should end with:
   ```
   Ingested: ~/.local/share/claude-pdf-index/<slug>.md
   Collection: claude-pdf-context
   ```

5. **Verify searchability** — run a quick sanity search:
   ```
   mcp__qmd__search({ collection: "claude-pdf-context", query: "<topic from doc>" })
   ```

6. Report to the user: what was ingested, the slug used, and a sample query they can run.

### Error handling

| Error | Fix |
|---|---|
| `'lit' CLI not found` | Run `npm i -g @llamaindex/liteparse` first |
| `file not found` | Verify the path — use absolute path if relative fails |
| QMD search still empty after ingest | QMD may need a moment to reindex; wait ~5s and retry |
