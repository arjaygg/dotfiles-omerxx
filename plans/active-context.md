# Active Context

## Current Focus: Clean slate — all branches merged (2026-04-01)

Branch: `main`
No active plan.

All prior feature branches merged into main:
- chore/stack-skills-overhaul (PR #109)
- feat/git-hygiene-enforcement (merged via #109)
- chore/worktree-settings-defaultmode (PR #105)
- feat/todo-gate-enforcement (PR #98)
- feat/self-learning-prompt-library (PR #111)
- feat/tool-call-hooks-optimization (closed — already upstream)
- chore/consolidate-hooks-v2 (PR #113)

### Hook Architecture

Consolidated to v2 (2026-04-01):
- PreToolUse: 1 hook (`pre-tool-gate-v2.sh`) replaces 6 individual scripts
- PostToolUse: 1 hook (`post-tool-analytics.sh`) replaces 4 individual scripts
- todo-gate: promoted to block mode
- edit-without-read: promoted to block mode
