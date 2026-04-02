# Plan: Skill & Automation Opportunities — System-Wide Gap Analysis

**Date:** 2026-04-03  
**Branch:** TBD (new branch from main)

---

## Context

Deep analysis of the entire dotfiles system revealed:
- **28 skills** active, **19,457 hook events/week**, **1,382 captured prompts** across 514 sessions
- **127 projects** tracked, heaviest: auc-conversion (62 sessions), dotfiles (15), team-okrs (14)
- Several **manual workflows** that repeat daily but lack automation
- **Existing infrastructure** (prompt-capture DB, hook metrics DB, tmux bridge) ready to power new skills

**Goal:** Identify every manual CLI operation, task, and workflow that would benefit from a skill, agent, or hook — prioritized by frequency × effort savings.

---

## Identified Opportunities (sorted by impact)

### Tier 1 — High Frequency, High Savings

#### 1. Skill Auto-Invocation Hook (UserPromptSubmit)
**Evidence:** 40 Grep calls in one session should have been `/explore`. 5,857 serena-tool-priority fires/week = model constantly choosing wrong tool.
**Current state:** Rules in tool-priority.md (behavioral guidance only, no enforcement)
**Proposal:** `UserPromptSubmit` hook that detects trigger phrases and injects skill reminder:
```
"find where X is" → "💡 Consider /explore skill → Serena.findSymbol()"
"explain how"     → "💡 Consider /gemini skill → better reasoning model"
"write tests for" → "💡 Consider /codex skill → pattern-following model"
```
**File:** `.claude/hooks/skill-trigger-reminder.sh`
**Savings:** 30-50% token reduction per session (1,600-3,200 tokens)

#### 2. Branch & Worktree Cleanup Skill
**Evidence:** 20 atomic state files in /tmp, 15+ worktrees across auc-conversion. No cleanup automation.
**Current state:** Manual `git worktree remove` + `git branch -d` required
**Proposal:** `/cleanup` skill that:
- Lists merged branches with no open PRs
- Shows stale worktrees (>7 days inactive, no uncommitted changes)
- Offers interactive or auto cleanup
- Respects safety: never deletes with uncommitted changes
**File:** `ai/skills/cleanup/SKILL.md`
**Frequency:** Daily (every developer session ends with stale branches)

#### 3. Prompt Learning Pipeline Completion
**Evidence:** 1,382 prompts captured but `ai/prompts/` directory doesn't exist yet. Memory says "SQLite capture/score pipeline → ai/prompts/ → Ctrl+A / picker" is planned but incomplete.
**Current state:** `prompt-capture.sh` writes to SQLite (`~/.local/share/prompt-library/prompts.db`). `skill-picker.sh` already reads `ai/prompts/*.md` but no prompts exist there.
**Proposal:** `/prompt-score` skill or cron job that:
- Reads prompts.db for prompts with >8 words
- Groups by task type (explore, implement, review, fix)
- Scores by outcome (did the session succeed? did it use skills?)
- Graduates high-scoring prompts to `ai/prompts/<category>.md`
- These then appear in the `Ctrl+A /` skill picker
**File:** `ai/skills/prompt-score/SKILL.md` + `scripts/ai/prompt-graduate.sh`
**Impact:** Self-improving prompt library; best practices auto-surface

#### 4. AI-Assisted Commit Message Generation
**Evidence:** `commit.sh` validates format but doesn't generate. User manually writes every commit subject + body.
**Current state:** `smart-commit` skill exists but only groups files and pushes. No diff-aware message generation.
**Proposal:** Enhance `/smart-commit` to:
- Read staged diff
- Generate conventional commit message (type + scope + subject + body)
- Present for user approval (not auto-commit)
- Fall back to user input if generation is weak
**File:** `ai/skills/smart-commit/SKILL.md` (enhance existing)
**Frequency:** 10-20x/day across all projects

### Tier 2 — Medium Frequency, Medium Savings

#### 5. Session Context Resume
**Evidence:** `session-handoff.md` captures state but model doesn't always read it. `plans-healthcheck.sh` marks it STALE but doesn't force the read.
**Current state:** Advisory hook output (`HANDOFF AVAILABLE: ...`); model often ignores
**Proposal:** Make `session-init.sh` read and inject handoff content directly (not just advise). After injection, delete the handoff file.
**File:** `.claude/hooks/session-init.sh` (enhance)
**Savings:** Eliminates 2-3 turns of "what was I working on?" at session start

#### 6. Checkpoint Keybinding + Skill
**Evidence:** `checkpoint.sh` exists (942 bytes) but no tmux keybinding. Must type full path.
**Current state:** Script stages all + commits with `chore(checkpoint):` + `--no-verify`
**Proposal:**
- Add `Ctrl+A c` tmux keybinding → `checkpoint.sh`
- Add `/checkpoint` slash command for Claude Code
- Enhance to accept optional scope: `/checkpoint auth-refactor`
**Files:** `tmux/tmux.conf` (keybinding), `ai/commands/checkpoint.md` (slash command)
**Frequency:** 3-5x/day during feature work

#### 7. Intent Drift Reporter
**Evidence:** `atomic-status.sh` detects drift (last commit `feat(auth)`, now staging `fix(payment)`) but only reports to hooks. No human-facing summary.
**Current state:** Drift guard is OFF in hook-config.yaml
**Proposal:** `/drift-check` skill that:
- Runs `atomic-status.sh --verbose` 
- Shows current intent vs staged changes
- Suggests: commit current work, or start new atomic unit
- Option to auto-checkpoint before switching context
**File:** `ai/skills/drift-check/SKILL.md`
**Frequency:** When switching between tasks mid-session

