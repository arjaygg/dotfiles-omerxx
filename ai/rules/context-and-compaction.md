# Context & Compaction (User-Scope)

Short guideline for token and context-window management. Full design: **docs/plans/2026-03-18-pre-compaction-token-context-management.md**.

## Three-layer preservation system

Context is preserved across compaction through three layers:

### Layer 1 — Model-maintained session artifacts (written during work)

Keep these files in `plans/` during active sessions (see behavioral rules in `~/.claude/CLAUDE.md`):

| File | Purpose | When to update |
|---|---|---|
| `plans/active-context.md` | Current focus, recent changes, next steps, key learnings | Whenever focus shifts or something significant is discovered |
| `plans/decisions.md` | Concise decision index for active work (append-only ADL log) | When making an architectural choice or finding a root cause |
| `plans/progress.md` | Task state in checkbox format | As tasks progress |

These are ephemeral per-session artifacts, not permanent documentation. The `qmd` MCP server indexes `plans/` for semantic search — decisions and context are automatically searchable.

Durable decisions belong in `decisions/`. Keep the concise entry in `plans/decisions.md` and link to the long-form record when promoted. See `docs/decision-records.md` for the canonical convention.

### Layer 2 — PreCompact hook (`pre-compact.sh`)

Fires before `/compact` (manual or auto). Injects an enriched checkpoint containing:
- Git branch + uncommitted file state
- Active context from `plans/active-context.md`
- Recent conversation topics (5 for manual compact, 10 for auto)
- Active plan file + title
- Recent decisions from `plans/decisions.md`
- Task state from `plans/progress.md`
- Recently edited files
- Retention hint for `plans/`, `docs/plans/`, and `decisions/`

### Layer 3 — Session handoff (`session-end.sh`)

Fires on `Stop` event (end of turn). If `plans/` exists and artifact files are populated, writes `plans/session-handoff.md` for the next session to discover.

## Artifact-driven state

- Keep current task and decisions in **plans/** or **docs/plans/**. Promote durable or non-trivial decisions to **decisions/**.
- Chat history is ephemeral; compaction is lossless if the model can resume from the plan.

## Request scoping

- Prefer concrete prompts (e.g. "fix `src/db.rs` line 42") over broad ones ("fix the database bug") to reduce tokens and keep focus.

## Session discipline

- One task per session when practical. After a significant commit or domain change, start a new chat.
- When context is high, **checkpoint to a plan and start a new session** rather than compacting repeatedly. Use compaction (e.g. `/compact`) at most 1–2 times per session.

## Hooks (Claude Code)

- **PreCompact** (`pre-compact.sh`): Injects enriched checkpoint before compaction (git state, artifact files, transcript topics, recent files, retention hint).
- **Stop** (`session-end.sh`): Writes `plans/session-handoff.md` at the end of each turn if artifact files are populated.
- **context-monitor.sh**: Alerts at 30%, 15%, and 5% context remaining.
