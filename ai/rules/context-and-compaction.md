# Context & Compaction (User-Scope)

Short guideline for token and context-window management. Full design: **docs/plans/2026-03-18-pre-compaction-token-context-management.md**.

## Artifact-driven state

- Keep current task and decisions in **plans/** or **docs/plans/** (and non-trivial decisions in **docs/adr/** when useful).
- Chat history is ephemeral; compaction is lossless if the model can resume from the plan.

## Request scoping

- Prefer concrete prompts (e.g. “fix `src/db.rs` line 42”) over broad ones (“fix the database bug”) to reduce tokens and keep focus.

## Session discipline

- One task per session when practical. After a significant commit or domain change, start a new chat.
- When context is high, **checkpoint to a plan and start a new session** rather than compacting repeatedly. Use compaction (e.g. `/compact`) at most 1–2 times per session.

## Hooks (Claude Code)

- **PreCompact** (`pre-compact.sh`): Injects a checkpoint (active plan, recent files, retention hint) before compaction so the model can resume from **plans/**, **docs/plans/**, and **docs/adr/**.
- **context-monitor.sh**: Alerts at 30%, 15%, and 5% context remaining.
