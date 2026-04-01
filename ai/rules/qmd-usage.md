# QMD Usage Rules

QMD is a local semantic search engine over private markdown collections. Use it proactively when a question touches domains covered by the indexed collections.

## Collections & When to Search

| Collection | Topics | Search when user asks about |
|---|---|---|
| `activtrak` | ActivTrak product, user behavior analytics, internal tooling, feature docs, onboarding | ActivTrak features, user tracking, productivity analytics, internal tools, product behavior |
| `team-okrs` | Team goals, OKRs, planning, priorities, KPIs, roadmap, metrics, quarterly targets | Team goals, OKRs, key results, initiatives, priorities, planning cycles, metrics, Q1/Q2/Q3/Q4 targets |
| `claude-pdf-context` | PDF documents, uploaded references, shared context docs | "my docs", "check the docs", PDFs, uploaded documents, reference materials |

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

## Behavior Pattern

1. Identify which collection is relevant (activtrak / team-okrs / claude-pdf-context)
2. Call `mcp__qmd__search` first (fast)
3. If results are weak or the query is conceptual, follow up with `mcp__qmd__vector_search`
4. Synthesize findings into your response — cite the doc path from the result
5. Do not mention "I searched qmd" unless the user asks; just use the context naturally
