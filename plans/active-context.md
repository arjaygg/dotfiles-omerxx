# Active Context

## Status: COMPLETE — CI/CD Lifecycle Redesign

**Task:** Deep analyze existing CI skills, identify improvements, apply Claude Code primitives, and implement unified PR→merge→deploy lifecycle.

**Completion:** All changes implemented and committed to main dotfiles repo (commit `97ae44a`).

## Implementation Summary

### New Skills (2)
- **`ci-pr-lifecycle`** (v1.0): Full PR lifecycle monitor with combined CI + review polling
- **`ci-deploy-watch`** (v1.0): Post-merge deployment monitor

### Updated Skills (4)
- **`ci-monitor`** (v3.0 → v4.0): Repo auto-detection from git remote
- **`ci-status`** (v1.0 → v2.0): Unified status surface
- **`ci-watch`**: Deprecation notice + redirect
- **`stack-pr`**: Added auto-chain instruction to `/ci-pr-lifecycle`

### Hooks & Configuration
- **`post-pr-lifecycle-advisory.sh`**: Advisory on PR creation
- **`post-merge-deploy-advisory.sh`**: Advisory on PR merge
- **`.claude/settings.json`**: Registered two PostToolUse hooks

## Architecture

Single combined Monitor loop:
- Polls CI checks (`gh run list`) + review state (`gh pr view`) every 30s
- Emits events only on state change: `CI_COMPLETE`, `REVIEW_CHANGED`
- Skill-level chaining (primary): `stack-pr` → `/ci-pr-lifecycle`
- PostToolUse hooks (secondary): Advisory text if user invokes `gh pr create` directly
- Event routing: CI success+review approved → "All gates passed — run /stack-merge to land"

## Files Modified

- `ai/skills/ci-pr-lifecycle/SKILL.md` (NEW)
- `ai/skills/ci-deploy-watch/SKILL.md` (NEW)
- `ai/skills/ci-monitor/SKILL.md` (UPDATED)
- `ai/skills/ci-status/SKILL.md` (UPDATED)
- `ai/skills/ci-watch/SKILL.md` (UPDATED)
- `ai/skills/stack-pr/SKILL.md` (UPDATED)
- `.claude/hooks/post-pr-lifecycle-advisory.sh` (NEW)
- `.claude/hooks/post-merge-deploy-advisory.sh` (NEW)
- `.claude/settings.json` (UPDATED)
