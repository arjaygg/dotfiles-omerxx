# Plan: Session Transcript Analysis → Automation Candidates

## Context

Analyzed 1,503 Claude Code session transcripts (463 MB) across all projects, plus 13,155 history.jsonl entries. Goal: identify recurring prompt patterns and build automation primitives (skills, hooks, agents) to eliminate repetition.

## Key Findings

| Pattern | Frequency | Current State |
|---|---|---|
| Branch cleanup/audit queries | ~25% of sessions | Manual multi-step |
| Stack PR full lifecycle ("create, merge, clean up") | ~20% | 5 separate skills chained manually |
| Session context switching (/clear=1613, /exit=647) | ~15% | session-picker exists, restore is manual |
| Single-word confirmations (yes/go/continue) | 2,230 instances | No automation |
| Config/keybinding lookups | ~10% | Full file reads each time |
| Explore→Design→Implement pattern | ~20% | Manual sequencing |
| Phase-gate reviews (TDD, security) | ~15% | hawk exists but project-specific |
| Model routing (/model=374 times) | ~8% | CLAUDE.md rules exist, not enforced |

## Top 8 Automation Candidates (ranked by impact)

### 1. `branch-audit` — Skill (Priority: HIGH, Size: M)
**Invoke:** `/branch-audit`
**Does:**
- Scans all local branches for merge status (merged into main, has open PR, orphaned)
- Checks for dangling worktrees in `.trees/`
- Lists stale remote-tracking branches
- Offers batch cleanup with confirmation
- Outputs actionable table: branch → status → recommended action

**Builds on:** `stack-status`, `stack-doctor`, git commands
**Create with:** `/claude-architect` → Skill

---

### 2. `session-restore` — Hook (Priority: HIGH, Size: M)
**Invoke:** Automatic (UserPromptSubmit, first prompt only)
**Does:**
- Detects current worktree/branch on session start
- Reads `plans/session-handoff.md` if present
- Injects prior context (active plan, progress state, last commit) into conversation
- Deletes handoff file after loading
- Skips if no handoff exists (fresh session)

**Builds on:** `session-init.sh`, `session-end.sh`, handoff file convention
**Create with:** `/claude-architect` → Hook

---

### 3. `auto-confirm` — Hook (Priority: HIGH, Size: S)
**Invoke:** Automatic (UserPromptSubmit)
**Does:**
- Matches single-word confirmation prompts: `yes`, `go`, `continue`, `do it`, `proceed`, `ship it`
- Injects "Continue with the pending operation" to reduce round-trips
- Deny-list for destructive operations (force push, branch delete) — always require explicit confirmation
- Logs confirmations for session audit

**Builds on:** `prompt-capture.sh` infrastructure
**Create with:** `/claude-architect` → Hook

---

### 4. `stack-lifecycle` — Skill (Priority: MEDIUM, Size: L)
**Invoke:** `/stack-lifecycle <description>` or detected from compound requests
**Does:**
- Orchestrates: stack-create → implement → smart-commit → stack-pr → auto-merge → cleanup
- Each phase gate is auto-confirmed unless `--interactive`
- Emits session summary on completion
- Handles failures gracefully (rolls back to last clean state)

**Builds on:** `stack-create`, `stack-pr`, `stack-auto-pr-merge`, `stack-merge`, `stack-update`
**Create with:** `/claude-architect` → Skill

---

### 5. `hawk-universal` — Agent (Priority: MEDIUM, Size: M)
**Invoke:** `/hawk` (generalized beyond auc-conversion)
**Does:**
- Adversarial code review for ANY project (not just Go/auc-conversion)
- Auto-detects language and applies appropriate linters
- Security gate mode for phase transitions
- Produces structured review artifact (findings, severity, recommendations)
- Integrates with PR workflow (can block merge)

**Builds on:** `hawk`, `bmad-custom-pr-review`
**Create with:** `/claude-architect` → Agent definition

---

### 6. `config-lookup` — Hook (Priority: LOW, Size: S)
**Invoke:** Automatic (UserPromptSubmit, when prompt mentions tmux/keybinding/dotfile)
**Does:**
- Pre-indexes common config files (tmux.conf, keybindings.json, zshrc)
- Intercepts config lookup prompts and injects relevant snippets
- Avoids repeated full-file reads

**Builds on:** `tmux-automation`, `keybindings-help`
**Create with:** `/claude-architect` → Hook

---

### 7. `model-router` — Hook (Priority: LOW, Size: M)
**Invoke:** Automatic (UserPromptSubmit)
**Does:**
- Classifies prompt intent and auto-suggests model switch
- Explanation/summary → suggest haiku or ollama
- Complex architecture → stay on opus
- Quick fix → suggest sonnet
- Logs routing decisions for tuning

**Builds on:** CLAUDE.md multi-model routing rules
**Create with:** `/claude-architect` → Hook

---

### 8. `edi` (Explore-Design-Implement) — Skill (Priority: LOW, Size: L)
**Invoke:** `/edi <task description>`
**Does:**
- Phase 1: Spawns Explore agent for codebase research
- Phase 2: Invokes claude-architect for design/plan
- Phase 3: Spawns appropriate dev agent for implementation
- Each phase emits gate artifact (exploration report → design doc → impl PR)

**Builds on:** `explore`, `autoresearch`, `claude-architect`, dev agents
**Create with:** `/claude-architect` → Skill

---

## Implementation Order

**Wave 1 (Quick wins — do first):**
1. `auto-confirm` hook (S) — immediate ergonomic improvement
2. `branch-audit` skill (M) — eliminates most frequent manual workflow
3. `session-restore` hook (M) — fixes context loss on every session start

**Wave 2 (High value, more effort):**
4. `stack-lifecycle` skill (L) — composes existing skills
5. `hawk-universal` agent (M) — generalizes existing hawk

**Wave 3 (Nice to have):**
6. `config-lookup` hook (S)
7. `model-router` hook (M)
8. `edi` skill (L)

## Execution Strategy

Each candidate should be built using `/claude-architect` which handles:
- Deciding the primitive type
- Scaffolding the file structure
- Registering in settings.json
- Creating symlinks

Build each in an isolated worktree, test, then merge via stack-pr.

## Verification

For each primitive built:
- **Skills:** Invoke via slash command, verify output matches expected behavior
- **Hooks:** Trigger the hook condition, verify injection/blocking works
- **Agents:** Spawn and verify autonomous completion of delegated task
