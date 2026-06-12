# 0006 — Cross-Tool Skills Standard Path: ~/.agents/skills

**Status:** Accepted  
**Date:** 2026-06-12

## Decision

Adopt `~/.agents/skills` as the canonical discovery path for user-scoped AI skills, backed by
a single symlink: `~/.agents/skills → ~/.dotfiles/ai/skills`.

## Context

Before this change, skill distribution was per-tool:
- `~/.codex/skills/` — populated by a per-skill loop in `setup.sh` (fragile, grows over time)
- `~/.gemini/skills/` — nested layout from initial setup, duplicated content
- `~/.cursor/skills/` — an explicit subset with manually-maintained entries
- `~/.claude/skills/` — symlinks to `ai/skills/` (correct, but still per-tool)

Each tool required its own distribution maintenance. Adding a new skill meant updating 3–4 places.

## New Standard

Codex 0.130.0+ and Gemini 0.42.0+ both discover user-scoped skills from `~/.agents/skills`.
One symlink covers both tools.

`setup.sh` now runs:
```bash
mkdir -p "$HOME/.agents"
ln -sfn "$HOME/.dotfiles/ai/skills" "$HOME/.agents/skills"
```

## Backwards Compatibility

The Codex legacy path (`~/.codex/skills/`) is retained for Codex < 0.130.0. Both paths coexist
harmlessly. The per-skill loop in `setup.sh` is kept but will be deprecated after confirming
the installed Codex version is ≥ 0.130.0 across all machines.

Cursor and Gemini paths remain until their skill format reaches parity with the `~/.agents/skills`
standard.

## Alternatives Rejected

- **Per-tool loops**: Too much maintenance surface; breaks silently when a skill is added to
  `ai/skills/` but not re-run through `setup.sh`.
- **Direct ai/skills references in each tool config**: Works but requires each tool to hard-code
  an absolute path — not portable.

## Assumptions

- Codex version on this machine is ≥ 0.130.0.
- Gemini CLI version is ≥ 0.42.0.
- Neither tool's `~/.agents/skills` discovery breaks when the path is a symlink (not a real dir).
