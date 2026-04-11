# Plan: Enforce PR Stacking Early and Intelligently
**Date:** 2026-04-11  
**Branch:** `feature/enforce-pr-stacking`

---

## Context

Currently, PR stacking is only enforced at the last possible moment: when `git commit` is attempted on `main` (via `pre-tool-gate-v2.sh` Section 2d). This means a session can burn many turns doing reads, plans, and edits before the wall hits. The user wants:

1. **Earlier detection** — catch "I'm on main" before any editing happens
2. **Intelligent guidance** — don't just block; derive a suggested branch name from the task, show the exact command

---

## Existing Gaps

| Layer | Problem |
|---|---|
| `instructions-loaded.sh` | Detects branch + emits SESSION START, but no main-branch warning |
| `plans-healthcheck.sh` | Checks hooks/pctx health but no stack health |
| `pre-tool-gate-v2.sh` | Only catches `git commit` on main — doesn't catch Edit/Write |
| git `protect-main.sh` | Blocks commit at git layer but message doesn't guide to stacking |
| No session-start stack check | Charcoal init status never verified; user may not know stacking is broken |

---

## Three-Layer Enforcement Model

```
Session Start               First Prompt             Every Edit/Write on main
      │                          │                              │
InstructionsLoaded          UserPromptSubmit              PreToolUse
(once per session)          (first prompt only)           (hard block)
      │                          │                              │
[L1] Advisory               [L2] Intelligent hint        [L3] Hard block
Branch: main → warn         Derive name from prompt      Block + show command
Show stack create cmd       Show suggested branch        Show suggested branch
Check Charcoal init         Cache flag (once/session)    Gate: .trees/ exempt
```

---

## Layer 1 — `instructions-loaded.sh` (Early Advisory)

**Event:** `InstructionsLoaded` (fires before first user turn)  
**File:** `.claude/hooks/instructions-loaded.sh`

Add after existing branch/pctx checks:

```bash
# --- Stack enforcement advisory ---
STACK_WARNING=""
if [[ "$GIT_BRANCH" == "main" || "$GIT_BRANCH" == "master" ]]; then
    GT_INIT=0
    [[ -f ".git/.graphite_repo_config" ]] && GT_INIT=1
    if [[ "$GT_INIT" -eq 1 ]]; then
        STACK_WARNING="[STACK ENFORCER] You are on '$GIT_BRANCH'. Create a stacked branch before editing:\n  stack create feature/<name> $GIT_BRANCH\nEdit/Write on main will be blocked."
    else
        STACK_WARNING="[STACK ENFORCER] You are on '$GIT_BRANCH' and Charcoal is not initialized.\n  Run: gt repo init\n  Then: stack create feature/<name> $GIT_BRANCH"
    fi
fi
```

Pass `$STACK_WARNING` into the Python block and emit it as a line in the SESSION START banner.

---

## Layer 2 — New `stack-enforce-prompt.sh` (Intelligent Per-Prompt Advisory)

**Event:** `UserPromptSubmit` (first prompt only per session, then silent)  
**File:** `.claude/hooks/stack-enforce-prompt.sh` (NEW)

Logic:
1. Parse prompt + session_id from stdin JSON (via `jq`)
2. Check `git branch --show-current` == `main` / `master`
3. If on main AND no flag file `/tmp/.claude-stack-advised-$(id -u)-$SESSION_ID`:
   - Extract 3–5 key content words from the prompt (strip stop words, slugify)
   - Emit `[STACK ENFORCER]` banner with derived branch suggestion
   - Create flag file (suppresses on all subsequent prompts this session)
4. Otherwise: silent exit

**Branch name derivation** (pure bash, no LLM):
```bash
derive_branch_name() {
    echo "$1" \
        | tr '[:upper:]' '[:lower:]' \
        | sed 's/[^a-z0-9 ]/ /g' \
        | tr -s ' ' \
        | awk '{for(i=1;i<=NF && i<=10;i++) printf $i" "}' \
        | sed 's/\b\(a\|an\|the\|is\|are\|was\|i\|me\|my\|we\|to\|for\|in\|on\|at\|with\|by\|of\|that\|this\|can\|you\|please\|would\|like\)\b//g' \
        | tr -s ' ' | sed 's/^ //; s/ $//' \
        | tr ' ' '-' | sed 's/-\+/-/g; s/-$//' \
        | cut -c1-40
}
```

**Output format:**
```
[STACK ENFORCER] You are on 'main'. Stack a branch before editing.
  Suggested: stack create feature/enforce-pr-stacking main
  Then edit in the worktree at .trees/enforce-pr-stacking/
  (This message fires once per session.)
```

---

## Layer 3 — `pre-tool-gate-v2.sh` Section 3 Enhancement (Hard Block)

**File:** `.claude/hooks/pre-tool-gate-v2.sh`  
**Insert:** After existing Section 3a (edit-without-read check), add Section 3b:

