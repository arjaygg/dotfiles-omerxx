# Plan: Stack Skills Overhaul — Bugs, ADO Removal & PR Stacking Improvements

**Date:** 2026-04-01

---

## Context

Full audit of all `ai/skills/stack-*.md` + `.claude/scripts/pr-stack/` scripts. Found 4 bugs, ADO hardcoding throughout merge, and several gaps in PR stacking automation. Goal: make the stack workflow seamless end-to-end on GitHub with native tmux and Claude Code integration.

---

## Task Backlog

### P0 — Bugs (block normal use)

#### T1 — Fix: `create-stack.sh` defaults to trunk, not current branch
**Files:** `.claude/scripts/pr-stack/create-stack.sh:74`, `ai/skills/stack-create/SKILL.md`

**Problem:** `BASE_BRANCH=${2:-$DEFAULT_BRANCH}` uses remote HEAD (`main`) even when you're on a stacked feature branch. Creating a new stacked branch silently forks from `main`.

**Fix in `create-stack.sh`:**
```bash
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [ -z "$CURRENT_BRANCH" ] || [ "$CURRENT_BRANCH" = "$DEFAULT_BRANCH" ]; then
    BASE_BRANCH=${2:-$DEFAULT_BRANCH}
else
    BASE_BRANCH=${2:-$CURRENT_BRANCH}
fi
```

**Fix in `stack-create/SKILL.md`:** Step 1 should say "default: current branch (stacks on top of current work); falls back to main only when already on trunk." Remove all examples that hardcode `main` as base without justification.

---

#### T2 — Fix: `stack-pr` SKILL uses broken `gt log | awk NR==2` for target
**File:** `ai/skills/stack-pr/SKILL.md:55`

**Problem:** The skill instructs Claude to construct `gh pr create` manually with:
```bash
TARGET=$(gt log --short 2>/dev/null | awk 'NR==2{print $1}' || echo "main")
```
`NR==2` is not guaranteed to be the parent — it depends on display order. The underlying `create-pr.sh` already uses `charcoal_get_parent` correctly.

**Fix:** Update skill step 4 to delegate to the script:
```bash
$HOME/.dotfiles/.claude/scripts/stack pr "$BRANCH" ["$TARGET"] ["$TITLE"] [--draft]
```
Remove the manual `gh pr create` block entirely.

---

#### T3 — Remove Azure DevOps: replace `merge-stack.sh` with GitHub-native flow
**Files:** `.claude/scripts/pr-stack/merge-stack.sh`, `ai/skills/stack-merge/SKILL.md`

**Problem:** `merge-stack.sh` hardcodes `az repos pr complete` against `https://dev.azure.com/bofaz` / `Axos-Universal-Core`. PRs are created via `gh` (GitHub). Merge always fails.

**Fix — rewrite `merge-stack.sh` to GitHub-only:**
```bash
# Accept PR number (from gh pr list) or branch name
# Merge via gh:
gh pr merge "$PR_ID" --squash --delete-branch

# After merge, update PR base branches for dependent PRs, then restack
$SCRIPT_DIR/update-stack.sh "$SOURCE_BRANCH"
```

**Fix in `stack-merge/SKILL.md`:**
- Remove all ADO language ("Azure DevOps", "complete the PR")
- Step 2: Identify PR — look up by current branch if no PR ID given: `gh pr view --json number -q .number`
- Step 3: Merge via `gh pr merge --squash --delete-branch`
- Step 4: Run `stack restack` + `stack update` to sync dependents

---

#### T4 — Fix: PR base branches not updated on GitHub after restack
**File:** `.claude/scripts/pr-stack/update-stack.sh`

**Problem:** After `gt restack` + `git push --force-with-lease`, the PR on GitHub still targets the old (possibly deleted) branch. GitHub marks the PR unmergeable.

**Fix — add after the restack loop in `update-stack.sh`:**
```bash
print_info "Updating GitHub PR base branches to match Charcoal stack..."
while IFS= read -r branch; do
    [ "$branch" = "$DEFAULT_BRANCH" ] && continue
    parent=$(charcoal_get_parent "$branch" 2>/dev/null || true)
    [ -z "$parent" ] && continue
    gh pr edit --base "$parent" --head "$branch" 2>/dev/null \
        && print_info "  PR for $branch → base updated to $parent" \
        || true
done < <(git branch --format='%(refname:short)')
```

Update `stack-update/SKILL.md`: add "PR base branches on GitHub are kept in sync with the Charcoal stack."

---

### P1 — tmux Improvements (quality of life)

#### T5 — Fix: `stack-navigate` always creates new tmux window, ignores existing
**Files:** `ai/skills/stack-navigate/SKILL.md`, `ai/skills/stack-create/SKILL.md`

