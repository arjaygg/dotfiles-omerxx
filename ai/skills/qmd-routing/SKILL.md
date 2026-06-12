---
name: qmd-routing
description: "QMD semantic search routing rules. Use when searching team docs, OKRs, goals, priorities, ActivTrak product/analytics docs, auc-conversion RFCs/ADRs/Go patterns, or PDF/DOCX/image files ingested via LiteParse. Collections: activtrak (user analytics, internal tooling), team-okrs (goals, KPIs, roadmap, quarterly targets), claude-pdf-context (ingested PDFs/DOCX/XLSX/PPTX/images), auc-conversion (conversion worker RFCs, queue design, DB contention, testing strategy). Also covers LiteParse ingest pipeline for binary docs."
---

# QMD Routing Rules

QMD is a local semantic search engine over private markdown collections. Use it proactively when a question touches domains covered by the indexed collections.

## Collections & When to Search

| Collection | Topics | Search when user asks about |
|---|---|---|
| `activtrak` | ActivTrak product, user behavior analytics, internal tooling, feature docs, onboarding | ActivTrak features, user tracking, productivity analytics, internal tools, product behavior |
| `team-okrs` | Team goals, OKRs, planning, priorities, KPIs, roadmap, metrics, quarterly targets | Team goals, OKRs, key results, initiatives, priorities, planning cycles, metrics, Q1/Q2/Q3/Q4 targets |
| `claude-pdf-context` | Parsed PDFs, Office docs (DOCX/XLSX/PPTX), images, job descriptions, OKRs, team docs — all ingested via LiteParse | "my docs", "check the PDF/doc", any binary file previously ingested via `/lit-ingest` |
| `auc-conversion` | AUC Conversion project docs — RFCs, ADRs, guides, specs, testing strategy, architecture, stories, technical debt | RFCs, ADRs, worker architecture, queue design, dequeuing, DB contention, Go patterns, conversion worker behavior, project guides |

## Tool Selection

| Scenario | Tool | Notes |
|---|---|---|
| Specific keyword or exact term | `mcp__qmd__search` | ~30ms, use first |
| Concept or paraphrase query | `mcp__qmd__vector_search` | ~2s, use when keyword fails or query is fuzzy |
| Broad exploratory question | `mcp__qmd__deep_search` | ~10s, use sparingly for open-ended research |
| Retrieve a specific known doc | `mcp__qmd__get` | Use when you have a path or doc ID |
| Check collection health | `mcp__qmd__status` | Use when debugging or verifying index |

Add `minScore: 0.5` to filter out low-confidence results.

## When to Trigger

**DO search qmd proactively when:**
- The user asks a question whose answer likely lives in one of the three collections
- The user references team planning, ActivTrak behavior, or "my docs"
- The question is knowledge/context-oriented and not a coding task

**DO NOT search qmd when:**
- The task is code editing, git operations, or debugging
- The question is generic (no match to a collection domain)
- You already have the relevant context in the current conversation

## Ingesting Binary Docs into QMD (LiteParse Pipeline)

`claude-pdf-context` is fed by LiteParse. When a user references a PDF, DOCX, XLSX, PPTX,
or image that QMD returns no results for:

1. Run: `LeanCtx.ctxShell({ command: "~/.dotfiles/scripts/lit-ingest.sh <file-path> [slug]" })`
2. Confirm output ends with `Collection: claude-pdf-context`
3. Re-run the original QMD search — the doc is now indexed

**Do NOT** try to `Read` binary files directly. Always route through LiteParse first.

The ingest script outputs markdown to `~/.local/share/claude-pdf-index/` — the path QMD already
watches for the `claude-pdf-context` collection. No config changes needed.

## Behavior Pattern

1. Identify which collection is relevant (activtrak / team-okrs / claude-pdf-context / auc-conversion)
2. If `claude-pdf-context` and query returns nothing → check if source is a binary doc, ingest via LiteParse first
3. Call `mcp__qmd__search` first (fast)
4. If results are weak or the query is conceptual, follow up with `mcp__qmd__vector_search`
5. Synthesize findings into your response — cite the doc path from the result
6. Do not mention "I searched qmd" unless the user asks; just use the context naturally
