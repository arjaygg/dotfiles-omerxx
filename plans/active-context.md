# Active Context

## Current (2026-07-28) — Goal 05: native agent orchestration harness

goal: goals/2026-07-28-05-native-agent-orchestration-harness.md
status: active
focus: Step 17 (unblocked), then Step 18 (after 15, 16 — both now shipped)

Steps 1-16 are all shipped; no goal-05 branch is outstanding.
- Steps 1-9, 13, 16 merged as PRs #361-#373. Step 10 as #374 (+ follow-up #375), Step 11 as
  #376, Step 12 as #377.
- Step 14 (orchestrator skeleton, interactive) merged as #383 -> `14a2ec7`.
- Step 15 (unattended-safety delta) merged as #389 -> `c87f60c`: §23 triage with the enforced
  scope-authority rule, §24 counters read from spec frontmatter, §25 computed follow-up signal,
  §15 HALT on every exit path, §20 finding fields across schemas.md + orchestrate.js + tests,
  auto-ship reusing the HALT definition. Nine dry runs, 0 agents. Suite 247/247, 33 orchestrate
  tests. Still one literal subagent call site.

Remaining: 17 (unblocked), 18 (unblocked now that 15 and 16 are both in).

Carried forward from Step 15, needs a decision:
- The plan's §20 says schemas.md requires per-finding `severity` and Step 15 removes it. Step 10
  already did, so that acceptance criterion passes vacuously. Step 15 substituted the real gap
  (the §20 field names). The plan text itself is still stale and should be corrected.
- §15's "kill a run mid-flight" criterion is met for thrown stages via try/finally but cannot be
  met for SIGKILL in-process. Covered from the other side: frontmatter still `running` with no
  terminal status is a crashed run. Judge whether that satisfies the plan.

Open, unrelated to goal 05:
- The ~55-60k static context baseline; whether PR #381's autocompact fix holds is unverified.
- 21 older PRs (mostly 2026-07-13 drafts) remain unmerged.

---

## Previous (2026-07-27) — orchestration plan v2 authoring

Superseded by goal 05 above; plan v2 (plans/2026-07-27-native-agent-orchestration.md)
is the durable design reference driving all 18 steps.
