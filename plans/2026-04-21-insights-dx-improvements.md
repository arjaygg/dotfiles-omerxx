# RFC-DOTFILES-002: Developer Experience Improvements — Post-Insights Action Plan

**Status:** Approved — implementation in progress  
**Date:** 2026-04-21  
**Author:** arjaygg  
**Source data:** Claude Code Insights reports, Apr 1–21 2026 (3,951 messages / 322 sessions / 20 days)

---

## 1. Summary

This RFC catalogs the actionable improvements surfaced by two Claude Code Insights reports covering April 2026. It converts qualitative observations and quantitative friction signals into a prioritized backlog of hook, skill, and workflow changes. The implementation should be sequenced from highest-ROI (sessions saved) to lowest (quality-of-life).

---

## 2. Problem Statement

### 2.1 Observed Friction (by frequency)

| Signal | Instances | Session Cost |
|---|---|---|
| Wrong Approach | 34 | High — requires interrupt + re-entry |
| Buggy Code | 24 | Medium — follow-up PRs |
| Misunderstood Request | 8 | Medium — compound requests misinterpreted |
| CI polling interruptions | 4+ sessions not_achieved | High — setup work discarded |
| Wrong remote/auth | 3+ sessions | Medium — mid-flow corrections |
| File Too Large errors | 77 | Low — recoverable but noisy |
| Excessive Changes | 4 | Medium — scope creep, rework |

### 2.2 Tool Usage Imbalance

- **Bash: 8,443 calls vs Edit: 1,664** (5.1x ratio; target: ≤2x for structured workflows)
- Bash dominance means exploratory shell work that Serena/LeanCtx/GitHub MCP should own
- `pre-tool-gate-v2.sh` blocks some patterns but 8,443 calls represent volume that hooks cannot fully absorb

### 2.3 Infrastructure Already In Place

The following are **already implemented** and must not be re-built:

- `pre-tool-gate-v2.sh` — consolidated Bash anti-pattern + session-init gate
- `violation-tracker.sh` + `violation-analysis.sh` — SQLite-backed enforcement telemetry
- `pr-title-conventional-guard.sh` — Conventional Commits title guard on `gh pr create`
- `post-read-auto-delete.sh` — auto-deletes `session-handoff.md` after Read (Fix 1 ✅)
- External CLI pipe exception in `tool-priority.md` §0 (Fix 2 ✅)
- Stack skills: create, merge, sync, update, doctor, navigate, clean, status, pr-all, auto-pr-merge
- Session skills: session-done, session-next, session-defer, session-picker, resume-context
- CI/CD skills: ci-monitor, migration-watchdog, quarantine-triage-live

### 2.4 Known Pending Work (from 2026-04-18 plan)

- **Fix 3** — auc-conversion `AGENTS.md`: add Advisor Trigger section + Task Tracking Discipline section
- **Fix 4** — `plans-healthcheck.sh`: detect stale `active-context.md` (>1 day without update)
- **Backlog T1** — `create-stack.sh` base branch default (should use current branch, not main)
- **Backlog T3** — `merge-stack.sh` GitHub-only rewrite + `gh-account.sh` integration
- **Backlog T5** — tmux window-exists check in `stack-navigate` + `stack-create`
- **Backlog T8** — `stack-auto-pr-merge`: fix Python `Task()` → Agent tool syntax

---

## 3. Goals

1. Eliminate CI polling session losses — fire-and-forget CI monitoring so interrupting the main session doesn't discard work.
2. Reduce wrong-remote detours — a pre-push hook that verifies remote+auth before any git push or PR creation.
3. Reduce File Too Large errors — intercept Read on large files before they fail.
4. Guard against Misunderstood Requests — lightweight echo-back protocol for compound requests.
5. Guard against Excessive Changes — scope-check gate before Claude executes a multi-file plan.
6. Complete the 2026-04-18 session-hygiene plan (Fix 3 + Fix 4).
7. Drain the stack-skill backlog (T1, T3, T5, T8).
8. Surface violation telemetry into actionable session-end feedback.
9. (Horizon) Lay the groundwork for an autonomous `/stack-ship` pipeline.

## 4. Non-Goals

- Replacing Serena with another LSP tool
- Cross-repo fleet refactor automation (Horizon item, depends on §3.1–3.4 being stable)
- Changes to auc-conversion Go code

