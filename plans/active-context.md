# Active Context

## Current (2026-07-28) — Goal 05: native agent orchestration harness

goal: goals/2026-07-28-05-native-agent-orchestration-harness.md
status: active
focus: Step 18 done (A0-A4 tiers + resolver + gate demotion + signed re-acceptance). Needs a PR.
  Step 18 spawned **Step 19** — pre-action enforcement of the A2 cap in pre-tool-gate-v2.sh, because
  a Stop hook cannot precede the merge it would guard. Step 19 is NOT started and NOT authorized.
in flight: `feature/autonomy-ladder-reconcile` (#395) — Step 18, open for review, NOT merged.
  Record `<branch> (#PR)` here at branch-create time, before any work. Three
  near-duplications on 2026-07-28 (#383/#385, #392, #387/#389) happened because this file carried
  only *merged* state, so a parallel session's open branch was invisible.
plan: plans/2026-07-27-native-agent-orchestration.md — durable design reference for all 18 steps.

Steps 1-17 shipped as PRs #361-#392. Step 18 is committed on
`feature/autonomy-ladder-reconcile` (`a553f11`, `9cadf12`, + docs) and needs a PR. Per-step detail
and evidence live in plans/progress.md, not here. **Remaining: open the Step 18 PR, then Step 19.**

Live consequence of Step 18 to carry forward: `auto_ship`/`auto_clean` now *resolve* to effective
A0 (no eval evidence exists for any pipeline leg, and the A2 cap applies). Nothing consults the
resolver yet, so behaviour is unchanged today — Step 19 turns that into enforcement and will stop
unattended merges. Two facts found while implementing: `.claude/settings.json` and
`settings.base.json` are **not** byte-identical (base is deliberately `$HOME`-relative) and
`config-integrity.sh` never checks them against each other, so the goal file's "keep byte-identical"
invariant is wrong as written; and `skipDangerousModePermissionPrompt: true` is set in both live
settings and `settings.local.json`, which may defeat `permissions.ask` as an A2 checkpoint.

Carried forward from Step 15, still needs a decision:
- The plan's §20 says schemas.md requires per-finding `severity` and Step 15 removes it. Step 10
  already did, so that criterion passes vacuously. The plan text itself is stale.
- §15's "kill a run mid-flight" cannot be met for SIGKILL in-process; covered from the other side
  (frontmatter still `running` with no terminal status = crashed run). Judge if that suffices.

Open, unrelated to goal 05:
- The ~55-60k static context baseline is ~75% fixed Claude Code overhead — measured, judged not
  worth trimming. Whether #381's autocompact fix holds is unverified (needs elapsed sessions).
- #349 (regenerates at session init — likely closeable) and the 19-draft 2026-07-13 cluster: one
  stalled workstream, a batch decision rather than 19 reviews.
- 89 stale merged branch refs (rebase-merge artifact, content is on main) — safe to delete.
