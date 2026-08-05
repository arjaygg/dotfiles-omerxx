# Claude Project Instructions — ~/.dotfiles

Project-scoped adapter for **this repository**. Claude loads it as
`<project>/.claude/CLAUDE.md` when working in `~/.dotfiles`.

It is **not** the user-global entrypoint — that is the live `~/.claude/CLAUDE.md`, whose tracked
template is `.claude-global/CLAUDE.md` (see `decisions/0020`). It said otherwise until 2026-08-03,
which made two files claim the same role.

The imports below resolve relative to this file, so they work in-repo.

@../ai/rules/agent-user-global.md
@../ai/rules/tool-priority.md
@../ai/rules/context-and-compaction.md
@../ai/rules/hyper-atomic-commits.md
@../ai/rules/delegation-and-context-admission.md

## Claude-Specific Notes

- Project-specific rules belong in each repository's `CLAUDE.md`, `AGENTS.md`, and `.claude/rules/`.
- Claude hooks and settings provide enforcement. This file provides behavioral guidance only.
- Auto memory is useful context, but tracked project docs override it when they conflict.

<!-- lean-ctx -->
<!-- /lean-ctx -->
