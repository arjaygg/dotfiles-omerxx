# Claude Code — Dotfiles Project Adapter

This file is the Claude project entrypoint for `~/.dotfiles`.

@AGENTS.md

## Claude-Specific Notes

- User-global defaults come from `~/.claude/CLAUDE.md` and any files under `~/.claude/rules/`.
- Claude-only enforcement lives in `.claude/settings.json` and `.claude/hooks/`.
- Use `.claude/rules/` only for Claude-specific or path-scoped behavior. Shared repo policy belongs in `AGENTS.md` and neutral docs.