**Problem:** Both skills do `tmux new-window -n $WINDOW_NAME` without checking if a window with that name already exists. Running `stack-navigate` twice opens duplicate windows.

**Fix — add window-exists check pattern to both skills:**
```bash
WINDOW_NAME="<sanitized-branch>"
TMUX_SESSION=$(tmux display-message -p '#S')
if tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' 2>/dev/null | grep -Fxq "$WINDOW_NAME"; then
    tmux select-window -t "$TMUX_SESSION:$WINDOW_NAME"
else
    tmux new-window -t "$TMUX_SESSION" -n "$WINDOW_NAME"
    sleep 0.3
    tmux send-keys -t "$TMUX_SESSION:$WINDOW_NAME" "cd $WORKTREE_PATH && claude" Enter
fi
```

---

#### T6 — New: `stack-merge` closes tmux window after merge + switches to parent
**File:** `ai/skills/stack-merge/SKILL.md`

After a PR merges, the worktree is deleted (`--delete-branch`) but the tmux window for that branch remains orphaned. 

**Fix — add to merge skill post-merge steps:**
```bash
# Close the merged branch's tmux window (if open) and switch to parent
MERGED_WINDOW=$(basename "$SOURCE_BRANCH_SANITIZED")
PARENT_WINDOW=$(basename "$(charcoal_get_parent "$SOURCE_BRANCH")" 2>/dev/null || echo "")
TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null || true)

if [ -n "$TMUX_SESSION" ]; then
    # Switch to parent window first, then kill merged window
    if [ -n "$PARENT_WINDOW" ] && tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' | grep -Fxq "$PARENT_WINDOW"; then
        tmux select-window -t "$TMUX_SESSION:$PARENT_WINDOW"
    fi
    tmux kill-window -t "$TMUX_SESSION:$MERGED_WINDOW" 2>/dev/null || true
fi
```

---

#### T7 — Fix: `stack-create` should call tmux bridge refresh after opening window
**File:** `ai/skills/stack-create/SKILL.md`

The `claude-tmux-bridge.sh` manages window names and status labels. After creating a new window via tmux, the bridge isn't notified. Window names may show wrong branch.

**Fix:** After `tmux send-keys ... claude Enter`, add:
```bash
sleep 0.5
~/.dotfiles/tmux/scripts/claude-tmux-bridge.sh session-start 2>/dev/null || true
```

---

### P2 — Claude Code Native Improvements

#### T8 — Fix: `stack-auto-pr-merge` uses Python `Task()` syntax (wrong tool format)
**File:** `ai/skills/stack-auto-pr-merge/skill.md`

**Problem:** The skill shows:
```python
Task(
    subagent_type="general-purpose",
    run_in_background=True,
    ...
)
```
Claude Code doesn't accept Python `Task()` calls. The correct tool is the `Agent` tool with `run_in_background: true`.

**Fix:** Replace the Python block with the correct Agent tool invocation pattern:
```
Use the Agent tool:
- subagent_type: "general-purpose"
- run_in_background: true
- description: "Auto-merge {branch_name} to {base_branch}"
- prompt: "..."
```

---

#### T9 — New: `stack-pr` enriches PR body with stack chain visualization
**File:** `.claude/scripts/pr-stack/create-pr.sh` + `ai/skills/stack-pr/SKILL.md`

PRs in a stack should display their dependencies in the body so reviewers understand the context.

**Fix — add to PR body template in `create-pr.sh`:**
```bash
# Build stack chain for PR description
STACK_CHAIN=""
if charcoal_initialized; then
    # Walk up the chain from trunk to current branch
    STACK_CHAIN=$(gt log --short 2>/dev/null | awk '{print "  - " $1}' || true)
fi

PR_BODY="## Summary
$COMMITS

## Stack
\`\`\`
$STACK_CHAIN
\`\`\`
> This PR is stacked on \`$TARGET_BRANCH\`. Review changes relative to that branch only.
"
```

---

#### T10 — New: `stack-clean` — one command to remove merged branch, worktree, tmux window
**Files:** New `ai/skills/stack-clean/SKILL.md`, new `.claude/scripts/pr-stack/clean-stack.sh`

**Problem:** After a branch merges, 3 manual steps are needed: `git branch -d`, `git worktree remove`, `tmux kill-window`. There's no "clean up finished work" command.

**New skill trigger:** "clean up branch", "remove merged branch", "close worktree", "done with branch"

**Script logic:**
1. Confirm branch is merged to its parent (`gh pr view --state merged`)
2. `git worktree remove .trees/<name>` (refuse if dirty)
3. `git branch -d <branch>`
4. Kill tmux window `<sanitized-name>` if it exists
5. Switch tmux to parent window

