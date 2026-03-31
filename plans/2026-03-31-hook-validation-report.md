# Hook Validation Report — 2026-03-31

**Goal:** Validate all Claude Code hooks function as expected  
**Scope:** 26 registered hooks across 8 event types  
**Metric:** Functional and actionable errors that help Claude/LLM be more effective

---

## Summary

| Severity | Count | Description |
|---|---|---|
| HIGH | 2 | Blocks fire but Claude never sees why |
| MEDIUM | 3 | Dead code, inconsistent config, gate logic bypass |
| LOW | 1 | Broken regex — condition never fires |

---

## BUG 1 — HIGH: Blocking hooks write reason to stderr; Claude never sees it

**Hooks affected:**

| Hook | Event | Config level | Exit | Messages on |
|---|---|---|---|---|
| `pre-tool-gate.sh` | PreToolUse | bash-tool-gate: **block** → 1 | 1 | **stderr** ← bug |
| `bash-output-guard.sh` | PostToolUse | bash-output-guard: **block** → 1 | 1 | **stderr** ← bug |
| `edit-without-read.sh` | PreToolUse | edit-without-read: warn → 2 | 2 | **stderr** ← bug |
| `check-agent-parallelism.sh` | PreToolUse | no config → 2 | 2 | **stderr** ← bug |
| `plan-scope-gate.sh` | PreToolUse | no config → 2 | 2 | **stderr** ← bug |
| `pctx-batch-tracker.sh` | PostToolUse | pctx-batch-tracker: warn → 2 | 2 | **stderr** ← bug |
| `post-task-fence.sh` | PostToolUse | no config → 2 | 2 | **stderr** ← bug |

**Root cause:** Claude Code injects the hook's **stdout** into the conversation as the
block reason. Anything on stderr reaches the terminal only — Claude never sees it.

**Impact (bash-tool-gate: block):** When Claude runs `cat`, `head`, `tail`, `grep`, `rg`,
`find`, or `ls` via Bash, the tool is blocked but no reason appears in context. Claude
retries the same (blocked) command or calls the wrong fallback.

**Impact (bash-output-guard: block):** When Bash produces >200 lines, the command is
blocked with zero context. Claude has no signal to use context-mode MCP tools instead.

**Fix pattern:** Remove `>&2` from all message echoes in blocking/warning hooks.
The guard pattern is correct (exit code, logic). Only the output channel is wrong.

**Specific lines:**
- `pre-tool-gate.sh`: lines 34, 43, 51, 70, 76, 83, 89, 95, 104, 114, 169, 172, 174, 176, 180, 182, 184
- `bash-output-guard.sh`: lines 52, 53, 54, 59
- `edit-without-read.sh`: line 45
- `check-agent-parallelism.sh`: lines 25, 26, 27
- `plan-scope-gate.sh`: lines 27, 28, 29
- `pctx-batch-tracker.sh`: lines 60, 61, 62
- `post-task-fence.sh`: lines 32–42

**Correctly implemented (stdout):** `serena-tool-priority.sh`, `plans-healthcheck.sh`,
`prompt-parallelism-hint.sh`, `plan-todowrite-reminder.sh`, `pre-compact.sh`, `todo-gate.sh` (block path).

---

## BUG 2 — HIGH: Dead code in post-tool-handler.sh — BATCH CHECK never fires

**File:** `.claude/hooks/post-tool-handler.sh` — lines 93–98  
**settings.json matcher:** `"Bash|Agent"`

```bash
# This condition is NEVER true — hook only fires for Bash and Agent
if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]] && [[ ! -f "$REMINDER_FLAG" ]]; then
    touch "$REMINDER_FLAG"
    echo "BATCH CHECK: Was this the only Serena/MCP operation needed this turn? ..." >&2
fi
```

The hook is registered for `Bash|Agent` but the check is gated on `mcp__pctx__execute_typescript`.
These are mutually exclusive — `TOOL_NAME` will never equal an MCP tool name in this hook.

**Fix:** Either change the matcher to include `mcp__pctx__.*`, OR move the BATCH CHECK logic
into the `pctx-batch-tracker.sh` hook which already has the correct matcher. 
Also: message is on stderr (see BUG 1).

---

