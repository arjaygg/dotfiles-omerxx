# Context & Compaction (User-Scope)

## Behavioral rules

- **Artifact-driven state:** Keep current task and decisions in `plans/`. Chat history is ephemeral; compaction is lossless if the model can resume from the plan.
- **Request scoping:** Prefer concrete prompts (e.g. "fix `src/db.rs` line 42") over broad ones to reduce tokens and keep focus.
- **Session discipline:** One task per session when practical. After a significant commit or domain change, start a new chat. Use `/compact` at most 1-2 times per session — prefer checkpointing to a plan and starting fresh.
- **lean-ctx CCP is NOT activated** — do not run `lean-ctx init` without `--agent` flag.

> Session artifact definitions (`active-context.md`, `decisions.md`, `progress.md`) live in each project's CLAUDE.md to avoid duplication.
