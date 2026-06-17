# 0009 — Remove Session-Picker and session-handoff.md

**Date:** 2026-06-17  
**Status:** Accepted

## Decision

Remove the session-hub tmux picker system (`tmux/scripts/session-hub.sh` + 4 helper scripts), the five `session-{defer,undefer,done,picker,next}` Claude commands, and the `plans/session-handoff.md` file mechanism entirely.

## Why

`plans/session-handoff.md` was a per-worktree file written at session end and read at session start to carry task context and lifecycle status across sessions. It served three functions:

1. **Context carry** — propagate task focus to a new worktree
2. **Status tracking** — lifecycle flags (pending / deferred / complete / abandoned) for the picker
3. **fzf preview** — per-session state display in the tmux session-hub picker

By 2026-06-17, the modern memory stack fully covers function 1:
- **Supermemory plugin** (`supermemory@supermemory-plugins`) auto-captures conversation context and injects `<supermemory-context>` at every session start — semantic context carry at zero cost
- **`plans/active-context.md`** carries structured, machine-readable state (plan file reference, current step, focus) that hooks can `grep` at runtime
- **Auto-memory** (`~/.claude/projects/.../memory/`) stores curated cross-session knowledge

Functions 2 and 3 (status tracking and fzf preview) depend on the session-hub picker, which adds maintenance overhead without commensurate value. Dropped by user decision.

The Stop hook that wrote `session-handoff.md` was already removed in a prior wave. The post-read-auto-delete hook was already retired. This decision formalizes the complete removal.

## What Changed

| Removed | Replacement |
|---|---|
| `plans/session-handoff.md` writes | Supermemory auto-capture (semantic) + `active-context.md` copy (structural) |
| `tmux/scripts/session-hub.sh` + 4 helpers | Dropped (no replacement) |
| `ai/commands/session-{defer,undefer,done,picker,next}.md` | Dropped |
| `plans/session-handoff.md` gitignore entry | Removed |
| `Ctrl+A G` tmux keybinding | Unbound |
| `stack-create` Step 6 (handoff write) | Step 4: copy `active-context.md` to new worktree |

## Alternatives Rejected

- **Minimal status-only file** (e.g. `plans/session-status.md`): still a dependency to maintain; no consumer after picker removal
- **Dotfile outside `plans/`**: same maintenance cost, lower visibility
- **Explicit Supermemory write in stack-create**: redundant — the plugin auto-captures conversation context; an explicit POST adds nothing the plugin doesn't already do

## Assumptions

- Supermemory local server (`http://localhost:6767`) is running when sessions are active
- User maintains `plans/active-context.md` update discipline as the structural resume point
- Hooks that read `active-context.md` (`pre-tool-gate-v2.sh` PLAN CONTEXT, `plans-healthcheck.sh`) continue to function with the file-copy approach
