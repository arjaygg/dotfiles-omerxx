# 0007 — migration-watchdog: keep as single skill (no split)

**Date:** 2026-06-12
**Status:** Accepted

## Context

During the AI primitives upgrade (Step 1), a question arose about whether to split
`ai/skills/migration-watchdog` into two skills:

- A read-only **health-check** skill (observation + reporting, no remediation)
- An **active-remediation** skill (capable of writing playbook fixes)

The skill was also found to have a stale copy in `.claude/skills/migration-watchdog/` as a
real directory with obsolete content, while `ai/skills/migration-watchdog/` held the
canonical up-to-date version.

## Decision

Keep `migration-watchdog` as a single skill.

## Why

1. **Remediation is already delegated** — the `disallowed-tools: [Edit, Write, MultiEdit]`
   frontmatter guard added in Step 6 enforces read-only behavior at the tool level. Active
   remediation is handled by `watchdog-remediate` as a separate, explicitly invoked skill.
2. **Single responsibility is already satisfied** — the watchdog observes and reports;
   remediation requires a separate invocation. Splitting into two skills adds no safety beyond
   what the `disallowed-tools` guard provides, and adds cognitive overhead.
3. **Maintenance burden** — two skills sharing context about the same migration system would
   require keeping both SKILL.md files in sync.

## Alternatives Rejected

- **Split into health-check + active-remediate**: Redundant with `watchdog-remediate` skill
  and the existing `disallowed-tools` guard. The added complexity brings no benefit.

## Consequences

- `.claude/skills/migration-watchdog/` (stale real directory) replaced with relative symlink
  to `ai/skills/migration-watchdog/`.
- `check-skill-drift.sh` will catch any future regression to a real directory.
- `watchdog-remediate` remains the designated active-remediation skill.
