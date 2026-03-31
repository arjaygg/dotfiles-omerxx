# Plan: Hook Correctness — Exit Codes, JSON Migration, Dead Code

**Date:** 2026-03-31  
**Context file:** `plans/2026-03-31-hook-validation-report.md`

---

## Context

Autoresearch session validated all 26 Claude Code hooks and found 6 bugs across the hook system. The most critical: `hook_exit_code()` in `hook-metrics.sh` maps `"block"` → exit 1, which is the **non-blocking** exit code per official Claude Code docs (tool still proceeds). This means every hook graduated to "block" today (bash-tool-gate, bash-output-guard, serena-tool-priority) is silently non-enforcing.

Additionally, all warning/blocking messages are written to stderr. Per the docs, exit 2 reads from stderr — so exit-2 hooks are channel-correct. But when the settings.json deny list fires first, it wins the race and Claude sees no actionable guidance from the hook. The industry-recommended fix is JSON structured output (exit 0 + `{"decision":"block","reason":"..."}`) which always renders cleanly regardless of deny-list interaction.

---

## Scope of Changes

| File | Changes |
|---|---|
| `.claude/hooks/hook-metrics.sh` | Fix `hook_exit_code()`: `block`→2, `warn`→0; add `hook_block()` JSON helper |
| `.claude/hooks/pre-tool-gate.sh` | All block/warn paths → JSON + exit 0 |
| `.claude/hooks/bash-output-guard.sh` | Warnings → stdout (PostToolUse); fix exit code |
| `.claude/hooks/check-agent-parallelism.sh` | stderr + exit 2 → JSON + exit 0 |
| `.claude/hooks/plan-scope-gate.sh` | stderr + exit 2 → JSON + exit 0 |
| `.claude/hooks/edit-without-read.sh` | stderr + exit 2 → JSON + exit 0 |
| `.claude/hooks/post-tool-handler.sh` | Fix dead BATCH CHECK condition; RTK hint → stdout |
| `.claude/hooks/pctx-batch-tracker.sh` | Hints → stdout |
| `.claude/hooks/post-task-fence.sh` | Warnings → stdout |
| `.claude/hooks/plans-healthcheck.sh` | Move HOOKS HEALTH check before early exit |
| `.claude/hooks/instructions-loaded.sh` | Fix server list: remove `sequential-thinking`, add `markitdown` |
| `.claude/hooks/serena-tool-priority.sh` | Fix broken regex on line 55 |
| `.claude/hooks/hook-config.yaml` | Update comments to reflect corrected exit code semantics |

---

## Step 1 — Fix hook-metrics.sh: invert exit codes + add JSON helper

**File:** `.claude/hooks/hook-metrics.sh`

**Problem:** `hook_exit_code()` maps `"block"` → 1 (non-blocking per official docs) and `"warn"` → 2 (actual block).

**Fix:** Invert the mapping. Add a `hook_block()` bash helper that hooks call instead of raw `exit`.

```bash
# hook_exit_code: NEW mapping
hook_exit_code() {
    local level
    level=$(hook_enforcement_level "$1")
    case "$level" in
        block) echo 2 ;;   # exit 2 = actual block, stderr fed to Claude
        off)   echo 0 ;;
        *)     echo 0 ;;   # warn = advisory, no block (output hint to stdout, exit 0)
    esac
}

# hook_block: emit JSON decision + exit 0 (preferred deterministic pattern)
# Usage: hook_block "hook-name" "tool-name" "Human-readable reason"
hook_block() {
    local hook_name="$1"
    local tool_name="$2"
    local reason="$3"
    hook_metric "$hook_name" "$tool_name" 2 2>/dev/null || true
    python3 -c "
import json, sys
print(json.dumps({'decision': 'block', 'reason': sys.argv[1]}))
" "$reason"
    exit 0
}
```

Update `cmd_summary` and `cmd_compliance` to count exit_code=2 as "block" (already correct in SQL — no change needed there).

Update `hook-config.yaml` header comment:
```yaml
# block → exit 2 (blocks tool; stderr shown to Claude via hook_block JSON)
# warn  → exit 0 (advisory; hint printed to stdout, tool proceeds)
# off   → exit 0 (disabled)
```

**Tradeoff:** Historical metrics.db has exit_code=1 labeled as "block". After this change, exit_code=1 entries are stale. The SQL already uses `exit_code=1` for "block" in compliance query — update to `exit_code=2`.  
**Decision:** Accept the metrics discontinuity. Old data is from burn-in phase (pre-2026-03-31) and should be ignored going forward. Add a `cmd_reset` call note in the comments.

---

## Step 2 — Migrate PreToolUse blocking hooks to JSON structured output

All PreToolUse hooks that block (exit 2 + stderr) should be migrated to the JSON pattern so the reason is always visible to Claude — even when the deny list fires simultaneously.

**Pattern to apply to each hook:**

