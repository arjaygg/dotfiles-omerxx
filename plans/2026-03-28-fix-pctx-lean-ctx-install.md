# Plan: Default Worktrees + Claude Code EnterWorktree/ExitWorktree Integration

**Date:** 2026-03-28
**Worktree:** `feature/worktree-enter-exit-integration` on `~/.dotfiles`

---

## Context

The existing stack-create workflow creates git worktrees at `.trees/<name>` but:
1. Requires an explicit `--worktree` flag (not the default)
2. After creation, Claude Code's session stays in the main repo — no automatic context switch

The goal is to:
- Make worktree creation the **default** (opt-out with `--no-worktree`)
- Wire `WorktreeCreate`/`WorktreeRemove` hooks so Claude Code's native `--worktree` CLI flag and in-session `EnterWorktree` use the stack's `.trees/` convention
- Update the `stack-create` skill to call `EnterWorktree` after branch+worktree creation so Claude Code's session automatically switches into the correct context
- Update `stack-navigate` skill to handle `EnterWorktree`/`ExitWorktree` when moving between worktrees

### Known Limitation (Bug #36205)
The in-session `EnterWorktree` tool currently **ignores** `WorktreeCreate`/`WorktreeRemove` hooks and always creates in `.claude/worktrees/`. The `claude --worktree` CLI flag **does** respect hooks correctly. The hooks are being added now for:
1. Immediate benefit with `claude --worktree` (CLI path)
2. Future compatibility when the bug is fixed (in-session EnterWorktree will then use `.trees/`)

The skill's `EnterWorktree` call is still included to shift CWD mid-session, with an inline note about the current limitation.

---

## Implementation

### 1. Default worktrees in `create-stack.sh`

**File:** `.claude/scripts/pr-stack/create-stack.sh` (line 34)

Change:
```bash
CREATE_WORKTREE=false
```
To:
```bash
CREATE_WORKTREE=true
```

Add `--no-worktree` opt-out flag in the argument parsing block (lines 37–52):
```bash
--no-worktree)
    CREATE_WORKTREE=false
    shift
    ;;
```

Update the help text in `print_usage` to reflect the new default.

---

### 2. New hook: `worktree-create.sh`

**File:** `.claude/hooks/worktree-create.sh` (new)

Receives JSON on stdin: `{"name": "<slug>", "cwd": "<project-root>", ...}`
Outputs the absolute path to the worktree on stdout (all informational output → stderr).

Logic:
1. Parse `name` and `cwd` from stdin JSON (use `python3 -c` or `jq`)
2. Sanitize `name` → `sanitized` using the same rules as `create-stack.sh` (strip type prefix, lowercase, hyphens)
3. Derive `branch_name` from the original `name` (preserve `feature/` prefix if present, else add `feature/`)
4. Set `worktree_path="$cwd/.trees/$sanitized"`
5. **If `.trees/$sanitized` already exists** (created by `stack create`): output its path and exit 0
6. **If branch already tracked in Charcoal**: create worktree only (`git worktree add "$worktree_path" "$branch_name"`)
7. **Otherwise**: create worktree + branch (`git worktree add -b "$branch_name" "$worktree_path" main`), then track with Charcoal (`gt branch track "$branch_name" --parent main`)
8. Copy configs using the same logic as `worktree-charcoal.sh::copy_worktree_configs` (source the lib and call it)
9. Output `$worktree_path` (absolute path) to stdout

---

### 3. New hook: `worktree-remove.sh`

**File:** `.claude/hooks/worktree-remove.sh` (new)

Receives JSON on stdin: `{"path": "<absolute-path>", ...}`
Delegates to the stack's existing clean-removal logic.

Logic:
1. Parse `path` from stdin JSON
2. Call `$HOME/.dotfiles/.claude/scripts/stack worktree-remove "$path"`
3. Exit with the same exit code

---

### 4. Register hooks in `settings.json`

**File:** `.claude/settings.json`

Add after the `"Stop"` hook block (before the closing `}` of `"hooks"`):

```json
"WorktreeCreate": [
  {
    "matcher": ".*",
    "hooks": [
      {
        "type": "command",
        "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/worktree-create.sh\"'"
      }
    ]
  }
],
"WorktreeRemove": [
  {
    "matcher": ".*",
    "hooks": [
      {
        "type": "command",
        "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/worktree-remove.sh\"'"
      }
    ]
  }
]
```

---

### 5. Update `stack-create` SKILL.md

**File:** `.claude/skills/stack-create/SKILL.md`

