# Plan: Session Hygiene Enforcement
**Date:** 2026-04-18  
**Branch:** `chore/enforce-session-hygiene`  
**Scope:** Dotfiles enforcement hooks + auc-conversion AGENTS.md

---

## Context

A deep scan of 38 Claude Code sessions in `auc-conversion` (Apr 15–18) revealed four enforcement gaps that degrade session quality at scale:

1. **676 session-handoff injections per session**: `plans/session-handoff.md` persists across sessions. Hook correctly says "then delete it" but agents don't comply under task pressure — every subsequent session injects a 2-line reminder on every prompt indefinitely.
2. **Pipe-limiter false positives**: `tool-priority.md` Section 0 says "Use the tool's built-in `limit:` param" with no exception for external CLIs (kubectl, gh, az, docker) that have no agent-accessible limit parameter. Valid patterns (`kubectl logs | head -N`) are avoided unnecessarily.
3. **0 advisor calls in 38 sessions**: Generic "call advisor when appropriate" rules are skipped under task pressure. Needs concrete, code-path-specific trigger scenarios.
4. **PRD 8x re-reads from stale active-context**: `plans/active-context.md` in auc-conversion was dated 2026-04-11, describing unrelated dotfiles work. `stale-memory-check.sh` only scans `~/.claude/projects/*/memory/*.md` — it never catches stale `plans/active-context.md`.

**Core principle:** Procedural enforcement > documentation. Text rules that duplicate existing enforcement are noise; hooks and structured triggers change behavior (proven: 0/38 sessions called advisor despite text rule).

**pre-tool-gate-v2.sh Section 2 verified:** Does NOT block `kubectl ... | head -N` or `gh run list | head -5`. The guard only matches commands starting with `grep`, `find`, or `ls`. Fix #2 is doc-only — no hook change needed.

---

## Fix 1 — PostToolUse Auto-Delete for session-handoff.md

**Files:**
- `.claude/hooks/post-read-auto-delete.sh` (create)
- `.claude/settings.json` (add PostToolUse hook entry)

**What it does:** When the Read tool reads any file ending in `plans/session-handoff.md`, immediately `rm -f` it. One-time read → file gone → zero future handoff injections.

**Implementation:**

```bash
#!/usr/bin/env bash
# PostToolUse: Read — auto-delete session-handoff.md after it is consumed
set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

[[ "$TOOL_NAME" != "Read" ]] && exit 0

if [[ "$FILE_PATH" == *"plans/session-handoff.md" && -f "$FILE_PATH" ]]; then
    rm -f "$FILE_PATH"
    echo "[auto-cleanup] Deleted $FILE_PATH — handoff context consumed." >&2
fi
```

Register in `.claude/settings.json` under `hooks.PostToolUse`:
```json
{
  "matcher": "Read",
  "hooks": [{"type": "command", "command": "bash /Users/axos-agallentes/.dotfiles/.claude/hooks/post-read-auto-delete.sh"}]
}
```

**Accepts:** Create `plans/session-handoff.md`, read it via Read tool, confirm file is deleted, start new prompt and confirm "HANDOFF AVAILABLE" no longer appears.

---

## Fix 2 — tool-priority.md: External CLI Pipe Exception

**Files:** `ai/rules/tool-priority.md`

**What it does:** Add explicit exception row and note to Section 0 for external CLIs.

**Change — add after "Limit any piped output" row in Section 0 table:**

```markdown
| Limit output from external CLI (kubectl, gh, az, docker) | N/A — no agent-accessible `limit:` param | Pipe to `head -N` is correct; not an anti-pattern |
```

**Change — add note below Section 0 table:**

```markdown
**External CLI exception:** For commands invoking external tools (kubectl, gh, az, docker, jq, curl) where no `limit:` parameter exists for the agent, piping to `head -N` is the correct pattern and is explicitly permitted.
```

**Accepts:** Confirm table reads clearly, `kubectl logs ... | head -20` pattern is documented as valid.

