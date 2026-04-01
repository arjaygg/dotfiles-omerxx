# Hook System Deep Analysis & Optimization Plan

## Context

The Claude Code hook system (31+ scripts, 10 event types) is the enforcement backbone of this dotfiles project. Prior work on `feat/tool-call-hooks-optimization` fixed correctness bugs (stderr->stdout, dead code, exit codes). This plan addresses **performance** and **ROI** — the system works correctly now, but every tool call pays a tax of 5-8 hook executions spawning 7+ external processes.

---

## System Audit: What Fires Per Tool Call

| Tool Call | PreToolUse Hooks | PostToolUse Hooks | Total Processes |
|-----------|-----------------|-------------------|-----------------|
| **Bash**  | pre-tool-gate.sh (python3+git+stat), pretooluse.mjs (Node) | post-tool-handler.sh (3x python3), bash-output-guard.sh (python3), posttooluse.mjs (Node) | **~9 processes** |
| **Edit**  | pre-tool-gate.sh (python3+git), edit-without-read.sh (python3), plan-scope-gate.sh (jq) | posttooluse.mjs (Node) | **~5 processes** |
| **Read**  | pre-tool-gate.sh (python3), serena-tool-priority.sh (python3) | read-tracker.sh (python3), posttooluse.mjs (Node) | **~5 processes** |
| **Grep/Glob** | pre-tool-gate.sh (python3), serena-tool-priority.sh (python3) | posttooluse.mjs (Node) | **~4 processes** |
| **Write** | pre-tool-gate.sh (python3+git), plan-naming-enforcer.ts (bun), plan-scope-gate.sh (jq) | posttooluse.mjs (Node) | **~5 processes** |

**Plus:** Each hook that sources `hook-metrics.sh` does a grep on `hook-config.yaml` AND a SQLite INSERT.

---

## Bottleneck #1: python3 Startup (~50-100ms each)

The dominant cost. Python3's startup on macOS is 50-100ms — heavier than any hook logic. Current python3 usage:

| Hook | python3 Calls | What It Does |
|------|--------------|--------------|
| pre-tool-gate.sh | 1 | JSON field extraction (tool_name, file_path, command, limit) |
| post-tool-handler.sh | 3-4 | tool_name, output extraction, JSON emit, cmd+exit_code |
| bash-output-guard.sh | 1 | line_count + command extraction |
| serena-tool-priority.sh | 1 | tool_name, file_path, pattern, limit |
| edit-without-read.sh | 1 | tool_name, file_path |
| read-tracker.sh | 1 | file_path |
| pctx-batch-tracker.sh | 2 | tool_name, session_id |
| hook-metrics.sh (hook_block) | 1 | JSON `{decision:block}` emission |
| plans-healthcheck.sh | 2 | pctx.json parse, output formatting |

**Fix:** Replace with `jq` (~5ms startup). Single jq call per hook for all field extraction.

---

## Bottleneck #2: Redundant Work

| Redundancy | Hooks Involved | Waste |
|-----------|---------------|-------|
| Output line counting | post-tool-handler.sh + bash-output-guard.sh | Both extract output text, both count lines, both warn about large output |
| hook-config.yaml reads | Every hook that sources hook-metrics.sh | File is grep'd on every invocation (4-7x per tool call) |
| SQLite INSERTs | hook_metric() in hook-metrics.sh | 4-7 DB opens+writes per tool call |
| pctx config check | serena-tool-priority.sh | Runs on every Grep/Glob/Read even when pctx isn't configured |
| plan-state.json check | plan-scope-gate.sh | Runs jq on every Edit/Write even when no plan is active |

---

## Bottleneck #3: `bash -lc` Wrapper

Every hook is launched via `bash -lc 'bash "..."'` which loads the full login profile (`.bash_profile`, `.bashrc`, etc.) before executing. This adds ~30-50ms per hook. For hooks that don't need login env (most of them), plain `bash` would suffice.

