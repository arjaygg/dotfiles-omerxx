# Active Context

plan: plans/2026-06-12-ai-primitives-upgrade.md
step: 0 of 19
focus: plan written — awaiting user review before Wave 1 execution

## Current Focus (2026-06-12)

AI primitives audit (`/autoresearch` analysis run, ultracode): audited all skills,
hooks, agents, rules, and MCP/cross-tool configs; researched current Claude Code /
Codex / Gemini CLI capabilities; produced verified improvement plan.

Workflow `ai-primitives-audit` (wf_6bbf6240-70d): 32 agents, 4 dimensions,
20 proposals — all survived adversarial verification (6 keep, 14 modify).

## Carried Over (from 2026-06-10 handoff)

- Untracked skills in .claude/skills/ still need promotion to ai/skills/ + symlink +
  commit (covered by plan Wave 1, Step 1).
- .bak litter in .claude/skills/lean-ctx/ and .cursor/hooks/ (same step).

## Known Defect (discovered this session)

`read-before-write-guard.sh` + hooks that touch `plans/*.md` per prompt deadlock
native Write on existing plans files (Read always returns stale marker).
Fix scheduled as plan Wave 1 step; workaround: rm + Write, or LeanCtx.ctxEdit.

## Next

User reviews plan → execute Wave 1 on a stack branch (NOT main).