Before:
```bash
echo "BLOCKED: <reason>" >&2
exit 2
```

After (using hook_block if hook-metrics is sourced):
```bash
hook_block "$_HOOK_NAME" "$TOOL_NAME" "BLOCKED: <reason>"
```

Or inline (for hooks not sourcing hook-metrics.sh):
```bash
python3 -c "import json,sys; print(json.dumps({'decision':'block','reason':sys.argv[1]}))" "BLOCKED: <reason>"
exit 0
```

**Files and specific changes:**

### pre-tool-gate.sh
- Lock file block (line 34): use `hook_block`
- Large file warn (line 43–44): change to stdout advisory (no block; informational)  
- .go file warn (line 51–52): change to stdout advisory (no block)
- bash-tool-gate blocks (cat/head/tail/grep/rg/find/ls/git commit): use `hook_block`
- Atomic state (blocked/overgrown/ready_to_commit): use `hook_block` for `blocked`; stdout advisory for `overgrown`/`ready_to_commit`
- Kernel file advisory (already exit 0 + stdout): no change needed

### check-agent-parallelism.sh
- Lines 25–28: replace `echo >&2; exit 2` with `hook_block` inline pattern  
- Add `source "$HOME/.dotfiles/.claude/hooks/hook-metrics.sh" 2>/dev/null || true` at top

### plan-scope-gate.sh
- Lines 27–30: replace `echo >&2; exit 2` with `hook_block` inline pattern

### edit-without-read.sh
- Line 45–47: already calls `hook_metric`; change `echo >&2` to `hook_block`

**Tradeoff — JSON string quoting:** File paths and reasons may contain single quotes, breaking naive `echo '{"reason":"$var"}'`. The `python3 -c ... sys.argv[1]` pattern passes the reason as an argument (not interpolated into the JSON), which is injection-safe. Use this pattern consistently. Performance cost is ~50ms per invocation — acceptable given hooks are already running python3 for JSON parsing.

---

## Step 3 — Fix PostToolUse hooks: warnings → stdout

PostToolUse cannot block a tool that already ran. The purpose of these hooks is to give Claude guidance for the NEXT action. For that, stdout is the correct channel (it's added to Claude's context).

