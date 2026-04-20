# Active Context

plan: plans/2026-04-18-session-hygiene-enforcement.md
step: 0 of 4
focus: new session — awaiting user direction (2026-04-20)

## Current Task

Implementing findings from Apr 15–18 auc-conversion session analysis. Four enforcement gaps identified:

1. session-handoff.md persistence (676 injections/session) → PostToolUse auto-delete hook
2. tool-priority.md pipe-limiter has no external CLI exception → doc edit
3. auc-conversion AGENTS.md missing code-path advisor triggers + TaskTracking discipline
4. plans-healthcheck.sh doesn't detect stale active-context.md

## Branch

`chore/enforce-session-hygiene` (dotfiles) + separate branch in auc-conversion for Fix 3

## Key Files

- `.claude/hooks/post-read-auto-delete.sh` (create)
- `.claude/settings.json` (add PostToolUse hook)
- `ai/rules/tool-priority.md` (add external CLI pipe exception)
- `.claude/hooks/plans-healthcheck.sh` (extend staleness check)
- `/Users/axos-agallentes/git/auc-conversion/AGENTS.md` (add two sections)
