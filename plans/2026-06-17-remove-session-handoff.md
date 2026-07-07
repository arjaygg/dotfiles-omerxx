# Plan: Remove Session-Handoff Mechanism

**Date:** 2026-06-17  
**Scope:** Remove `plans/session-handoff.md`-based session tracking and the entire session-hub tmux picker. Modern memory stack (auto-memory + Serena + active-context.md) handles context continuity; explicit status tracking is no longer needed.

---

## Context

`plans/session-handoff.md` was written at session end and read at session start to carry task context across worktrees. It served three functions:

1. **Context carry** — propagate task focus from prior session to new worktree
2. **Status tracking** — lifecycle flags (pending / deferred / complete / abandoned) for the session-hub picker
3. **fzf preview** — display per-session state in the tmux picker

With the modern memory stack now in place, each function is replaced:

| Function | Old mechanism | New mechanism |
|---|---|---|
| Context carry | `plans/session-handoff.md` (file) | **Supermemory** (auto-capture) + `active-context.md` (structured) |
| Status tracking | session-hub picker + handoff flags | **Dropped** (user decision) |
| fzf preview | session-hub fzf picker | **Dropped** (moot with picker removal) |

**Supermemory** (`supermemory@supermemory-plugins`) is installed and runs a local server at `$SUPERMEMORY_BASE_URL` (default: `http://localhost:6767`). The plugin:
- Auto-captures conversation context during each session
- Injects a `<supermemory-context>` block at session start with relevant prior-session memories
- Exposes a REST API (`POST /v1/memories`, `GET /v1/search`) for explicit saves

This means semantic context carry is fully automatic — no file writing needed. The Stop hook writer was already removed in a prior wave. Status tracking → **drop the session picker entirely** (user decision).

---

## Files To Delete

### tmux session-hub scripts (5 files)
- `tmux/scripts/session-hub.sh` — main picker (Ctrl+A G target)
- `tmux/scripts/_session-hub-handoff.sh` — creates worktree + writes handoff
- `tmux/scripts/_session-hub-done.sh` — marks sessions complete
- `tmux/scripts/_session-hub-lib.sh` — shared lib: get_task_list_id, claude_launch_cmd
- `tmux/scripts/_session-hub-new.sh` — creates new worktree from hub

### Claude session-* commands (10 files: source + symlink for each)
Source in `ai/commands/`:
- `session-defer.md`, `session-undefer.md`, `session-done.md`, `session-picker.md`, `session-next.md`

Symlinks in `.claude/commands/` (same 5 names) — delete alongside sources.

### Retired hook
- `.claude/hooks/post-read-auto-delete.sh` — already marked "retired"

---

## Files To Modify

### `tmux/tmux.conf` — lines 90–92
Remove the `Ctrl+A G` keybinding and its comment block:
```
# repo-launcher.sh shelved — replaced by session-hub
# bind-key G display-popup ...
bind-key G display-popup -E -w 85% -h 80% -d "#{pane_current_path}" "~/.dotfiles/tmux/scripts/session-hub.sh"
```

### `ai/skills/stack-create/SKILL.md` — Step 6
Replace the step that writes `plans/session-handoff.md` with two actions:

**Structured carry** — copy `active-context.md` from parent to new worktree:
```bash
if [ -f "plans/active-context.md" ]; then
  mkdir -p "$WORKTREE_PATH/plans"
  cp plans/active-context.md "$WORKTREE_PATH/plans/active-context.md"
fi
```

**Semantic carry** — write a Supermemory entry so the new session has searchable context (Supermemory auto-captures during conversation, but an explicit write on worktree create ensures branch + task intent is immediately retrievable):
```bash
if [ -n "${SUPERMEMORY_API_KEY:-}" ] && [ -n "${SUPERMEMORY_BASE_URL:-}" ]; then
  BRANCH="$1"
  TASK_SUMMARY=$(grep -m1 "^focus:" plans/active-context.md 2>/dev/null | sed 's/^focus: //' || echo "New worktree for $BRANCH")
  curl -s -X POST "$SUPERMEMORY_BASE_URL/v1/memories" \
    -H "Authorization: Bearer $SUPERMEMORY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"Worktree created: $BRANCH. Task: $TASK_SUMMARY\", \"metadata\": {\"branch\": \"$BRANCH\", \"type\": \"worktree-create\"}}" > /dev/null || true
fi
```
The `|| true` ensures a Supermemory outage never blocks worktree creation.

### `.gitignore`
Remove: `plans/session-handoff.md`  
Remove: `plans/.task-list-id` (written by `_session-hub-lib.sh`, no longer needed)

---

## New File To Create

### `decisions/0009-remove-session-picker.md`
ADL entry documenting: removal rationale, Supermemory as semantic-carry replacement, `active-context.md` as structured-carry replacement, alternatives rejected (status-only file, dotfile outside plans/), and assumptions (Supermemory server running; user maintains active-context.md discipline).

---

## Execution Order

1. Create branch + worktree: `stack create chore/remove-session-handoff main`
2. Delete 5 tmux scripts
3. Delete 5 source commands in `ai/commands/` + 5 `.claude/commands/` symlinks
4. Delete `.claude/hooks/post-read-auto-delete.sh`
5. Edit `tmux/tmux.conf` — remove lines 90–92
6. Edit `ai/skills/stack-create/SKILL.md` — replace Step 6
7. Edit `.gitignore` — remove `plans/session-handoff.md` and `plans/.task-list-id`
8. Write `decisions/0009-remove-session-picker.md`
9. Verify: `grep -r "session-handoff" .` → zero matches

---

## Verification
```bash
grep -r "session-handoff" . --include="*.md" --include="*.sh" --include="*.nu"  # → 0 results
grep "session-hub" tmux/tmux.conf                                                # → 0 results
ls .claude/commands/session-*.md 2>/dev/null                                     # → no files
ls tmux/scripts/_session-hub*.sh 2>/dev/null                                     # → no files
# Confirm Supermemory server is reachable
curl -s "$SUPERMEMORY_BASE_URL/health" | head -1                                 # → 200 or {"status":"ok"}
```