---

## 5. Technical Design

### 5.1 Fire-and-Forget CI Monitor (P1)

**Problem:** 4+ sessions interrupted mid-CI-poll because Claude runs `gh run watch` synchronously.  
**Solution:** A `/ci-watch` skill that launches a background headless agent and returns immediately.

```
ai/skills/ci-watch/SKILL.md
```

Behavior:
1. Detects current PR from `git branch --show-current` + `gh pr view`
2. Launches `claude -p "..." --allowedTools Bash,Read,Write --output-format stream-json` as a background process writing status to `plans/ci-status.md`
3. Prints the PID and location of status file, returns to user immediately
4. Background agent: polls CI max 10 times at 90s intervals; on green → deploys to DEV; writes final status to `plans/ci-status.md`; sends macOS notification via `osascript`
5. User checks status with `/ci-status` (trivial skill: reads `plans/ci-status.md`)

**Accepts:** Running `/ci-watch` returns within 5 seconds; `plans/ci-status.md` is updated within 3 minutes of CI completing.

---

### 5.2 Remote Pre-flight Hook (P1)

**Problem:** Claude assumes wrong remote (GitHub vs ADO vs GHE) 3+ times per month.  
**Solution:** PreToolUse hook on Bash commands matching `git push|gh pr create|az repos pr create`.

```
.claude/hooks/pre-push-remote-check.sh
```

Behavior:
1. Intercepts Bash commands matching `(git push|gh pr create|gh pr edit|az repos pr)`
2. Runs `git remote -v` and `gh auth status` non-interactively
3. Prints a one-line summary: `Remote: origin → github.com/bofaz/auc-conversion (gh: arjaygg)`
4. If remote is ADO but branch matches auc-conversion pattern → warn + ask for confirmation via stderr
5. Does NOT block — warn-only (exit 0); blocking would be too aggressive given multi-repo work

Registration in `settings.json`:
```json
{ "matcher": "Bash", "hooks": [{ "type": "command", "command": "~/.dotfiles/.claude/hooks/pre-push-remote-check.sh" }] }
```

**Accepts:** A `git push` to the wrong remote prints a warning with the correct remote identified. No false positives on legitimate pushes.

---

### 5.3 File-Too-Large Read Interceptor (P2)

**Problem:** 77 "File Too Large" errors across 20 days — Read called on files that should go through `ctxSmartRead`.  
**Solution:** Extend `pre-tool-gate-v2.sh` Section 1 with a file-size pre-check that suggests `ctxSmartRead`.

Files in scope: any file Read where size > 500KB OR filename matches `*_repomix_*`, `*.sum`, `*-lock.*`.

Behavior:
- Detect file size via stat before Read proceeds
- For >500KB: block with message: `File is Xkb — use LeanCtx.ctxSmartRead("path") for analysis-only reads`
- For exact locks/generated files: block unconditionally (no analysis value)

**Accepts:** `Read` on a file >500KB is blocked with a helpful redirect. `Read` on normal-sized files is unaffected.

---

### 5.4 Echo-Back Protocol for Compound Requests (P2)

**Problem:** 8 Misunderstood Request events — terse compound requests get partially misinterpreted.  
**Solution:** CLAUDE.md rule addition (not a hook — this is a behavioral instruction).

Add to `ai/rules/agent-user-global.md` § Working Style:

```markdown
## Compound Request Echo-Back
For any request containing 2+ distinct actions joined by AND/THEN/ALSO/PLUS, before taking any action:
1. Print a one-line interpretation: "I understand: (1) X, (2) Y, (3) Z"
2. Proceed immediately — do NOT wait for confirmation unless actions are destructive
```

This adds ~5 tokens overhead per compound request and prevents 15-minute course-corrections.

**Accepts:** A request like "fix the build, deploy to DEV, and confirm health" produces an echo before any tool calls.

---

### 5.5 Scope Gate for Multi-File Plans (P2)

**Problem:** 4 Excessive Changes instances — Claude over-scopes fixes, touching unrelated files.  
**Solution:** Add a pre-execution scope declaration requirement for tasks touching >3 files.