Key changes:
- Remove `--worktree` from the command (it's now the default); mention `--no-worktree` to skip
- After confirming the worktree was created successfully, the skill instructs Claude to call:
  ```
  EnterWorktree({name: "<sanitized-branch-name>"})
  ```
  where `<sanitized-branch-name>` is the description part (e.g., for `feature/user-auth` → `"user-auth"`)
- Add a note to the skill: the WorktreeCreate hook will redirect EnterWorktree to `.trees/<name>` once bug #36205 is resolved; until then the session CWD moves to `.claude/worktrees/` (limited isolation)
- Add `ExitWorktree({action: "keep"})` as the cleanup instruction at the end of the session

---

### 6. Update `stack-navigate` SKILL.md

**File:** `.claude/skills/stack-navigate/SKILL.md`

Add a section: **Worktree Session Handoff**
When navigating between stack branches that have worktrees:
1. If the current Claude Code session is in a worktree (entered via EnterWorktree), call `ExitWorktree({action: "keep"})` before navigating
2. After navigating to the target branch, call `EnterWorktree({name: "<target-sanitized>"})` to switch context into the target worktree
3. If unsure whether we're in an EnterWorktree session, note: "If you entered this session via EnterWorktree, call ExitWorktree first before navigating."

---

## Critical Files

| File | Action |
|---|---|
| `.claude/scripts/pr-stack/create-stack.sh` | Flip default, add `--no-worktree` |
| `.claude/hooks/worktree-create.sh` | Create new hook |
| `.claude/hooks/worktree-remove.sh` | Create new hook |
| `.claude/settings.json` | Add WorktreeCreate/WorktreeRemove hook registrations |
| `.claude/skills/stack-create/SKILL.md` | Remove `--worktree` flag, add EnterWorktree call |
| `.claude/skills/stack-navigate/SKILL.md` | Add ExitWorktree/EnterWorktree session handoff section |

All source files are in `~/.dotfiles`. The `.claude/` directory in `~/.dotfiles` is symlinked to `~/.claude/`.

---

## Verification

1. **Default worktree creation:**
   ```bash
   cd ~/.dotfiles && .claude/scripts/stack create feature/test-default main
   # Expected: worktree created at .trees/test-default WITHOUT --worktree flag
   ls .trees/test-default
   ```

2. **Opt-out works:**
   ```bash
   .claude/scripts/stack create feature/no-tree main --no-worktree
   # Expected: branch created, no worktree
   git worktree list | grep no-tree  # should show nothing
   ```

3. **WorktreeCreate hook (CLI path):**
   ```bash
   # From ~/.dotfiles main repo
   claude --worktree my-feature
   # Expected: worktree at .trees/my-feature (from hook), Claude starts in that context
   # (not .claude/worktrees/my-feature)
   ```

4. **In-session EnterWorktree (with hook, after bug fix):**
   ```bash
   # In active Claude Code session, after stack create feature/test-hook
   EnterWorktree({name: "test-hook"})
   # Expected: session CWD = .trees/test-hook (not .claude/worktrees/)
   ```

5. **Skill end-to-end:**
   - Ask Claude: "Create a stack branch feature/ci-improvements"
   - Expected: `create-stack.sh` runs with default worktree, `EnterWorktree` called, session CWD switches

---

## Notes

- The `.claude/` symlink convention means hook scripts live at `~/.dotfiles/.claude/hooks/` and are automatically available via `~/.claude/hooks/`
- The `worktree-create.sh` hook should source `.claude/scripts/pr-stack/lib/worktree-charcoal.sh` for config copying — avoids code duplication
- JSON parsing in hooks: prefer `python3 -c` over `jq` for portability (jq may not be installed), or check for jq and fall back to python3
- Don't update `session-init.sh` or `plans-healthcheck.sh` — those are covered by the existing hook infrastructure

---

## Expected Behavior (Post-Implementation)

### Happy path: creating a new stack branch

```
User: "Create stack branch feature/auth-improvements"

1. Skill runs:
   $HOME/.dotfiles/.claude/scripts/stack create feature/auth-improvements main
   → Worktree created at .trees/auth-improvements on branch feature/auth-improvements
   → Charcoal tracks the branch
   → Configs copied (.mcp.json paths updated, .vscode, .serena copied)

2. Skill calls:
   EnterWorktree({name: "auth-improvements"})
   → [With hook, after bug fix] Claude CWD = .trees/auth-improvements (correct branch)
   → [Current, bug #36205]      Claude CWD = .claude/worktrees/auth-improvements (new branch, different from stack branch)

3. Subsequent Claude Code tool calls (Read, Edit, Grep, Write) operate in that CWD context

4. User completes work, calls stack-pr to create PR

5. ExitWorktree({action: "keep"}) → Claude CWD returns to ~/.dotfiles main repo
```

### Happy path: `claude --worktree` CLI flag (works NOW with hooks)

```
User (terminal): claude --worktree auth-improvements
→ WorktreeCreate hook fires
→ Hook sanitizes "auth-improvements" → .trees/auth-improvements
→ Hook sees .trees/auth-improvements exists → outputs its path
→ Claude starts with CWD = .trees/auth-improvements on branch feature/auth-improvements ✅
```

### Happy path: opt-out of worktree

```
User: "Create stack branch feature/quick-fix --no-worktree"
→ Skill passes --no-worktree flag
→ Branch created, no worktree, no EnterWorktree call
→ Standard workflow continues
```

---

## Risks and Potential Problems

### Risk 1: EnterWorktree bug creates wrong branch (HIGH impact, currently present)
**Problem:** In-session `EnterWorktree` ignores `WorktreeCreate` hooks (bug #36205) and creates `.claude/worktrees/<name>` with a NEW auto-generated branch from HEAD, not the stack branch. Claude Code edits in that session go to the WRONG branch.

**Mitigation:**
- The `stack-create` SKILL.md will clearly document this limitation
- The skill will print a warning when calling EnterWorktree, noting that `.trees/<name>` is the authoritative worktree
- For now, the EnterWorktree call shifts CWD context but the user must verify edits land in `.trees/<name>`
- When bug is fixed, behavior becomes correct automatically

### Risk 2: `WorktreeCreate` hook JSON parsing failure (MEDIUM impact)
**Problem:** If `python3` is not available, or the JSON format from Claude Code changes, the hook will crash and break `claude --worktree`.

**Mitigation:**
- Use `jq` first, fall back to `python3`, fall back to `grep`/`sed` for basic name extraction
- Add `set -e` and a clear error message if parsing fails
- Test hook independently before using

### Risk 3: Double-worktree creation (MEDIUM impact)
**Problem:** If `stack create` creates `.trees/auth` and the user also calls `claude --worktree auth` later, the hook must recognize the existing worktree and not create a duplicate. Git will refuse to add a worktree for a branch already checked out elsewhere.

**Mitigation:**
- Hook explicitly checks `if [ -d "$worktree_path" ]` → reuse existing, no duplicate creation
- Also check if the branch is already checked out in any worktree before creating

### Risk 4: Naming mismatch between `EnterWorktree(name)` and `.trees/` directory (LOW impact)
**Problem:** `stack create feature/user-auth` sanitizes to `.trees/user-auth`. But if the user calls `EnterWorktree({name: "feature/user-auth"})` or `EnterWorktree({name: "user-auth"})`, the hook must map both to the same `.trees/user-auth`.

**Mitigation:**
- Hook applies the same sanitization as `create-stack.sh` (strip type prefix, lowercase, hyphens) before deriving the path
- This means `feature/user-auth`, `user-auth`, and `feat/user-auth` all resolve to `.trees/user-auth`

### Risk 5: Settings.json is a kernel file (LOW impact, known constraint)
**Problem:** CLAUDE.md warns "Do not edit `CLAUDE.md` or `RTK.md` mid-session — editing these files invalidates the LLM prompt cache." `settings.json` is similarly cached.

**Mitigation:**
- Edit `settings.json` only as part of the stack branch commit, not interactively mid-session
- Already the plan — changes committed on the feature branch, applied after merge

### Risk 6: Charcoal not available (LOW impact)
**Problem:** The hook calls `gt branch track` to register with Charcoal. If Charcoal isn't installed, the hook fails.

**Mitigation:**
- Wrap Charcoal calls in `if command -v gt >/dev/null 2>&1; then` guards (same pattern as existing `worktree-charcoal.sh`)

---

## Implementation Workflow (Stack Branch + PR)

Per the AGENTS.md branch workflow rule, this implementation runs in a **stack branch with worktree**:

```bash
# Step 1: Create implementation branch (from ~/.dotfiles)
.claude/scripts/stack create feature/worktree-enter-exit-integration main --worktree
# → Creates .trees/worktree-enter-exit-integration

# Step 2: Work in the worktree
# (All file edits happen in .trees/worktree-enter-exit-integration/)

# Step 3: Commit changes on the feature branch
git add <files>
git commit -m "feat(stack): default worktrees + WorktreeCreate/Remove hook integration"

# Step 4: Push and create PR
.claude/scripts/stack pr feature/worktree-enter-exit-integration main \
  "feat(stack): default worktrees + EnterWorktree/ExitWorktree integration"

# Step 5: User reviews and approves PR before merge
```

Note: Since the change itself modifies `stack create` to default to worktrees, we use the **current** behavior (`--worktree` flag explicit) to create this implementation branch.
