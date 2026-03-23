# Pre-Compaction & Token/Context Window Management

**User-scope reference.** This doc lives in dotfiles and describes how we manage token usage and context windows across agent workflows (Claude Code, Cursor, and others). It is the single source of truth for pre-compaction behavior and context discipline.

---

## 1. Pre-Compaction vs. Compaction

| | Pre-compaction | Compaction |
|---|----------------|------------|
| **When** | Proactive, before hitting the context limit | Reactive, after the limit is reached or triggered |
| **Goal** | Reduce or structure context so the window is not exhausted | Summarize/discard history so the session can continue |
| **How** | Tiered loading, request scoping, artifact-driven state, session discipline | Model or tool compresses/summarizes prior turns (e.g. `/compact`) |

Pre-compaction is the primary lever: if state lives in artifacts (`plans/`, `docs/plans/`, `docs/adr/`) and prompts are scoped, compaction becomes a rare fallback and remains lossless because the model can resume from the plan.

---

## 2. Artifact-Driven State

**Principle:** The source of truth for “what we’re doing” is files, not chat history.

- **Plans:** Current task and decisions go in `plans/*.md` or `docs/plans/*.md`.
- **ADRs:** Non-trivial decisions go in `docs/adr/*.md` when useful.
- **Compaction:** When context is compacted, the model only needs to read the *current plan* (and optionally recent ADRs) to restore state. Chat history can be summarized or dropped without losing the thread.

This makes compaction **lossless**: orientation is preserved via artifacts.

---

## 3. Prompts & Discipline

- **Request scoping:** Prefer concrete prompts (e.g. “fix `src/db.rs` line 42”) over broad ones (“fix the database bug”). Scoped requests use far fewer tokens and keep the model focused.
- **Session discipline:** One task per session when practical. When changing domain or after a significant commit, start a new chat.
- **Compaction as fallback:** Prefer short sessions and artifact checkpoints over repeated compaction cycles. Use compaction (e.g. `/compact`) at most 1–2 times per session; after that, checkpoint to a plan and start a new session.
- **Kernel files:** Avoid editing kernel files (e.g. `AGENTS.md`, `CLAUDE.md`) mid-session if prompt caching is in use; changes can invalidate the cache.

---

## 4. Hooks (Claude Code, user-scope)

The system is powered by 7 integrated hooks in `~/.dotfiles/.claude/hooks/`:

### Artifact & Session Lifecycle
- **UserPromptSubmit** (`plans-healthcheck.sh`): Fires at session start. Validates that artifact files (`plans/`) are present and updated today. Checks for missing binary dependencies (`qmd`, `rtk`).
- **UserPromptSubmit** (`qmd-sync.sh`): Silently updates the `qmd` semantic index on every prompt submission.
- **PreCompact** (`pre-compact.sh`): Injects an enriched checkpoint (git state, active plan, decisions, progress, topics) before context compaction, ensuring the process is lossless.
- **Stop** (`session-end.sh`): Writes `plans/session-handoff.md` at the end of each turn if artifacts are present.

### Content & Token Management
- **PreToolUse** (`pre-tool-gate.sh`): Safeguard that blocks large lock file reads and enforces tool discipline (e.g., using `Read` instead of `cat`).
- **PostToolUse** (`post-tool-handler.sh`): Intercepts large Bash output (>300 lines) and compacts it. This is the implementation of "context-mode routing."
- **Notification** (`context-monitor.sh`): Real-time desktop alerts (macOS) at 30%, 15%, and 5% context remaining.

---

## 5. IDE-Specific Notes

- **Claude Code:** Full 7-hook lifecycle. "Context-mode" is implemented via `post-tool-handler.sh` and `pre-tool-gate.sh`.
- **Cursor:** No PreCompact hook; use artifact-driven discipline and request scoping. Rules in `ai/rules/` (e.g. context-and-compaction) can reinforce the same habits.
- **Gemini / Codex:** Session discipline and artifact checkpoints apply; project-level docs (e.g. CODEX.md, GEMINI.md) can reference this approach.

---

## 6. Verification

- In any project with `plans/` or `docs/plans/`, trigger compaction (or run until a context notification). Confirm the PreCompact hook runs and the injected message includes the active plan and the retention hint for `plans/`, `docs/plans/`, and `docs/adr/`.
- See `ai/rules/context-and-compaction.md` for a short guideline linked from this plan.
