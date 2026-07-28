# Active Context

## Current (2026-07-28) — Goal 05: native agent orchestration harness

goal: goals/2026-07-28-05-native-agent-orchestration-harness.md
status: active
focus: Step 14 — orchestrator skeleton (interactive only); unblocked

Merged to main. Steps 1-13 and 16 are all shipped; no goal-05 branch is outstanding.
- Steps 1-9, 13, 16 merged as PRs #361-#373 (two checkpoint branches included).
- Step 10 (lensed-review consolidation) merged as #374; evidence report at
  plans/2026-07-28-step10-acceptance.md.
- Follow-up #375: lensed-review predated step13's anatomy convention, so validate_skills.py
  failed repo-wide once both landed. Fixed by adding its Verification section.
- Step 11 (customization layer) merged as #376: scripts/resolve_customization.py, three-layer
  base -> .claude/custom/<skill>.toml -> .user.toml resolution, ai/skills/README.md.
- Step 12 (generated router) merged as #377: ai/skills/manifest.csv is the source of truth,
  using-my-skills/SKILL.md is generated from it, linter fails on manifest drift.

Remaining: 14 (unblocked), 17 (unblocked), then 15 (after 14) and 18 (after 15, 16).
Step 15's "no finding-level severity in schemas.md" criterion is already satisfied by Step 10.

Unrelated, merged 2026-07-28 (PR #381): autocompact threshold 70 -> 88 (was thrashing against a
75-81k post-compact floor); subagent rule inverted to fresh-by-default; tracked settings.json
sanitized, suite back to 210/210. Open: the ~55-60k static baseline is untouched. New sessions
only — verify by re-measuring compaction frequency from transcript usage fields.

Open, unrelated to goal 05: 21 older PRs (mostly 2026-07-13 drafts) remain unmerged.

---

## Previous (2026-07-27) — orchestration plan v2 authoring

Superseded by goal 05 above; plan v2 (plans/2026-07-27-native-agent-orchestration.md)
is the durable design reference driving all 18 steps.