Extend `pre-tool-gate-v2.sh` or add a new `UserPromptSubmit` hook:
- When a response contains >3 Edit/Write tool calls planned in sequence → emit a warning to stdout: `Scope: N files planned. If this exceeds the request's intent, confirm with user.`
- This is advisory (stdout, not blocking) — surfaces the count before user reviews the plan

Alternative: Add to `ai/rules/agent-user-global.md`:
```markdown
## Scope Declaration  
Before editing >3 files: list the files and why each is in scope. Stop if any are not obviously connected to the request.
```

**Decision:** Prefer the CLAUDE.md rule (zero hook overhead, behavioral fix at the right layer per ADL-009).

**Accepts:** A fix request touching 5 files produces a file list before edits begin.

---

### 5.6 Pending Session-Hygiene Fixes (P1 — carry-forward)

#### Fix 3 — auc-conversion AGENTS.md

**File:** `/Users/axos-agallentes/git/auc-conversion/AGENTS.md`

Add two sections:
```markdown
## Advisor Trigger Conditions
Call `advisor()` before: architecture decisions, first tool call on a new file, any change to a public API, 
any migration touching production data, and before declaring a multi-step task complete.

## Task Tracking Discipline  
For 3+ step tasks: create a TodoWrite list before executing. Mark in_progress when starting, 
completed when done. Do NOT use TaskCreate (spawns agents). Do NOT stop until all items complete.
```

**Accepts:** A session in auc-conversion with a 3-step task produces a TodoWrite list before execution begins.

#### Fix 4 — plans-healthcheck.sh stale active-context.md detection

**File:** `.claude/hooks/plans-healthcheck.sh`

Current gap: healthcheck warns about missing files but doesn't detect an `active-context.md` that hasn't been updated today.

Add logic:
```bash
if [ -f "plans/active-context.md" ]; then
  last_mod=$(stat -f "%Sm" -t "%Y-%m-%d" plans/active-context.md 2>/dev/null)
  today=$(date +%Y-%m-%d)
  if [ "$last_mod" != "$today" ]; then
    echo "STALE: plans/active-context.md last updated $last_mod — update it to reflect current session state"
  fi
fi
```

**Accepts:** A session starting with an `active-context.md` last updated yesterday shows a STALE warning in the hook output.

---

### 5.7 Stack Skill Backlog (P3)

#### T1 — create-stack.sh base branch default
**File:** `.claude/scripts/pr-stack/create-stack.sh`  
Change: When no base branch is specified, default to `git branch --show-current` (not hardcoded `main`).

#### T3 — merge-stack.sh GitHub-only rewrite
**File:** `.claude/scripts/pr-stack/` (new or modified script)  
Change: Remove ADO-specific logic; always use `gh pr merge` + `gh-account.sh` for account resolution. Add guard: if remote is not GitHub, print error and exit.

#### T5 — tmux window-exists check
**Files:** `ai/skills/stack-navigate/SKILL.md`, `ai/skills/stack-create/SKILL.md`  
Change: Before `tmux new-window`, run `tmux list-windows | grep -q "<name>"` and skip creation if window exists.

#### T8 — stack-auto-pr-merge Python Task() → Agent tool
**File:** `ai/skills/stack-auto-pr-merge/SKILL.md`  
Change: Replace `Task(...)` syntax (Python SDK idiom) with the correct Agent tool call pattern used in all other skills.

---

### 5.8 Violation Telemetry Surfacing (P3)

**Problem:** `violation-tracker.sh` and `violation-analysis.sh` exist but their data isn't surfaced in normal workflow — violations are logged but not actioned.  
**Solution:** Wire `violation-analysis.sh` into `session-end.sh` (Stop hook) to append a summary line to `plans/session-handoff.md`.

Add to `session-end.sh`:
```bash
# Append violation summary if tracker DB exists
if command -v violation-analysis.sh &>/dev/null; then
  violation-analysis.sh summary >> plans/session-handoff.md 2>/dev/null || true
fi
```

**Accepts:** After a session with at least one hook violation, the handoff file includes a "Violations this session: N" line.

---

### 5.9 Horizon: /stack-ship Groundwork (P4)

**Not implemented in this RFC.** Pre-conditions must be met first:
- T3 (merge-stack GitHub-only) must be stable
- T5 (tmux window guard) must be fixed
- `ci-watch` background agent (§5.1) must have shipped and been used in 3+ real sessions
- Hook coverage for scope-gate (§5.5) must be live