## BUG 3 — MEDIUM: Inconsistent pctx server requirements between two hooks

**instructions-loaded.sh** line 31:
```python
required = ['serena', 'exa', 'sequential-thinking', 'lean-ctx']
```

**plans-healthcheck.sh** line 84:
```python
required = ['serena', 'exa', 'markitdown', 'lean-ctx']
```

`sequential-thinking` vs `markitdown` — one will fire a false-positive "missing server"
warning if the other's server is not in `pctx.json`. Actual pctx.json must be checked to
determine which is correct; then both hooks should use the same list.

---

## BUG 4 — MEDIUM: HOOKS HEALTH check in plans-healthcheck.sh unreachable when plans are healthy

**File:** `.claude/hooks/plans-healthcheck.sh`

```bash
# Line 131 — early exit when all plans are healthy
if [[ ${#MISSING[@]} -eq 0 ]] && [[ ${#STALE[@]} -eq 0 ]] && [[ "$HANDOFF_EXISTS" -eq 0 ]]; then
    exit 0  # ← exits here
fi

# ... python3 PYEOF block ...

# Lines 173–179 — this block NEVER runs on healthy sessions
if git rev-parse --show-toplevel &>/dev/null 2>&1; then
    HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || echo "")
    if [[ "$HOOKS_PATH" != "$EXPECTED" ]]; then
        echo "[HOOKS HEALTH] Hyper-atomic commit hooks not installed in this repo."
```

The hyper-atomic hooks setup reminder is gated behind plan staleness. Any repo with
up-to-date plans but missing atomic hooks never gets the setup prompt.

**Fix:** Move the HOOKS HEALTH check before the early-exit, or make it independent.

---

## BUG 5 — LOW: serena-tool-priority.sh regex broken — symbol keyword check never fires

**File:** `.claude/hooks/serena-tool-priority.sh` — line 55

```bash
if [[ "$PATTERN" =~ ^(func|class|type|struct|interface|def|fn)\s*\\?s ]]; then
```

`\\?s` in a bash `[[ =~ ]]` ERE pattern means: optional literal backslash `\`, then `s`.
This would only match patterns like `func\s` or `funcs` — not the intended "keyword followed
by whitespace and a name". The condition likely never fires.

**Likely intent:** `^(func|class|type|struct|interface|def|fn)[[:space:]]`  
(Or in ERE: `^(func|class|...) `)

---

## Hooks verified as correct

| Hook | Event | Status |
|---|---|---|
| `session-init.sh` | SessionStart | ✓ — stdout, exit 0 |
| `instructions-loaded.sh` | InstructionsLoaded | ✓ — stdout json |
| `serena-tool-priority.sh` | PreToolUse | ✓ — stdout, correct exit codes |
| `plans-healthcheck.sh` | UserPromptSubmit | ✓ — stdout (BUG 4 noted) |
| `prompt-parallelism-hint.sh` | UserPromptSubmit | ✓ |
| `plan-todowrite-reminder.sh` | UserPromptSubmit | ✓ |
| `qmd-sync.sh` | UserPromptSubmit | ✓ — background, non-blocking |
| `pre-compact.sh` | PreCompact | ✓ — stdout json, comprehensive |
| `todo-gate.sh` | Stop | ✓ — block path correct (stdout json) |
| `session-end.sh` | Stop | ✓ — writes handoff correctly |
| `feedback-capture.sh` | Stop | ✓ — transcript parse correct |
| `context-monitor.sh` | Notification | ✓ — osascript desktop alerts |
| `read-tracker.sh` | PostToolUse | ✓ — pure tracking, no enforcement |
| `worktree-create.sh` | WorktreeCreate | ✓ — stdout path, stderr info |
| `hook-metrics.sh` | (library) | ✓ — SQLite logging, correct API |

---

## Prioritized fix order

1. **BUG 1** (all stderr→stdout migrations) — highest impact, affects every blocked tool call
2. **BUG 2** (post-tool-handler dead code + matcher fix) — BATCH CHECK is invisible today
3. **BUG 4** (plans-healthcheck early exit) — repos with healthy plans never get atomic hooks reminder
4. **BUG 3** (server list sync) — verify actual pctx.json, unify both hooks
5. **BUG 5** (regex fix) — low urgency, feature was never working
