# Active Context

## Current (2026-07-28) — Goal 05: native agent orchestration harness

goal: goals/2026-07-28-05-native-agent-orchestration-harness.md
status: active
focus: Step 15 — unattended paths; needs a frozen spec at plans/specs/<label>.md first

Steps 1-14 and 16 are all shipped; no goal-05 branch is outstanding.
- Steps 1-9, 13, 16 merged as PRs #361-#373. Step 10 (lensed-review) as #374, plus
  follow-up #375. Step 11 (customization layer) as #376. Step 12 (generated router) as #377.
- Step 14 (orchestrator skeleton) merged as #383 -> `14a2ec7`: `.claude/workflows/orchestrate.js`
  (first entry in that directory) + `scripts/test_orchestrate_workflow.py` (13 static tests).
  Three phases, one `runStage()` helper so the file holds a single literal subagent call site
  under SECTION 8's cap of 3. Verified by two dry runs, 0 agents spawned: DoD present ->
  `ok:true`; DoD absent -> `ok:false, unmet:[...]`. Interactive only.

Remaining: 17 (unblocked), 15 (after 14, now unblocked), 18 (after 15, 16).
Step 15's "no finding-level severity in schemas.md" criterion is already satisfied by Step 10.
Step 15 owns the next change to `ai/skills/cap/references/schemas.md`.

Open, unrelated to goal 05:
- The ~55-60k static context baseline (PR #381 raised the autocompact threshold but did not
  shrink the floor); whether that fix holds is still unverified — re-measure compaction
  frequency from transcript `usage` fields. Measured since: ~75% of the baseline is fixed
  Claude Code overhead, so trimming the rules chain buys ~2% of a 200k window — not worth it.
- 21 older PRs (mostly 2026-07-13 drafts) remain unmerged.
- `stack merge` warns "Charcoal rebase encountered issues (non-fatal)" and synced 0 of 51 PR
  bases on #383. Harmless for Step 14 (no dependents); unexamined for the other 34 worktrees.

---

## Previous (2026-07-27) — orchestration plan v2 authoring

Superseded by goal 05 above; plan v2 (plans/2026-07-27-native-agent-orchestration.md)
is the durable design reference driving all 18 steps.