Once pre-conditions are met, `/stack-ship` can be designed as a separate RFC.

---

## 6. Backlog (Ordered by Priority)

```
PRIORITY 1 — Highest session ROI
──────────────────────────────────
[ ] B-01  Fix 3: auc-conversion AGENTS.md (Advisor Triggers + Task Tracking)
[ ] B-02  Fix 4: plans-healthcheck.sh stale active-context.md detection
[ ] B-03  ci-watch skill + ci-status skill (fire-and-forget CI monitoring)
[ ] B-04  pre-push-remote-check.sh hook (remote/auth pre-flight)

PRIORITY 2 — Reduces recurring noise
──────────────────────────────────────
[ ] B-05  File-Too-Large Read interceptor in pre-tool-gate-v2.sh
[ ] B-06  Echo-back protocol rule in agent-user-global.md
[ ] B-07  Scope declaration rule in agent-user-global.md

PRIORITY 3 — Stack skill fixes
────────────────────────────────
[ ] B-08  T1: create-stack.sh base branch default fix
[ ] B-09  T3: merge-stack.sh GitHub-only rewrite
[ ] B-10  T5: tmux window-exists check in stack-navigate + stack-create
[ ] B-11  T8: stack-auto-pr-merge Agent tool syntax fix

PRIORITY 4 — Telemetry + Horizon
──────────────────────────────────
[ ] B-12  Wire violation-analysis.sh into session-end.sh
[ ] B-13  /stack-ship RFC (unblock after B-03, B-04, B-09, B-10 are stable)
```

---

## 7. Implementation Sequence

```
Session 1 (dotfiles, new branch: chore/insights-enforcement-apr21):
  B-01 → B-02 → B-04 → B-05 → B-06 → B-07
  Commit each as atomic PR; merge via stack-pr-all

Session 2 (dotfiles + auc-conversion, separate branches):
  B-03 (ci-watch skill)
  B-08, B-09, B-10, B-11 (stack script fixes)

Session 3:
  B-12 (violation telemetry wiring)
  B-13 (stack-ship pre-conditions review → RFC if ready)
```

---

## 8. Key Files

| File | Action | Item |
|---|---|---|
| `ai/rules/agent-user-global.md` | Add echo-back + scope declaration rules | B-06, B-07 |
| `.claude/hooks/pre-tool-gate-v2.sh` | Add File-Too-Large interceptor in Section 1 | B-05 |
| `.claude/hooks/plans-healthcheck.sh` | Add stale active-context.md detection | B-02 |
| `.claude/hooks/pre-push-remote-check.sh` | Create new warn-only remote check hook | B-04 |
| `.claude/settings.json` | Register pre-push-remote-check.sh for Bash PreToolUse | B-04 |
| `.claude/hooks/session-end.sh` | Wire violation-analysis.sh summary | B-12 |
| `ai/skills/ci-watch/SKILL.md` | Create new skill | B-03 |
| `ai/skills/ci-status/SKILL.md` | Create new skill (reads plans/ci-status.md) | B-03 |
| `.claude/scripts/pr-stack/create-stack.sh` | Base branch default fix | B-08 |
| `.claude/scripts/pr-stack/` | merge-stack.sh GitHub-only | B-09 |
| `ai/skills/stack-navigate/SKILL.md` | tmux window guard | B-10 |
| `ai/skills/stack-create/SKILL.md` | tmux window guard | B-10 |
| `ai/skills/stack-auto-pr-merge/SKILL.md` | Agent tool syntax fix | B-11 |
| `/Users/axos-agallentes/git/auc-conversion/AGENTS.md` | Add two new sections | B-01 |

---

## 9. Verification

Each item has an **Accepts** criterion in §5. End-to-end smoke test:

1. Start session → `active-context.md` stale → healthcheck warns (B-02)
2. Run `git push origin main` → pre-push hook prints remote summary (B-04)
3. `Read` a 600KB file → blocked with ctxSmartRead suggestion (B-05)
4. Send compound request → echo-back line printed before first tool call (B-06)
5. `/ci-watch` → returns in <5s, background agent running (B-03)
6. Session ends → handoff includes violation summary if any violations (B-12)
