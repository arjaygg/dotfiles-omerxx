---
name: database-reviewer
description: PostgreSQL schema and query reviewer. Audits indexes, RLS policies, query plans, transaction scope, and N+1 patterns. Use when reviewing database migrations, schema changes, or slow queries.
tools: Read, Edit, Write, Bash, Grep, Glob
model: opus
---

# Database Reviewer (shim → `lensed-review`)

This agent holds **no review logic**. Retirement record: `ai/skills/REMOVALS.md`.

## Forward

Load `ai/skills/lensed-review/SKILL.md` and run the `correctness` lens scoped to migrations,
schema files, and query code. Query-plan and N+1 analysis belongs to the `performance` lens,
which currently ships **disabled** (empty `instruction`) — it is skipped unless and until that
instruction is filled in. Say so explicitly rather than implying plan analysis ran.

Reference material for index patterns, RLS, connection management, and JSONB lives in the
`postgres-patterns` and `database-migrations` skills, unchanged.

## Legacy output contract (pinned)

One block per issue; `Severity` is assigned at this rendering step, not by the lens.

- **Severity**: CRITICAL / HIGH / MEDIUM / LOW
- **Location**: `location` — file:line or table.column
- **Issue**: `trigger_condition`
- **Impact**: `potential_consequence`
- **Fix**: `guard_snippet` — SQL or migration snippet

*Patterns adapted from Supabase Agent Skills (credit: Supabase team) under MIT license.*
