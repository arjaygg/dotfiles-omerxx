# Context & Compaction (User-Scope)

Short guideline for token and context-window management. Full design: **plans/2026-03-18-pre-compaction-token-context-management.md**.

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

## lean-ctx integration notes

lean-ctx is integrated as a pctx upstream (see `decisions/0004-lean-ctx-pctx-upstream.md`):
- **`ctx_read`** provides SessionCache-backed file reads (~13 tokens on cache hit) — complements Grep and Read, does not replace them.
- **`ctx_tree`** provides AST skeleton trees for map-mode exploration — use before Serena.getSymbolsOverview when territory is unfamiliar.
- **lean-ctx CCP is explicitly NOT activated** — the 3-layer system below is the sole session continuity mechanism. Do not run `lean-ctx init` without `--agent` flag.

## Artifact-driven state

- Keep current task and decisions in **plans/** or **docs/plans/**. Promote durable or non-trivial decisions to **decisions/**.
- Chat history is ephemeral; compaction is lossless if the model can resume from the plan.

## Request scoping

- Prefer concrete prompts (e.g. "fix `src/db.rs` line 42") over broad ones ("fix the database bug") to reduce tokens and keep focus.

## Session discipline

- One task per session when practical. After a significant commit or domain change, start a new chat.
- When context is high, **checkpoint to a plan and start a new session** rather than compacting repeatedly. Use compaction (e.g. `/compact`) at most 1–2 times per session.

## Hooks (Claude Code)

The system is powered by 7 integrated hooks in `~/.dotfiles/.claude/hooks/`:

- **PreToolUse** (`pre-tool-gate.sh`): Enforces tool discipline. Blocks lock file reads, warns on large reads, and prevents using Bash for operations where dedicated tools (Read/Grep/Glob) exist.
- **PostToolUse** (`post-tool-handler.sh`): Compacts Bash output >300 lines to save context. Provides batching reminders after `pctx execute_typescript` calls.
- **UserPromptSubmit** (`plans-healthcheck.sh`): Session start healthcheck. Warns on missing/stale artifact files and missing binary dependencies (`qmd`, `rtk`).
- **UserPromptSubmit** (`qmd-sync.sh`): Silently keeps the `qmd` semantic search index current for the workspace.
- **PreCompact** (`pre-compact.sh`): Injects an enriched checkpoint (git state, active plan, decisions, progress, topics) before context compaction to make it lossless.
- **Stop** (`session-end.sh`): Handoff generator. Writes `plans/session-handoff.md` at turn end so the next session can resume state.
- **Notification** (`context-monitor.sh`): Real-time usage alerts. Fires macOS desktop notifications at 30%, 15%, and 5% context remaining.
