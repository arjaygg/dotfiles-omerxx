# Context & Compaction (User-Scope)

## Behavioral rules

- **Artifact-driven state:** Keep current task and decisions in `plans/`. Chat history is ephemeral; compaction is lossless if the model can resume from the plan.
- **Request scoping:** Prefer concrete prompts (e.g. "fix `src/db.rs` line 42") over broad ones to reduce tokens and keep focus.
- **Session discipline:** One task per session when practical. After a significant commit or domain change, start a new chat. Use `/compact` at most 1-2 times per session — prefer checkpointing to a plan and starting fresh.
- **Screenshots:** Prefer file-path references over pasted screenshots in long working sessions — a pasted image is re-carried in context until compaction (311KB observed); paste images into short dedicated sessions instead.
- **lean-ctx CCP is active and in use** — `LeanCtx.ctxSession(action: "status"/"load")` returns real, persisted cross-session state (50+ sessions under `~/.config/lean-ctx/sessions`, spanning months), confirming CCP works today and does not depend on any CLI bootstrap step. Use `ctxSession(action: "load"/"finding")` per `ai/rules/tool-priority.md` §10 for cross-session continuity.
  (Note: `decisions/0004-lean-ctx-pctx-upstream.md` records CCP as "not activated" — that line is stale relative to current behavior and should be revisited separately.)
  Unrelated to CCP: if the lean-ctx CLI bootstrap is ever re-run, use `lean-ctx init --agent` only — never `--global` — to avoid shell-hook double-compression conflicts with rtk.

> Session artifact definitions (`active-context.md`, `decisions.md`, `progress.md`) live in the global `~/.claude/CLAUDE.md` § Session Artifacts, to avoid duplication.

- **Never re-Read CLAUDE.md-imported files post-compaction:** `CLAUDE.md`, `AGENTS.md`, and anything they `@`-import (`RTK.md`, `rules/*.md`) are reloaded automatically as part of the system prompt on every turn, including immediately after compaction. Re-reading them manually after a compaction event wastes tokens on content already present in context — check whether a fact is already covered by loaded rules before issuing a `Read` for one of these files.
