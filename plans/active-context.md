# Active Context

## Current (2026-07-27) — Native agent orchestration plan v2

plan: `plans/2026-07-27-native-agent-orchestration.md` (renamed from `native_agent_orchestration_plan.md`)
step: authoring complete; 15 steps defined, none started
focus: reconcile orchestration plan with real Claude Code primitives + `addyosmani/agent-skills` practices

Branch `feat/agent-orchestrator-harness`. v1 committed as `ab27c37`; v2 (+336/-19) uncommitted.

**v1** — audited the v0 draft against live tool schemas, docs, and this repo (33-agent workflow,
55 findings survived adversarial refutation). Rewrote around real primitives: `Agent`/`SendMessage`/
`Workflow`, fork-vs-fresh, `tools:`-allowlist anti-nesting, worktree-isolation retrieval paths.

**v2** — integrated `~/git/agent-skills` @ `7829ffd`. Added: five-layer model (we are missing the
**References** and **Evals** layers), three-tier eval harness, skill-anatomy sections
(Rationalizations / Red Flags / Verification), the doubt cycle for §9b, Definition of Done, and
**Part III — the autonomy ladder A0-A4** (evals as the currency that buys autonomy).

**Open decisions blocking execution:**
1. Step 3 — frozen-spec path: per-worker `plans/specs/<label>.md` (recommended) vs single `plans/spec.md`.
2. Step 8 — `/tech-lead` is `"off"` at both settings scopes: re-enable and retrofit, or retire.

**Live defect found, not yet fixed:** `ai/agents/cicd-{audit,auto-retry,monitor,review}.md` have no
`tools:` line, so they inherit `Agent` and can spawn nested subagents today (Step 1).

---

## Previous (2026-07-26) — Agentic git pipeline goal fully complete

Goal `goals/2026-07-25-03-agentic-git-pipeline.md` (design: `plans/2026-07-25-agentic-git-pipeline.md`)
is **done**. All 8 steps (0-7) landed, plus the documentation-closure follow-up:

- Steps 0-6: hooks, validation scripts, autonomy flags, `auto-ship` skill, doc reconciliation —
  all merged to `main` via PR #353 (2026-07-26).
- Step 7 end-to-end shakedown: PR #352 exercised commit -> push -> PR -> merge -> cleanup on a
  scratch branch; PR #353's own landing into `main` exercised the two previously-outstanding legs
  for real (CI-wait via `ai/skills/ci-watch/SKILL.md`, sync-against-main via `git pull --ff-only`).
- Doc-gap closure: PR #354 (`docs/goal03-step7-gap-closure`, merged 2026-07-26) updated the goal
  file's "current state" / Step 7 note / acceptance criteria to reflect Step 7 as fully exercised
  with no remaining gaps.

**No open work remains on this goal.** All acceptance criteria are checked off in the goal file.
Worktrees for both feature branches (`docsrevise-agentic-git-pipeline-plan`,
`docsgoal03-step7-gap-closure`) have been removed after confirming their content matched `main`.

**Next:** none pending. Start a fresh session for any new task.