---

## Fix 3 — auc-conversion AGENTS.md: Code-Path Advisor Triggers + Task Tracking

**Files:** `/Users/axos-agallentes/git/auc-conversion/AGENTS.md`

**What it does:** Add two sections with concrete, code-path-specific rules — NOT generic behavioral guidelines.

**Section: Task Tracking Discipline**

```markdown
## Task Tracking Discipline

When spawning subagents for multi-step work:
1. Create the task list first: `TaskCreate` with all subtasks
2. Export `CLAUDE_CODE_TASK_LIST_ID=<id>` in each subagent's environment
3. Each subagent uses `TaskUpdate` (not a new `TaskCreate`) to report progress
4. The orchestrator polls `TaskGet` before aggregating results

Never abandon a `TaskCreate` list — orphaned lists accumulate across sessions. Mark cancelled tasks with status `cancelled`.
```

**Section: Advisor Trigger Scenarios**

```markdown
## Advisor Trigger Scenarios

Call `advisor` (no arguments — reads full context automatically) before:

- **Changing FK resolution strategy** in `pkg/migration/` or `pkg/queue/` — blast radius spans dequeuing, retry, and idempotency
- **Modifying `pkg/worker/pool.go` worker lifecycle** — affects queue saturation, backpressure, and DB contention
- **Adding or removing a DB index** on conversion or transaction tables — irreversible without a migration window
- **Changing queue dequeue logic** (`pkg/queue/dequeue*.go`) — affects throughput guarantees and ordering invariants
- **Cross-package interface changes** spanning >3 call sites — use `Serena.findReferencingSymbols` first, then advisor if blast radius is high

These are checkpoints, not bureaucracy. An advisor call costs ~2s and prevents expensive rollbacks.
```

**Accepts:** Read AGENTS.md and confirm both sections are present with specific file paths/patterns.

---

## Fix 4 — plans-healthcheck.sh: Detect Stale active-context.md

**Files:** `.claude/hooks/plans-healthcheck.sh`

**What it does:** Extend existing check to flag `plans/active-context.md` older than 3 days in the current working directory.

**Add after the `has_handoff` logic block, before final output assembly:**

```bash
# Stale active-context.md check
ACTIVE_CTX="${CWD}/plans/active-context.md"
if [[ -f "$ACTIVE_CTX" ]]; then
    MTIME=$(stat -f%m "$ACTIVE_CTX" 2>/dev/null || stat -c%Y "$ACTIVE_CTX" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE_DAYS=$(( (NOW - MTIME) / 86400 ))
    if [[ "$AGE_DAYS" -ge 3 ]]; then
        stale+=("plans/active-context.md is ${AGE_DAYS}d old — update or delete before starting new work")
    fi
fi
```

**Accepts:** Run `touch -t 202604110000 plans/active-context.md` in auc-conversion, submit a prompt, confirm stale warning appears. Update the file, confirm warning clears.

---

## Deferred (Out of Scope)

- `db-migration-verify` skill — targets auc-conversion codebase, not dotfiles
- `ci-triage` skill — CI patterns not yet stable
- `worktree-startup` skill — hooks already cover session init
- `todo-gate.sh` default: "warn"→"block" — risk of false positives without more data
- `TaskCreate` orphan detection stop hook — insufficient signal to justify stop hook

---

## Execution Order

| # | Fix | Repo | Effort |
|---|-----|------|--------|
| 1 | PostToolUse auto-delete hook | dotfiles | ~15 min |
| 2 | tool-priority.md external CLI exception | dotfiles | ~5 min |
| 4 | plans-healthcheck.sh staleness check | dotfiles | ~15 min |
| 3 | auc-conversion AGENTS.md sections | auc-conversion | ~10 min |

Fixes 1, 2, 4 → single branch `chore/enforce-session-hygiene` in dotfiles.  
Fix 3 → separate branch in auc-conversion repo.
