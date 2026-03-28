# Context & Compaction (User-Scope)

## Session artifacts

Keep these files in `plans/` during active sessions. They are ephemeral — not permanent docs.

| File | Purpose | When to update |
|---|---|---|
| `plans/active-context.md` | Current focus, recent changes, next steps, key learnings | Whenever focus shifts or something significant is discovered |
| `plans/decisions.md` | Concise decision index for active work (append-only ADL log) | When making an architectural choice or finding a root cause |
| `plans/progress.md` | Task state in checkbox format | As tasks progress |

Durable decisions belong in `decisions/`. Link from `plans/decisions.md` when promoted.

## Behavioral rules

- **Artifact-driven state:** Keep current task and decisions in `plans/`. Chat history is ephemeral; compaction is lossless if the model can resume from the plan.
- **Request scoping:** Prefer concrete prompts (e.g. "fix `src/db.rs` line 42") over broad ones to reduce tokens and keep focus.
- **Session discipline:** One task per session when practical. After a significant commit or domain change, start a new chat. Use `/compact` at most 1-2 times per session — prefer checkpointing to a plan and starting fresh.
- **lean-ctx CCP is NOT activated** — do not run `lean-ctx init` without `--agent` flag.