---

#### T11 — New: `stack pr-all` — create PRs for entire unpublished stack in one command
**Files:** New `.claude/scripts/pr-stack/create-pr-all.sh`, update `.claude/scripts/stack`, update `ai/skills/stack-pr/SKILL.md`

**Trigger:** "create PRs for all branches", "publish the stack", "open all PRs"

**Script logic:**
1. Get all non-trunk tracked branches bottom-up from `gt log --short`
2. For each branch: check `gh pr view --head $branch` — skip if already open
3. Call `create-pr.sh $branch $(charcoal_get_parent $branch)` sequentially (bottom-to-top order preserves dependency targeting)
4. Print table: branch → PR URL → base

**Add to `stack` entrypoint:**
```bash
pr-all)
    exec "$PR_STACK_DIR/create-pr-all.sh" "$@"
    ;;
```

---

### P2b — GitHub Account Handling (silent, parallel-safe)

#### T14 — Replace `gh auth switch` with per-command `GH_TOKEN` injection
**Files:** `.claude/scripts/pr-stack/lib/gh-account.sh` (new), `create-pr.sh`, `merge-stack.sh`, `update-stack.sh`, `create-pr-all.sh`, all `stack-pr/stack-merge/stack-auto-pr-merge` SKILL.md

**Problem with current approach (`_ensure_gh_account`):**
1. `gh auth switch --user` changes the **global** active account — a process-level side effect visible to all concurrent `gh` calls across sessions
2. Two parallel worktrees calling `stack-pr` simultaneously can clobber each other's auth state mid-PR-creation
3. `gh api user` makes a **network call** just to detect the current account on every invocation
4. The mapping is duplicated in both `create-pr.sh` AND the `stack-pr` skill (drift risk)
5. On `auth switch` failure, the script silently continues with the wrong account

**Smarter approach — `GH_TOKEN` env var per command:**

`gh` respects `GH_TOKEN` to override the active account, scoped to that process only. This is the official recommended pattern for multi-account scripts.

**New `lib/gh-account.sh`:**
```bash
#!/usr/bin/env bash
# gh-account.sh — Silent, parallel-safe GitHub account resolution

# Map remote URL → gh account login name
_gh_target_account() {
    local remote_url="${1:-$(git remote get-url origin 2>/dev/null || true)}"
    local org
    org=$(echo "$remote_url" | sed 's|.*github\.com[/:]||;s|/.*||')
    case "$org" in
        arjaygg) echo "arjaygg" ;;
        *)       echo "Arjay-Gallentes_axosEnt" ;;
    esac
}

# Get the stored token for the correct account — no network call, no global state change
# Usage: GH_TOKEN=$(gh_token_for_remote) gh pr create ...
gh_token_for_remote() {
    local account
    account="$(_gh_target_account "$@")"
    # gh auth token --user retrieves stored token without switching active account
    gh auth token --user "$account" 2>/dev/null \
        || gh auth token 2>/dev/null  # fallback: current active token
}

# Ensure credential helper is registered (one-time, silent)
gh_setup_git() {
    gh auth setup-git 2>/dev/null || true
}
```

**Usage pattern everywhere (replace `_ensure_gh_account`):**
```bash
source "$SCRIPT_DIR/lib/gh-account.sh"
gh_setup_git

# All gh commands get the right token transparently:
GH_TOKEN=$(gh_token_for_remote) gh pr create ...
GH_TOKEN=$(gh_token_for_remote) gh pr merge ...
GH_TOKEN=$(gh_token_for_remote) gh pr edit --base ...
```

**Benefits:**
- Silent: zero output, zero network call for detection
- Parallel-safe: env var is process-scoped, never touches global auth state
- Fast: `gh auth token --user` reads from local keychain (~0ms vs `gh api user` ~300ms)
- Centralised: single source of truth in `gh-account.sh`, not duplicated in skills
- Extensible: add more account mappings in `_gh_target_account` without touching callers

**Skill updates** (`stack-pr`, `stack-merge`, `stack-auto-pr-merge`): remove the `_ensure_gh_account` block from instructions; add a one-liner comment: "Account selection is handled automatically by the script based on the remote URL."

---

### P3 — Workflow Polish

#### T12 — New: `stack-create` offers draft PR immediately after branch creation
**File:** `ai/skills/stack-create/SKILL.md`

After creating worktree + tmux window, add step 7:
> "The new worktree and Claude session are ready. Would you like to also create a **draft PR** now to establish this branch in the GitHub stack? (Runs `stack pr --draft` in the new worktree)"

