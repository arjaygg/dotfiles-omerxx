<!-- f3868c00-c262-45b0-a9cf-a95e8b753a2f -->
# Pre-Compaction & Token Context Management — User-Scope Implementation

## Current state

- **Plan document**: `docs/plans/2026-03-18-pre-compaction-token-context-management.md` does **not** exist in this repo; it was created in another repo (auc-discovery). The optimization is described in existing Cursor plans (e.g. `context_engineering_complete_6edbcaa7.plan.md`, `context_optimization_&_token_management_(balanced)_a13f7b8b.plan.md`) and in the transcript that wrote the 2026-03-18 plan.
- **Hooks** (already user-scope): `.claude/hooks/pre-compact.sh` and `context-monitor.sh` live in dotfiles and are invoked from `.claude/settings.json` with `~/.dotfiles/.claude/hooks/`. They run in the **current working directory** (any project), so they are already applicable across projects.
- **pre-compact.sh** today: Finds the most recent `plans/*.md`, lists recently modified files (vs `.git/index`), and emits a checkpoint message so the compacted context retains orientation. It does **not** look for `docs/plans/` or mention `docs/adr/`.
- **context-monitor.sh**: Fires desktop notifications at 30%, 15%, and 5% context remaining.

**User scope** here means: everything lives in **dotfiles** and applies whenever you use Claude Code (and optionally other IDEs) in any project — no per-project setup required beyond the hook config that already points at dotfiles.

---

## 1. Add the optimization plan to dotfiles

**Goal:** Make the optimization the single source of truth in this repo.

- Create **`docs/plans/`** in the dotfiles repo (it does not exist yet).
- Add **`docs/plans/2026-03-18-pre-compaction-token-context-management.md`** with content that:
  - Defines **pre-compaction** (proactive: reduce/structure context before hitting the window limit) vs **compaction** (reactive: after the fact).
  - Describes **artifact-driven state**: decisions and current task in `plans/` or `docs/plans/`, not in chat history; compaction then becomes lossless (model resumes from the plan).
  - Captures **prompts / discipline**: request scoping (e.g. “fix `src/db.rs` line 42”), session discipline (one task per session, new chat when changing domain), compaction as fallback (prefer short sessions + checkpoints over repeated compactions).
  - References the **existing hooks**: PreCompact runs `pre-compact.sh` to inject a checkpoint; context-monitor alerts at 30/15/5%.
  - Optionally notes **IDE-specific** bits (e.g. Cursor RTK vs Claude Code context-mode) as in the existing Cursor plans, so the doc stays the canonical “what we do” at user scope.

**Source for content:** Synthesize from (1) the Cursor plans under `.cursor/plans/` (context_engineering_complete, balanced, artifact-driven), (2) the behavior of `pre-compact.sh` and `context-monitor.sh`, and (3) if you have it, the auc-discovery version of the 2026-03-18 plan (copy/adapt rather than invent from scratch).

---

## 2. Make the PreCompact hook work for common project layouts

**Goal:** Pre-compact remains user-scope (unchanged location) but recognizes both `plans/` and `docs/plans/` so any project convention works.

- In **`.claude/hooks/pre-compact.sh`**:
  - **Plan discovery**: Keep current logic for `plans/*.md`; **additionally** look for the most recent `docs/plans/*.md`. If both exist, prefer the more recently modified one, or define a simple rule (e.g. prefer `docs/plans/` if it exists, else `plans/`).
  - **Retention hint**: In the message injected before compaction, explicitly mention retaining **`plans/`**, **`docs/plans/`**, and **`docs/adr/`** (so the model knows which artifacts to keep in view after compaction). This can be one line in the emitted text, e.g. “Retain state from plans/, docs/plans/, and docs/adr/.”

No changes to `context-monitor.sh` or `.claude/settings.json` are required for this step.

---

## 3. User-facing context discipline (optional but recommended)

**Goal:** One place in dotfiles that tells you (and agents) how to use context and compaction; applicable “within user scope” when working from dotfiles or when agents load dotfiles rules/skills.

- **Option A — Rule:** Add **`ai/rules/context-and-compaction.md`** (or similar name under `ai/rules/`). Short guideline: artifact-driven state, request scoping, session discipline, and “when context is high, prefer checkpoint + new chat over repeated compaction.” Link to `docs/plans/2026-03-18-pre-compaction-token-context-management.md` for the full optimization design. This aligns with the existing “Unified AI Hub” (`.cursorrules` points to `ai/rules/`).
- **Option B — Skill:** Add **`ai/skills/pre-compaction-context-management/`** with a `SKILL.md` that agents can use when: planning a compaction, starting a long session, or being asked to “optimize context.” The skill would describe: what the PreCompact hook does, how to resume from `plans/` or `docs/plans/`, and the prompts/discipline from the plan doc. This is optional and only needed if you want agents to explicitly “use” the optimization (e.g. “before compacting, ensure the current plan is written to `docs/plans/`”).

Recommendation: do **Option A** so the rule is always visible when using dotfiles; add **Option B** only if you want a dedicated skill for compaction/context flows.

---

## 4. Verification (user-scope)

- **Claude Code**: In any project that has a `plans/` or `docs/plans/` directory, run a session until a context notification (or trigger compaction). Confirm the PreCompact hook runs and the injected message includes the active plan path and the retention hint for `plans/`, `docs/plans/`, and `docs/adr/`.
- **Dotfiles as source of truth**: Open `docs/plans/2026-03-18-pre-compaction-token-context-management.md` and confirm it accurately describes the hooks and the intended behavior. If you use `ai/rules/context-and-compaction.md`, confirm it links to this plan and is concise.

---

## Summary of deliverables

| Deliverable | Location | Purpose |
|------------|----------|---------|
| Optimization plan | `docs/plans/2026-03-18-pre-compaction-token-context-management.md` | Single source of truth for pre-compaction and token-context management at user scope |
| PreCompact hook update | `.claude/hooks/pre-compact.sh` | Resolve plan from `plans/` or `docs/plans/`; add retention hint for `plans/`, `docs/plans/`, `docs/adr/` |
| Context discipline rule (optional) | `ai/rules/context-and-compaction.md` | Short user/agent guideline + link to plan |
| Skill (optional) | `ai/skills/pre-compaction-context-management/SKILL.md` | Agent-facing skill for compaction and context flows |

No change to Cursor, Gemini, or Codex **project** config is required for “user scope”: the hooks and docs live in dotfiles and apply whenever Claude Code uses your dotfiles hook path. Projects that use `plans/` or `docs/plans/` automatically get the improved checkpoint behavior.