```bash
# 3b. Edit/Write on main — block unless in a worktree or plans/
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]]; then
    _EDIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    if [[ "$_EDIT_BRANCH" == "main" || "$_EDIT_BRANCH" == "master" ]]; then
        # Allow plans/ files (they're always managed on current branch)
        # Allow .trees/ paths (already in a worktree)
        if [[ ! "$FILE_PATH" =~ (^|/)(plans|\.trees)/ ]]; then
            _SUGGESTED_BRANCH=""
            _HINT_FILE="/tmp/.claude-stack-hint-$(id -u)-${CLAUDE_SESSION_ID:-}"
            [[ -f "$_HINT_FILE" ]] && _SUGGESTED_BRANCH=$(cat "$_HINT_FILE")
            echo "BLOCKED: Editing '$FILE_PATH' on '$_EDIT_BRANCH'. Create a stacked branch first:" >&2
            if [[ -n "$_SUGGESTED_BRANCH" ]]; then
                echo "  stack create feature/$_SUGGESTED_BRANCH $_EDIT_BRANCH" >&2
            else
                echo "  stack create feature/<name> $_EDIT_BRANCH" >&2
            fi
            echo "  This creates a worktree at .trees/<name>/ — work there instead." >&2
            exit 1
        fi
    fi
fi
```

> The `_HINT_FILE` contains the derived branch name written by `stack-enforce-prompt.sh`, so both layers share the suggestion.

---

## Layer 4 — `plans-healthcheck.sh` Stack Health Check

**File:** `.claude/hooks/plans-healthcheck.sh`  
**Insert:** After the existing `[HOOKS HEALTH]` check (line 108–114), add `[STACK HEALTH]`:

```bash
# --- [STACK HEALTH] Charcoal / stacking readiness ---
if git rev-parse --show-toplevel &>/dev/null 2>&1; then
    STACK_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    GT_INIT=0
    [[ -f ".git/.graphite_repo_config" ]] && GT_INIT=1
    if [[ "$STACK_BRANCH" == "main" || "$STACK_BRANCH" == "master" ]]; then
        echo "[STACK HEALTH] On '$STACK_BRANCH' — use stack-create skill before editing."
    fi
    if [[ "$GT_INIT" -eq 0 ]] && command -v gt &>/dev/null; then
        echo "[STACK HEALTH] Charcoal installed but 'gt repo init' not run in this repo."
        echo "  Action: Run 'gt repo init' to enable stacking, then use stack-create skill."
    elif ! command -v gt &>/dev/null; then
        echo "[STACK HEALTH] Charcoal (gt) not found. Install: npm install -g @withgraphite/graphite-cli"
        echo "  Then: gt repo init && stack create feature/<name> main"
    fi
fi
```

---

## Layer 5 — Register New Hook in `settings.json`

**File:** `.claude/settings.json`

Add `stack-enforce-prompt.sh` under `UserPromptSubmit` hooks alongside existing entries:

```json
{
  "type": "command",
  "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/stack-enforce-prompt.sh\"'"
}
```

> Note: Order matters. Add BEFORE `plans-healthcheck.sh` so the enforcement message appears above the plans-health warnings.

---

## Files to Modify

| File | Change |
|---|---|
| `.claude/hooks/instructions-loaded.sh` | Add `STACK_WARNING` variable + include it in SESSION START banner |
| `.claude/hooks/pre-tool-gate-v2.sh` | Add Section 3b: Edit/Write block on main (after 3a) |
| `.claude/hooks/plans-healthcheck.sh` | Add `[STACK HEALTH]` check after `[HOOKS HEALTH]` |
| `.claude/settings.json` | Register `stack-enforce-prompt.sh` under `UserPromptSubmit` |

## Files to Create

| File | Purpose |
|---|---|
| `.claude/hooks/stack-enforce-prompt.sh` | New UserPromptSubmit hook: intelligent per-prompt advisory |

---

## Verification

After implementation:

1. **Session start test**: Start a fresh Claude Code session while on `main` branch.  
   Expect: SESSION START banner includes `[STACK ENFORCER]` with `stack create` command and Charcoal status.

2. **First-prompt test**: Send any prompt while on `main`.  
   Expect: `[STACK ENFORCER]` banner with derived branch name from prompt content.

3. **Second-prompt test**: Send another prompt while still on `main`.  
   Expect: No repeat `[STACK ENFORCER]` message (flag file suppresses it).

4. **Edit block test**: While on `main`, attempt `Edit` on any non-plans file.  
   Expect: `BLOCKED: Editing ... on 'main'. Create a stacked branch first:`

5. **Worktree exemption test**: From inside `.trees/feature-x/`, attempt an `Edit`.  
   Expect: Not blocked (worktree path is exempt).

6. **Plans exemption test**: Write to `plans/active-context.md` while on `main`.  
   Expect: Not blocked (plans/ is always allowed).

7. **Stack health test**: Run session in a repo without `gt repo init`.  
   Expect: `[STACK HEALTH]` advisory in `plans-healthcheck.sh` output.

---

## Key Design Decisions

**D1: plans/ and .trees/ are exempt from Layer 3 block**  
Plans files are bookkeeping, not feature work. `.trees/` files are already in a proper worktree.

**D2: Branch name suggestion is derived client-side (no LLM)**  
Simple stop-word removal + slugify. Fast, zero tokens, no API calls. Good enough for suggestion quality.

**D3: L2 fires once per session via flag file**  
Repeat nagging degrades UX. One clear message per session is enough; L3 hard-block handles subsequent attempts.

**D4: L3 blocks Edit AND Write (not just Bash commit)**  
The existing gate only catches `git commit`. Claude can Edit files for many turns before ever committing. Block at the first modification attempt.

**D5: Charcoal init check in L1 and L4**  
Without `gt repo init`, `stack create` silently degrades. Surface this early so users know the dependency.