**However:** This requires testing — some hooks call `python3`, `git`, `jq` which need PATH from the login shell. If jq/git are in standard locations (`/usr/bin`, `/usr/local/bin`), the `-l` flag is unnecessary.

---

## ROI Assessment: Is Each Hook Earning Its Keep?

### High ROI (keep, optimize)
| Hook | Why | Action |
|------|-----|--------|
| pre-tool-gate.sh (bash-tool-gate) | Blocks cat/head/tail/grep/find/ls — direct token savings | Optimize JSON parsing |
| post-tool-handler.sh | Compacts >300-line output — massive context savings | Merge bash-output-guard into it |
| read-tracker.sh + edit-without-read.sh | Prevents blind edits, catches real mistakes | Optimize JSON parsing |
| plans-healthcheck.sh | Once-per-prompt, catches missing artifacts | Keep (already efficient enough) |

### Medium ROI (keep with caveats)
| Hook | Why | Caveat |
|------|-----|--------|
| serena-tool-priority.sh | Nudges toward Serena | At `block` level but uses `exit $_EXIT_CODE` not `hook_block()` — **broken enforcement**. Fix required. |
| check-agent-parallelism.sh | Prevents serial agent misuse | Already uses jq, lightweight |
| plan-scope-gate.sh | Blocks out-of-scope edits | High overhead for rare utility. Needs fast-path exit. |
| pctx-batch-tracker.sh | Encourages batching | pctx at <1% usage means this almost never fires. Disable until adoption rises. |

### Low ROI (merge or disable)
| Hook | Why | Action |
|------|-----|--------|
| bash-output-guard.sh | 100% redundant with post-tool-handler.sh | Merge into post-tool-handler.sh, delete |
| context-monitor.sh | Notification events only | Keep (negligible overhead) |
| prompt-parallelism-hint.sh | Once per session | Keep (negligible overhead) |

### Bug: serena-tool-priority.sh Enforcement
The hook uses `exit "$_EXIT_CODE"` (which is 2 for `block` level) but prints reasons via `echo` to stdout. Exit code 2 means "blocked" to Claude Code, but Claude expects the block reason on stderr (or in JSON `{decision:block}` format on stdout). The current code blocks the tool but Claude doesn't see why. **Must migrate to `hook_block()` or JSON output.**

---

## Optimization Plan: 5 Phases

### Phase 1 — Replace python3 with jq (Highest Impact)
**Files:** pre-tool-gate.sh, post-tool-handler.sh, bash-output-guard.sh, serena-tool-priority.sh, edit-without-read.sh, read-tracker.sh, pctx-batch-tracker.sh, hook-metrics.sh
**Accepts:** All hooks parse JSON via jq. No python3 calls in per-tool-call hooks. Same behavior verified via existing test fixtures.
**Estimated savings:** 240-360ms per Bash call, 100-200ms per Edit/Read call

### Phase 2 — Merge bash-output-guard into post-tool-handler
**Files:** post-tool-handler.sh, bash-output-guard.sh (delete), settings.json, hook-config.yaml
**Accepts:** post-tool-handler.sh has 3-tier output handling (compact >300, hint 50-300, pass <50). bash-output-guard.sh removed from settings.json.
**Estimated savings:** 80-120ms per Bash call

### Phase 3 — Fast-Path Exits and Lazy Init
**Files:** plan-scope-gate.sh, serena-tool-priority.sh, pre-tool-gate.sh, hook-metrics.sh, session-init.sh
**Changes:**
- plan-scope-gate.sh: `[[ -f plans/plan-state.json ]] || exit 0` before `cat`
- serena-tool-priority.sh: pctx config check before `cat`
- hook-config.yaml: pre-parsed to flat env file at session start
- hook-metrics.sh: guard `_ensure_db()` after first call
**Accepts:** Hooks that can't fire exit in <1ms. hook-config.yaml read once per session.
**Estimated savings:** 20-80ms per tool call