### bash-output-guard.sh
- Lines 52–61: remove `>&2`, write to stdout
- Remove the `exit "$_EXIT_CODE"` pattern (PostToolUse exit code doesn't block; use exit 0 always)
- Hint text remains the same, just goes to stdout

### pctx-batch-tracker.sh
- Lines 60–62: remove `>&2`

### post-task-fence.sh
- Lines 32–43: remove `>&2`

### post-tool-handler.sh — fix dead code + RTK hint
- Lines 93–98: the `if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]]` check dead because PostToolUse matcher is `Bash|Agent`. Options:
  - **Recommended:** Remove the block entirely. The `pctx-batch-tracker.sh` hook (matcher: `mcp__pctx__.*`) already handles this.
- Line 88: RTK hint — remove `>&2`

**Tradeoff — PostToolUse exit codes:** Changing from `exit 2` to `exit 0` in PostToolUse hooks changes how hook errors are reported. With exit 0, a hook crash would be silent. Acceptable trade since these are advisory-only hooks with no hard enforcement intent.

---

## Step 4 — Fix plans-healthcheck.sh: HOOKS HEALTH unreachable

**File:** `.claude/hooks/plans-healthcheck.sh`  
**Lines:** 131–133 (early exit) vs 173–179 (HOOKS HEALTH check)

Move the HOOKS HEALTH check to run before the early-exit, or make it unconditional:

```bash
# Run HOOKS HEALTH check unconditionally (independent of plan artifact state)
if git rev-parse --show-toplevel &>/dev/null 2>&1; then
    HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || echo "")
    EXPECTED="$HOME/.dotfiles/git/hooks"
    if [[ "$HOOKS_PATH" != "$EXPECTED" ]]; then
        echo "[HOOKS HEALTH] Hyper-atomic commit hooks not installed in this repo."
        echo "  Action: Run /hyper-commit-setup to enable atomic commit enforcement."
    fi
fi

# ... existing plan artifact check ...
if [[ ${#MISSING[@]} -eq 0 ]] && [[ ${#STALE[@]} -eq 0 ]] && [[ "$HANDOFF_EXISTS" -eq 0 ]]; then
    exit 0
fi
```

**Tradeoff:** The git hooks check now runs on every prompt, not just when plans are stale. It's cheap (one `git config` call) but adds ~5ms per prompt. Acceptable.

---

## Step 5 — Fix instructions-loaded.sh: remove false-positive server warning

**File:** `.claude/hooks/instructions-loaded.sh`  
**Line 30:** `required = ['serena', 'exa', 'sequential-thinking', 'lean-ctx']`

Actual pctx.json servers: `serena`, `exa`, `lean-ctx`, `markitdown`, `qmd`, `Ref`  
`sequential-thinking` does NOT exist → fires false advisory every session.

**Fix:** Match plans-healthcheck.sh:
```python
required = ['serena', 'exa', 'markitdown', 'lean-ctx']
```

---

## Step 6 — Fix serena-tool-priority.sh: broken regex

**File:** `.claude/hooks/serena-tool-priority.sh`  
**Line 55:** `^(func|class|type|struct|interface|def|fn)\s*\\?s`

This regex never fires. Intent: match `func MyFunc`, `class Foo`, etc.

**Fix:** Use ERE-compatible pattern that bash `[[ =~ ]]` can evaluate:
```bash
if [[ "$PATTERN" =~ ^(func|class|type|struct|interface|def|fn)[[:space:]]+[A-Za-z] ]]; then
```

This matches a keyword, required whitespace, and a letter — the signature of a symbol declaration search.

---

## Step 7 — Validation session

After all code changes are committed, **open a fresh Claude Code session** in the dotfiles repo to exercise the hooks end-to-end. The new session fires every hook type organically:

- SessionStart → verifies `session-init.sh` and `instructions-loaded.sh` (no false pctx advisory)
- First Bash/Read/Edit → fires `pre-tool-gate.sh`, `serena-tool-priority.sh`, `edit-without-read.sh`
- A deliberate `cat` command → should now show JSON block reason in-context (not silent)
- UserPromptSubmit → fires `plans-healthcheck.sh` (verify HOOKS HEALTH runs unconditionally)
- Stop → fires `todo-gate.sh`, `session-end.sh`, `feedback-capture.sh`

The session is the live oracle. Hooks that previously blocked silently should now show actionable JSON reasons inline in Claude's response.

---

## Verification

After applying all steps, validate with a manual trigger sweep:

```bash
# 1. Verify hook_exit_code() returns correct values
source ~/.dotfiles/.claude/hooks/hook-metrics.sh
hook_exit_code "bash-tool-gate"   # expect: 2  (block config)
hook_exit_code "edit-without-read" # expect: 0  (warn config → advisory)
hook_exit_code "todo-gate"         # expect: 0  (warn config)

# 2. Smoke-test a blocking hook directly
echo '{"tool_name":"Bash","tool_input":{"command":"cat foo.txt"}}' \
  | bash ~/.dotfiles/.claude/hooks/pre-tool-gate.sh
# Expect: JSON {"decision":"block","reason":"..."} on stdout, exit 0

# 3. Smoke-test a non-blocking advisory hook
echo '{"tool_name":"Read","tool_input":{"file_path":"foo.go"}}' \
  | bash ~/.dotfiles/.claude/hooks/pre-tool-gate.sh
# Expect: advisory text on stdout, exit 0

# 4. Verify plans-healthcheck fires HOOKS HEALTH on healthy repo
bash ~/.dotfiles/.claude/hooks/plans-healthcheck.sh < /dev/null
# Expect: either silent or [HOOKS HEALTH] line (not "[PLANS HEALTH]" noise)

# 5. Verify instructions-loaded.sh shows no pctx advisory
bash ~/.dotfiles/.claude/hooks/instructions-loaded.sh < /dev/null 2>/dev/null | jq -r .text
# Expect: no "missing: sequential-thinking" in output

# 6. Verify serena-tool-priority.sh regex fires
echo '{"tool_name":"Grep","tool_input":{"pattern":"func HandleRequest"}}' \
  | bash ~/.dotfiles/.claude/hooks/serena-tool-priority.sh
# Expect: HINT about Serena.findSymbol
```

---

## Tradeoffs Summary

| Decision | Trade |
|---|---|
| JSON output pattern (exit 0 + JSON) over exit 2 + stderr | More deterministic, deny-list-safe. Cost: python3 per block call (~50ms). Risk: quoting bugs if not using sys.argv for reason. |
| hook_exit_code() re-mapping | Fixes enforcement. Breaks historical metrics DB (exit_code=1 was "block" → now meaningless). Run `hook-metrics.sh reset` after deploy. |
| "warn" → exit 0 (advisory, no block) | Matches user intent ("warn" should not block). Existing "warn" hooks that relied on exit 2 for blocking (e.g. edit-without-read) will no longer halt the tool — they become pure hints. This is a behavior change: edit-without-read will allow edits without reads, just advising. |
| PostToolUse exit 0 always | Cleaner. PostToolUse can't block anyway. Loses granular error signaling from hook crashes — but those were silent to Claude regardless. |
| Remove dead BATCH CHECK from post-tool-handler.sh | Cleans up dead code. The `pctx-batch-tracker.sh` hook already covers this use case with the correct matcher. |

---

## Branch

All changes go on a new branch via stack workflow:
```bash
/stack-create chore/hook-correctness-fixes main
```

Commit as one atomic unit (all hooks are logically coupled through `hook-metrics.sh`).
