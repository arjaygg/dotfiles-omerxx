# Active Context

plan: decisions/RFC-STACK-SHIP-001.md
step: Phase 1 of 4
focus: Core merge algorithm + skill implementation

## Current Task

Implementing RFC-STACK-SHIP-001: Fully Automated Stack Branch → Release Pipeline
Phase 1: Core skill with merge algorithm, validation, and logging.

## Work Items

Phase 1 Implementation:
- [x] Create RFC-STACK-SHIP-001.md specification
- [x] Create ai/skills/stack-ship/SKILL.md documentation
- [x] Create .claude/scripts/stack-ship.sh implementation
- [ ] Test with stacked branches in this repo
- [ ] Create PR and merge to main

## Branch

`chore/stack-ship` (dotfiles) — Phase 1 implementation

## Key Files

- `decisions/RFC-STACK-SHIP-001.md` — Full RFC specification
- `ai/skills/stack-ship/SKILL.md` — Skill documentation
- `.claude/scripts/stack-ship.sh` — Implementation script
- `plans/active-context.md` — This file
- `.stack-ship/log.jsonl` — Audit log (created on first merge)