#### 8. PR Dashboard Skill
**Evidence:** PR stack skills exist (8 total) but no quick "show me all my open PRs" command across repos.
**Current state:** `az repos pr list` requires org flag + project + output filtering. GH CLI for personal repos.
**Proposal:** `/my-prs` skill that:
- Lists open PRs across configured repos (ADO + GitHub)
- Shows status (draft, approved, needs review, merge conflicts)
- Highlights stack relationships
- Quick action: merge, approve, close
**File:** `ai/skills/my-prs/SKILL.md`
**Frequency:** 2-3x/day (checking PR status)

### Tier 3 — Low Frequency, High Value

#### 9. Task-to-Worktree Linking
**Evidence:** Worktrees and tasks are independent. No "create worktree for this ADO work item" shortcut.
**Current state:** `/stack-create` creates worktree; `/ado-workitem` creates work items. No bridge.
**Proposal:** Enhance `/stack-create` to accept ADO PBI/Task ID:
- Creates worktree named from the work item title
- Links branch to work item via ADO CLI
- Sets up commit template with work item reference
**File:** `ai/skills/stack-create/SKILL.md` (enhance)
**Frequency:** 1-2x/day when starting new feature work

#### 10. Cron-Based Health Reports
**Evidence:** Hook metrics DB has 19,457 events. Prompt DB has 1,382 entries. No periodic summary.
**Current state:** Data collected but never analyzed automatically
**Proposal:** Weekly cron (via Claude Code's `CronCreate`) that:
- Summarizes: most blocked hooks, most wasted tokens, skill usage rates
- Identifies: sessions where Serena was never used, high-Grep sessions
- Outputs: `plans/weekly-health-<date>.md`
**File:** Cron job definition (uses existing metrics.db and prompts.db)
**Frequency:** Weekly (Monday morning)

#### 11. IDE Config Sync Skill
**Evidence:** MCP configs in `.cursor/mcp.json`, `.windsurf/mcp_config.json`, `.mcp.json` — manually maintained per tool.
**Current state:** Symlinks exist for some configs but MCP server lists diverge (voice-mode removed from some but not all)
**Proposal:** `/sync-configs` skill that:
- Reads canonical MCP server list from `pctx.json`
- Generates/updates all IDE-specific MCP configs
- Reports drift between tools
**File:** `ai/skills/sync-configs/SKILL.md`
**Frequency:** When adding/removing MCP servers

---

## Opportunity Matrix

| # | Skill/Enhancement | Frequency | Token Savings | Effort | Priority |
|---|---|---|---|---|---|
| 1 | Skill auto-invocation hook | Every session | 30-50% | Medium | **P0** |
| 2 | Branch/worktree cleanup | Daily | Low (time savings) | Low | **P0** |
| 3 | Prompt learning pipeline | Passive | Compounding | Medium | **P1** |
| 4 | AI commit message gen | 10-20x/day | Low | Low | **P1** |
| 5 | Session context resume | Every session | 2-3 turns saved | Low | **P1** |
| 6 | Checkpoint keybinding | 3-5x/day | Low | Trivial | **P1** |
| 7 | Intent drift reporter | Context switches | Medium | Low | **P2** |
| 8 | PR dashboard | 2-3x/day | Low (time savings) | Medium | **P2** |
| 9 | Task-to-worktree link | 1-2x/day | Low | Medium | **P2** |
| 10 | Weekly health reports | Weekly | Insights | Medium | **P2** |
| 11 | IDE config sync | Ad-hoc | Low | Low | **P3** |

---

## Recommended Execution Order

**Phase 1 (quick wins, do first — 1 session each):**
- #6 Checkpoint keybinding (trivial: 1 line in tmux.conf + command file)
- #2 Branch/worktree cleanup skill (straightforward: list + filter + delete)
- #5 Session context resume (enhance existing session-init.sh)

**Phase 2 (medium effort, high impact — 1-2 sessions each):**
- #1 Skill auto-invocation hook (the biggest lever for token savings)
- #4 AI commit message generation (enhance smart-commit)
- #3 Prompt learning pipeline (connect capture → scoring → graduation)

**Phase 3 (refinements — 1 session each):**
- #7 Intent drift reporter
- #8 PR dashboard
- #9 Task-to-worktree linking
- #10 Weekly health reports
- #11 IDE config sync

---

## Files Modified (Phase 1 only)

| File | Change |
|---|---|
| `tmux/tmux.conf` | Add `Ctrl+A c` → checkpoint.sh keybinding |
| `ai/commands/checkpoint.md` | New slash command for Claude Code |
| `ai/skills/cleanup/SKILL.md` | New skill: branch/worktree cleanup |
| `.claude/hooks/session-init.sh` | Read + inject handoff content, then delete |

---

## Validation

- **#1**: After deploying skill-trigger-reminder hook, run a session with explore/explain prompts → verify hints appear
- **#2**: Run `/cleanup` in a project with stale worktrees → verify only merged/inactive branches offered
- **#3**: Check `ai/prompts/` after graduation runs → verify templates appear in `Ctrl+A /` picker
- **#5**: Start new session with existing `session-handoff.md` → verify context auto-loaded (not just advised)
- **#6**: Press `Ctrl+A c` in tmux → verify checkpoint commit created