### Phase 4 — SQLite Metrics to Flat File
**Files:** hook-metrics.sh, session-end.sh
**Changes:** `hook_metric()` appends to `/tmp/.claude-hook-metrics-*.log` instead of SQLite. `session-end.sh` bulk-imports on shutdown.
**Accepts:** `hook-metrics.sh summary` still works. No SQLite on hot path.
**Estimated savings:** 25-75ms per tool call

### Phase 5 — Fix serena-tool-priority.sh + Disable pctx-batch-tracker
**Files:** serena-tool-priority.sh, hook-config.yaml
**Changes:**
- serena-tool-priority.sh: use `hook_block()` for block-level enforcement
- pctx-batch-tracker: set to `off` in hook-config.yaml
**Accepts:** Serena hints actually block tools at `block` level. pctx-batch-tracker overhead eliminated.

---

## Total Expected Savings

| Tool Call | Current Overhead (est.) | After All Phases | Reduction |
|-----------|------------------------|------------------|-----------|
| Bash | ~700-900ms | ~200-300ms | **60-65%** |
| Edit | ~400-500ms | ~100-200ms | **60-70%** |
| Read | ~350-450ms | ~80-150ms | **60-70%** |
| Grep/Glob | ~300-400ms | ~60-120ms | **70-75%** |

---

## The Deeper Question: Are Hooks Teaching or Just Blocking?

The system has **three enforcement layers** — and the data suggests they're not aligned:

| Layer | Mechanism | When It Acts | Can Claude Learn? |
|-------|-----------|-------------|-------------------|
| `settings.json` deny list | Hard permission block | Before hook fires | No — Claude gets "permission denied", no reason |
| PreToolUse hooks | Block (exit 2/JSON) or warn (exit 0) | Before tool executes | Partially — sees stdout message as system-reminder |
| CLAUDE.md / AGENTS.md instructions | In-context rules | During planning | Yes — Claude reasons about rules when choosing tools |

**Key evidence of misalignment:**
- `Bash(cat *)`, `Bash(head *)`, `Bash(tail *)`, `Bash(rg *)` are in the deny list AND in `pre-tool-gate.sh` — **dead code** in the hook since deny list fires first
- `serena-tool-priority.sh` is at `block` level, yet Bash remains at 41% and pctx at <1% — **hints are not producing behavioral change**
- `tool-priority.md` is loaded via CLAUDE.md as an instruction, AND hooks enforce the same rules — but the instruction is more nuanced ("use Serena for symbol lookups") while the hook pattern-matches crudely

### The Core Insight: Hooks Are Scaffolding, Not Architecture

Hooks exist to **train behavioral patterns**. Once Claude consistently follows a rule via instruction-level compliance (choosing Read without ever trying cat), the hook becomes pure overhead. The system needs:
1. **Measurement** of whether hooks are teaching or just walling
2. **Graduation** from hook enforcement to instruction-only when rules are learned
3. **Memory reinforcement** for persistently violated rules

---

## Phase 6 — Validation Framework (`claude -p` Integration Tests)

### Unit Tests (Hook Logic)
Existing fixture-based tests validate hook scripts in isolation. Extend coverage:
```
fixtures/pre-tool-gate/bash-find.exit2.json     # find → Glob
fixtures/pre-tool-gate/bash-ls.exit2.json        # ls → Glob
fixtures/pre-tool-gate/bash-head.exit2.json      # head → Read
fixtures/pre-tool-gate/bash-rg.exit2.json        # rg → Grep
fixtures/pre-tool-gate/bash-git-status.exit0.json # git status → pass
fixtures/pctx-batch-tracker/single-serena.exit0.json
```

### Integration Tests (End-to-End Behavior via `claude -p`)

These test whether Claude **adapts** after a hook fires, not just whether the hook fires correctly:

```bash
# hook-integration-test.sh — run via: bash .claude/hooks/hook-integration-test.sh

SCENARIO_1="Show me the contents of src/main.go"
# Expected: Claude uses Read tool (not Bash cat)
# Pass: Read tool in transcript, no Bash(cat)

SCENARIO_2="Find all TODO comments in the codebase"
# Expected: Claude uses Grep tool (not Bash grep)
# Pass: Grep tool in transcript, no Bash(grep)

SCENARIO_3="List all TypeScript files"
# Expected: Claude uses Glob (not Bash ls/find)
# Pass: Glob in transcript, no Bash(ls) or Bash(find)

SCENARIO_4="Find the definition of HandleRequest function"
# Expected: Serena.findSymbol preferred over Grep
# Pass: pctx/Serena call in transcript

SCENARIO_5="Commit the current changes" (on main)
# Expected: Claude is blocked, suggests branch creation
# Pass: Block message in transcript, no git commit executed

SCENARIO_6="Change foo to bar in src/handler.go"
# Expected: Read precedes Edit in transcript
# Pass: Read(handler.go) before Edit(handler.go)
```

Each test runs `claude -p "<prompt>" --output-format jsonl` and parses the transcript JSONL to classify behavior.

### Transcript Analyzer

A script `analyze-transcript.py` that reads JSONL and produces:
- Tool usage distribution (% Bash vs Read vs Grep vs Glob vs pctx)
- Block-then-recover sequences (hook taught Claude)
- Block-then-repeat sequences (hook is just a wall)
- Preemptive compliance (Claude followed rule without being blocked)

---

## Phase 7 — Learning Effectiveness Metrics (LES)

### Classification of Tool Call Sequences

| Pattern | Description | Score |
|---------|-------------|-------|
| **Preemptive Compliance** | Claude uses correct tool without trying blocked one | +2 (instruction learning) |
| **Block-then-Recover** | Tries blocked tool, gets blocked, switches correctly | +1 (hook teaching) |
| **Warn-then-Adapt** | Sees warning, changes approach next time | +1 (warning effective) |
| **Warn-then-Ignore** | Sees warning, repeats same pattern | -1 (warning is noise) |
| **Block-then-Repeat** | Tries blocked tool, gets blocked, tries again | -2 (hook is just a wall) |

### Learning Effectiveness Score (LES) Per Hook

```
LES = (2×preemptive + 1×recover + 1×adapt - 1×ignore - 2×repeat) / total_events
```

Range: -2.0 (pure wall) to +2.0 (pure instruction learning). **Target: > 0.5**

### Enhanced Metrics Schema

```sql
-- New columns in hook_events
ALTER TABLE hook_events ADD COLUMN violation_pattern TEXT DEFAULT '';
ALTER TABLE hook_events ADD COLUMN sequence_position INTEGER DEFAULT 0;

-- New table for behavioral classification
CREATE TABLE learning_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    session_id TEXT NOT NULL,
    hook_name TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'preemptive', 'block_recover', 'warn_adapt', 'warn_ignore', 'block_repeat'
    blocked_tool TEXT DEFAULT '',
    recovery_tool TEXT DEFAULT ''
);
```

### New CLI Command: `hook-metrics.sh effectiveness`

```
Hook Effectiveness Report (last 30 days)
═══════════════════════════════════════════
hook                    LES   preempt  recover  repeat  trend
bash-tool-gate          1.4   45       5        2       stable
edit-without-read       0.8   20       3        1       improving
serena-tool-priority    0.3   12       8        15      declining ⚠
pctx-batch-tracker     -0.2   2        1        8       flat ⚠
```

---

## Phase 8 — Hook vs Instruction Layering

### Where Each Rule Should Live

