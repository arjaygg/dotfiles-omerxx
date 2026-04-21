# Active Context

plan: plans/2026-04-21-insights-dx-improvements.md
step: 1 of 3
focus: Session 1 — B-01 through B-07 (dotfiles enforcement + rules)

## Current Task

Implementing RFC-DOTFILES-002 backlog from Claude Code Insights reports (Apr 1–21 2026).
Cap orchestrating implementation across P1 + P2 items.

Session 1 scope (B-01 → B-07):
- B-01: auc-conversion AGENTS.md — Advisor Triggers + Task Tracking sections
- B-02: plans-healthcheck.sh — stale active-context.md detection
- B-03: ci-watch + ci-status skills
- B-04: pre-push-remote-check.sh hook + settings.json registration
- B-05: pre-tool-gate-v2.sh — File-Too-Large interceptor
- B-06: agent-user-global.md — echo-back protocol rule
- B-07: agent-user-global.md — scope declaration rule

## Branch

`chore/insights-dx-improvements` (dotfiles) — use stack-create before editing

## Key Files

- `plans/2026-04-21-insights-dx-improvements.md` — RFC with all Accepts criteria
- `.claude/hooks/pre-tool-gate-v2.sh` — extend for B-05
- `.claude/hooks/plans-healthcheck.sh` — extend for B-02
- `.claude/hooks/pre-push-remote-check.sh` — create for B-04
- `.claude/settings.json` — register B-04 hook
- `ai/rules/agent-user-global.md` — add B-06, B-07 rules
- `ai/skills/ci-watch/SKILL.md` — create for B-03
- `ai/skills/ci-status/SKILL.md` — create for B-03
- `/Users/axos-agallentes/git/auc-conversion/AGENTS.md` — add sections for B-01
