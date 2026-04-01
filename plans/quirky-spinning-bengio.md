# Plan: Diagnose & Fix qmd Triggering

**Date:** 2026-04-01  
**Context:** User reports qmd "does not seem to trigger anymore." Investigation needed to determine if this is a broken install, a missing rule, or a removed hook.

---

## Context

qmd is a local markdown search engine (MCP server) over 86 docs across 3 collections:
- `activtrak` (31 docs, /Users/axos-agallentes/git/activtrak)
- `team-okrs` (36 docs, /Users/axos-agallentes/git/team-okrs)
- `claude-pdf-context` (19 docs, /Users/axos-agallentes/.local/share/claude-pdf-index)

The user's concern: qmd used to "trigger" (Claude proactively used it) but no longer does.

---

## Findings

### What IS working (no fixes needed)
- **Binary:** `/Users/axos-agallentes/.bun/bin/qmd` v1.0.7 — installed via bun
- **MCP Server:** configured in `.mcp.json` → `qmd mcp` command — tools load in Claude Code
- **Sync Hook:** `qmd-sync.sh` runs on every `UserPromptSubmit`, keeps collections updated in background
- **Collections:** 86 docs, 859 vectors, current as of each session start
- **Tools available:** `mcp__qmd__search`, `vector_search`, `deep_search`, `get`, `multi_get`, `status`

### Root Cause: No triggering rules exist
qmd was designed as a **callable tool** (Claude uses it when asked) and a **freshness system** (sync hook keeps indices warm). There is **no rule in `ai/rules/`** and no content in `CLAUDE.md`/`AGENTS.md` that tells Claude *when* to proactively search qmd collections.

Without triggering rules, Claude only calls qmd if:
- The user explicitly asks to search it
- Claude independently infers it's relevant

This means "auto-triggering" behavior never existed in rules form — but the user likely expected it given the system is otherwise sophisticated.

### What may have changed
The prior session (2026-04-01) did heavy hook optimization (phases 1-9). `instructions-loaded.sh` and `session-end.sh` were modified. If any of those hooks previously injected qmd search results, that behavior may have been removed as part of the optimization pass. The git history shows qmd was added March 19, 2026 — a relatively recent addition.

---

## Recommended Fix

**Add a qmd usage rule to `ai/rules/`** — a new file `qmd-usage.md` that tells Claude when to proactively search qmd collections. This is the correct layered approach (rules for behavior, hooks for data freshness).

### Rule content to add

The rule should specify:
1. **When to search qmd** — types of questions that map to each collection:
   - `activtrak` → questions about ActivTrak product, user behavior analytics, internal tooling
   - `team-okrs` → questions about team goals, OKRs, planning, priorities, metrics
   - `claude-pdf-context` → questions about PDFs, documents, or when user says "check my docs"
2. **Which tool to use** — `search` for keyword queries, `vector_search` for concept queries, `deep_search` for broad exploration
3. **When NOT to search** — code changes, git operations, debugging — don't waste the 2-10s RTT

The new rule would live at `ai/rules/qmd-usage.md` and be symlinked/loaded in `.claude/CLAUDE.md` via `@../ai/rules/qmd-usage.md`.

---

## Files to Modify

| File | Action |
|------|--------|
| `ai/rules/qmd-usage.md` | CREATE — qmd triggering rules |
| `.claude/CLAUDE.md` | ADD `@../ai/rules/qmd-usage.md` loader line |
| `ai/rules/tool-priority.md` | OPTIONAL — add qmd to tool priority table |

---

## Secondary Check: Verify hooks weren't regressed

Before writing rules, verify that the prior session's hook optimization didn't accidentally remove qmd-related behavior from `instructions-loaded.sh` or `session-end.sh`. Check the git diff for those files.

**Command:**
```bash
git -C /Users/axos-agallentes/.dotfiles show HEAD:.claude/hooks/instructions-loaded.sh 2>/dev/null | grep -i qmd
```

If any qmd logic was in those hooks before and was removed, that needs to be restored separately.

---

## Verification

After adding the rule:
1. Start a new Claude Code session
2. Ask a question about ActivTrak or team OKRs — Claude should proactively call `mcp__qmd__search` or `mcp__qmd__vector_search`
3. Confirm tools return results (not errors)
4. Run `mcp__qmd__status` to verify collections are current

---

## Out of Scope

- Reinstalling qmd — not needed, binary is healthy
- Reconfiguring MCP — not needed, server loads correctly
- Modifying UserPromptSubmit sync hook — working as designed

---

## User Clarification

**User confirmed:** "Triggering" means Claude auto-searching qmd on its own when a question seemed relevant to the collections — without being explicitly asked.

Fix is confirmed: add `ai/rules/qmd-usage.md` with proactive trigger rules.