| Rule | Primary Layer | Secondary Layer | Rationale |
|------|-------------|-----------------|-----------|
| Don't use cat/head/tail/rg | `settings.json` deny list | Brief CLAUDE.md note | Binary pattern. Deny list = zero overhead. Hook is redundant dead code. |
| Don't use grep/find/ls | `settings.json` deny list + hook | Brief CLAUDE.md note | Add to deny list. Keep hook only for `ls -l` exception. |
| Prefer Serena over Grep | CLAUDE.md instruction (detailed) | Hook (warn) | Requires judgment — not all Grep should use Serena. Instruction teaches _when_. |
| Use context-mode for large output | Hook (warn, PostToolUse) | CLAUDE.md instruction | Hook detects after the fact. Instruction teaches proactive use. Both needed. |
| Batch pctx calls | CLAUDE.md instruction | Disable hook | Batching requires planning ahead — instruction territory. Hook can only detect sequentially after the fact. |
| Don't commit to main | Hook (block) | Brief CLAUDE.md note | Binary detection. Hook is the right enforcement point. |
| Read before Edit | Hook (warn) | CLAUDE.md brief mention | Detectable pattern. Advisory is appropriate. |
| TodoWrite for multi-step | CLAUDE.md instruction | Hook (advisory nudge) | Requires understanding task complexity. Instruction is primary. |

### Critical Finding: Deny List Overlap

`settings.json` already blocks `Bash(cat *)`, `Bash(head *)`, `Bash(tail *)`, `Bash(rg *)`. These never reach `pre-tool-gate.sh`. Lines 65-82 of that hook are **dead code** — they add JSON parsing overhead for patterns that are pre-blocked.

**Action:** Remove redundant checks from `pre-tool-gate.sh`. Add `Bash(grep *)`, `Bash(find .*)` to deny list (keep `ls -l*` exception in hook).

---

## Phase 9 — Memory as Reinforcement + Auto-Graduation

### When Hooks Should Generate Memories

| Trigger | Memory Type | Example |
|---------|------------|---------|
| `block_then_repeat` > 3x in session | `feedback` | "In pctx-enabled projects, use Serena.findSymbol for symbol lookups" |
| `warn_then_ignore` > 5x in session | `feedback` | "Large Bash output wastes context — use context-mode MCP for data-heavy commands" |
| Hook graduated from block→warn | `project` | "serena-tool-priority graduated 2026-04-01 based on LES>1.0 for 7 days" |

**Memories should have TTL (14 days)** — if the hook is still needed after expiry, memory regenerates. Prevents stale memories.

### Auto-Graduation Ladder

```
BLOCK (hook) → WARN (hook) → INSTRUCTION-ONLY (off) → GRADUATED
```

| Transition | Criteria |
|------------|----------|
| block → warn | LES > 1.0 for 7 consecutive days AND preemptive rate > 80% |
| warn → off | LES > 1.5 for 14 days AND zero violations in last 7 days |
| off → warn (regression) | Target metric regresses (e.g., Bash% rises above 30%) |

**Implementation:** `hook-graduate.sh` runs at session start, queries metrics DB, updates `hook-config.yaml` levels, logs graduation events.

**State tracking:** `hook-graduation-state.json` alongside `hook-config.yaml`:
```json
{
  "serena-tool-priority": {
    "current_level": "block",
    "les_7d": [0.3, 0.4, 0.5],
    "next_graduation": { "target": "warn", "les_min": 1.0, "preemptive_rate_min": 0.8 }
  }
}
```

---

## Verification Strategy

### Per-Phase Verification
1. **Unit:** `echo '<fixture.json>' | bash hook.sh` for all affected hooks
2. **Latency:** `time echo '<fixture.json>' | bash hook.sh` before/after each phase
3. **Behavior:** `claude -p` integration tests for end-to-end validation
4. **Metrics:** `hook-metrics.sh summary` and `hook-metrics.sh effectiveness` after live use
5. **Regression:** Monitor LES trends for 7 days after each phase deployment

### Live Session Spot-Check
After all phases, run a full Claude Code session exercising:
- Bash commands (should use Read/Grep/Glob natively)
- Edit operations (should Read first)
- Symbol lookups (should prefer Serena)
- Large output commands (should get compacted)
- Multi-step tasks (should use TodoWrite)