This is opt-in — don't auto-create without asking.

---

#### T13 — Rename `sync-base` → `stack-sync` and use `gt sync` when Charcoal available
**Files:** `ai/skills/sync-base/SKILL.md` → rename to `ai/skills/stack-sync/SKILL.md`, update `setup.sh` symlink

**Why rename:** `sync-base` is the only stack-related skill not in the `stack-*` family. All stack skills share a naming convention that makes their relationship clear in `--help` output, trigger lists, and tab completion. `stack-sync` is instantly understood as "sync the current layer of the stack with its parent."

**Distinction to preserve in the new skill header:**
> - `stack-sync` = "pull in changes from my parent into the current branch" (single-branch, daily use)
> - `stack-update` = "rebase all downstream branches after a merge" (whole-stack, post-merge)

**Charcoal integration:** Add step 1a: if `charcoal_initialized`, prefer `gt sync` (which handles fetch + rebase + force-push in one command). Fall back to the current manual steps only when Charcoal is absent.

**Trigger updates:** Add "stack sync", "sync stack layer", "sync my branch" alongside existing triggers. Keep all existing triggers for backward compat.

**`setup.sh`:** Update symlink from `sync-base` to `stack-sync` (both Claude and Gemini/Codex adapter targets).

---

## Implementation Parallelism

These tasks are fully independent:

| Group | Tasks | Can parallelize? |
|-------|-------|-----------------|
| A: Script bugs | T1, T3, T4 | 2 background agents (T1 + T3 independently) |
| B: GH account | T14 | Prerequisite for T3/T4/T11 — do first |
| C: tmux fixes | T5, T6, T7 | All skill files, parallel |
| D: Claude native | T8, T9 | Parallel |
| E: New commands | T10, T11 | T11 needs stack entrypoint; background |
| F: Polish | T2, T12, T13 | Skill-only updates, low risk |

Suggested parallel execution:
- **Wave 1 (foreground):** T14 — new `gh-account.sh` lib (unblocks T3, T4, T11)
- **Wave 2 (background×2):** T1 (create-stack default base) + T3 (merge-stack GitHub rewrite)
- **Wave 3 (background×2):** T4 (update-stack PR base sync) + T8 (auto-pr-merge Agent syntax)
- **Wave 4 (background×3):** T5+T6+T7 (all tmux skill updates — no scripts, safe)
- **Wave 5 (background×2):** T10 (stack-clean) + T11 (pr-all + stack entrypoint)
- **Wave 6:** T2, T9, T12, T13 (remaining skill polish — T13 includes rename + setup.sh symlink update)

---

## Files Modified

| File | Tasks |
|------|-------|
| `.claude/scripts/pr-stack/create-stack.sh` | T1 |
| `.claude/scripts/pr-stack/lib/gh-account.sh` | T14 (new) |
| `.claude/scripts/pr-stack/create-pr.sh` | T9, T14 |
| `.claude/scripts/pr-stack/merge-stack.sh` | T3 (full rewrite), T14 |
| `.claude/scripts/pr-stack/update-stack.sh` | T4, T14 |
| `.claude/scripts/pr-stack/create-pr-all.sh` | T11 (new) |
| `.claude/scripts/pr-stack/clean-stack.sh` | T10 (new) |
| `.claude/scripts/stack` | T11 (pr-all + clean routing) |
| `ai/skills/stack-create/SKILL.md` | T1, T5, T7, T12 |
| `ai/skills/stack-pr/SKILL.md` | T2, T9, T11 |
| `ai/skills/stack-merge/SKILL.md` | T3, T6 |
| `ai/skills/stack-update/SKILL.md` | T4 |
| `ai/skills/stack-navigate/SKILL.md` | T5 |
| `ai/skills/stack-auto-pr-merge/skill.md` | T8 |
| `ai/skills/stack-clean/SKILL.md` | T10 (new) |
| `ai/skills/sync-base/SKILL.md` → `ai/skills/stack-sync/SKILL.md` | T13 (rename + rewrite) |
| `setup.sh` | T13 (update symlink) |

---

## Verification

- `stack create feature/b` from `feature/a` → base is `feature/a` not `main`
- `stack pr` → calls script, PR targets `charcoal_get_parent` correctly
- `stack merge` → uses `gh pr merge`, closes tmux window, updates dependent PR bases
- `stack update` → `gh pr edit --base` runs for each stacked branch
- `stack pr-all` on 3-branch stack → 3 PRs created bottom-up with correct base chain
- `stack clean` on merged branch → worktree + branch + tmux window all gone
- `stack-auto-pr-merge` → uses Agent tool (not Python Task syntax)
