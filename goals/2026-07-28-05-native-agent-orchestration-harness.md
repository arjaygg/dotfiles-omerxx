# Goal 05 — Native Agent Orchestration Harness

## Objective

Build the harness specified in `plans/2026-07-27-native-agent-orchestration.md` so that a delegated
unit of work in this repo runs **spec → worker → verify → triage → halt-or-ship** without a human
"now do X" prompt between phases, and so that every autonomy level the harness operates at is backed
by a committed eval run rather than a config flag.

Concretely, "done" means all 18 of the plan's `**Accepts:**` blocks are satisfied, which delivers
five things this repo does not have today: an eval harness (Tiers 1-4), a References layer, a single
lensed review skill replacing nine overlapping review skills/agents, a skill customization and
retirement lifecycle, and an autonomy ladder (A0-A4) whose demotion triggers are enforced by a gate
rather than remembered.

## Why

The repo has ~73 skills, 11 agents, and a fully-armed git pipeline, with **zero** evidence that any
skill triggers when it should. Three specific consequences are live right now, not hypothetical:

1. **No routing validation.** Description collision scales quadratically; at 73 skills it is
   near-certain and presents as the wrong skill activating — which reads as a model failure and gets
   debugged as one. Nine review-ish skills/agents currently compete in the same routing space.
2. **Anti-nesting is unenforced.** `ai/agents/cicd-audit.md`, `cicd-auto-retry.md`, `cicd-monitor.md`,
   and `cicd-review.md` declare no `tools:` allowlist, so they inherit `Agent` and can spawn nested
   subagents today. Claude Code 2.1.219+ permits three layers by default; the prose rule in
   `ai/rules/agent-user-global.md` enforces nothing.
3. **Autonomy is asserted, not earned.** All five `.claude-atomic.yaml` pipeline flags
   (`auto_commit`/`auto_push`/`auto_pr`/`auto_ship`/`auto_clean`) are `true` as of `7390f63`, while
   no eval tier exists. `auto_ship` and `auto_clean` are irreversible actions the plan's ladder caps
   at A2. This is a user-accepted risk, recorded so it is visible rather than implicit.

The design is review-complete: three independent fresh-context reviewers (fable tier, given
artifact + contract only and no severity authority) returned 58 findings against the plan and
converged independently on five, including a forked triage taxonomy and two competing review
harnesses. All 58 are folded in; the plan was reorganised by mechanism rather than by source as a
result.

## Current state

Design-complete, implementation not started. **No step has begun.**

- `plans/2026-07-27-native-agent-orchestration.md` (1,034 lines, branch `docs/orchestration-plan-v3`,
  **uncommitted**) is the durable design reference. This goal is a tracking summary — do not
  duplicate the plan's mechanism sections here.
- The plan synthesises three sources: this repo (**RE**), `~/git/agent-skills` @ `7829ffd` (**AS**),
  and `~/git/BMAD-METHOD` @ `bb45db4a` v6.10.0 (**BM**). Appendix A is the import/reject ledger;
  Appendix B lists the open decisions.
- It supersedes `plans/2026-04-02-bmad-learnings.md`, which reviewed BMAD v6.0.0-Beta.2 and reversed
  two verdicts that v6.10.0 justifies. That plan's three accepted patterns were never implemented
  (`ai/knowledge/` does not exist) and are subsumed by plan §28 — do not reopen them.
- Verified sound as of 2026-07-27: every cited `settings.json` line reference, all **AS**/**BM**
  quotations, agent frontmatter counts, and Claude Code 2.1.220. Ten factual defects were found and
  fixed in the same pass.
- **Two open decisions block specific steps** (Appendix B): the frozen-spec path (blocks Step 3) and
  `/tech-lead`'s disposition (blocks Step 9). Steps 1, 2, and 6 are independent and unblocked.
- `scripts/validate_goals.py` does not exist in this repo, so this goal file has **not** been
  machine-validated for heading order or index consistency — only checked manually against the
  `goal-authoring` convention. `goals/README.md` and `scripts/pre-commit-goals.sh` are likewise
  absent. Installing them is not part of this goal.

**Scope caution for a fresh agent:** 18 steps is large for one goal. It is tracked as one because
the steps form a single dependency graph, not because the whole thing should be attempted in one
session. Work one step per session where practical, and see "Stop and ask if" on splitting.

## Non-goals

- **Any change to non-Claude CLIs.** Cursor, Codex, and AGY stay on `ai/skills/tmux-orchestrator/`.
  That skill is scoped, not deleted — it is the only cross-CLI capability and no Claude primitive
  replaces it.
- **Retiring Claude Code built-in skills.** `review`, `simplify`, `code-review`, `run`, and `explore`
  are built-ins. They cannot be shimmed, ledgered, or removed; the consolidated skill is named
  `lensed-review` specifically to avoid colliding with `/review`.
- **Reimplementing `cap`'s phase machinery.** `ai/skills/cap/` already orchestrates the TDD
  feature-delivery path on the Workflow runtime. This harness owns generic delegation (research,
  audit, migration, multi-file refactor); shared definitions live in the plan and `cap` adopts them.
- **Promoting `pre-tool-gate-v2.sh` gates from warn to deny**, beyond the fan-out deny already
  shipped. That is goal 03's deferred decision, not this goal's.
- **Building a pre-commit framework.** The repo uses `core.hooksPath` → `~/.dotfiles/git/hooks`;
  new checks wire in there.
- **Installing the `goals/` validator, README, or pre-commit hook.** Tracked separately.
- **Cross-machine locking, multi-worktree sync fan-out, or Agent Teams adoption.** Teams stay
  experimental and out of scope; the harness uses `Workflow` and `Agent`.
- **Raising any autonomy tier above A2 for irreversible actions**, regardless of accumulated
  evidence.

## Steps

Numbering matches `plans/2026-07-27-native-agent-orchestration.md` `# Steps` exactly, so references
here and in the plan cannot drift. Each step's full `**Files:**`/`**Accepts:**` block lives in the
plan; this is a tracking summary. All 18 are **pending**.

Independent and parallel-safe: **1, 2, 6**. Everything else has a stated predecessor.

- **Step 1 — Close the anti-nesting hole** — pending. `tools:` allowlists on the four `cicd-*`
  agents plus `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` in both settings files.
- **Step 2 — Create the References layer** — pending. `ai/references/definition-of-done.md` + symlink.
- **Step 3 — Spec template and path convention** *(after 2)* — pending. **Blocked on decision 1.**
- **Step 4 — Executor agent definition** *(after 1, 3)* — pending.
- **Step 5 — Hooks: dead matchers and missing events** *(one step, same JSON block)* — pending.
- **Step 6 — Tier 1: the skill linter** — pending. Ratchet semantics against a committed baseline.
- **Step 7 — Tier 2: trigger and routing evals** *(after 6)* — pending. Commit the collision report.
- **Step 8 — `/tech-lead` disposition** *(decision; blocks 9)* — pending. **Blocked on decision 2.**
- **Step 9 — Skill lifecycle ledger** *(after 8)* — pending.
- **Step 10 — Consolidate review into `lensed-review`** *(after 7, 9)* — pending.
- **Step 11 — Customization layer** *(after 10)* — pending.
- **Step 12 — Router and core operating behaviors** *(after 9, 10)* — pending. Router is
  **generated** from `ai/skills/manifest.csv`, not hand-written.
- **Step 13 — Skill anatomy and step-file decomposition** *(after 6; one step, same files)* — pending.
- **Step 14 — Orchestrator skeleton, interactive only** *(after 2, 3, 10)* — pending.
- **Step 15 — Unattended-safety delta** *(after 14)* — pending. Also amends
  `ai/skills/cap/references/schemas.md` to drop finding-level `severity`.
- **Step 16 — Tier 3 and pressure cases** *(after 7)* — pending.
- **Step 17 — Tier 4 input sensitivity** *(after 10, 16)* — pending.
- **Step 18 — Reconcile the autonomy ladder with config** *(after 15, 16)* — **done 2026-07-28**.
  Gap re-accepted in writing, asymmetrically: reversible legs keep A2 on a dated signed override
  (`expires: 2026-10-31`), irreversible legs are not re-accepted and resolve to A0 under the A2 cap.
  Two clauses were amended, not faked — pre-action enforcement moved to a new **Step 19** (a Stop
  hook cannot precede the merge it guards), and tier declaration was scoped to the five pipeline
  legs rather than every workflow and skill.

## Acceptance criteria

Each bullet is the corresponding step's `**Accepts:**` line in the plan, reduced to its verifiable
check. `[ ]` = pending; `[x]` = verified satisfied. **Do not mark a box without running the check.**

- [ ] **Step 1** — `grep -L '^tools:' ai/agents/*.md` returns nothing; depth env key present in both
      settings files; `bash .claude/hooks/config-integrity.sh` exits 0; settings files byte-identical.
- [ ] **Step 2** — `test -L .claude/references` passes after `./setup.sh`; DoD separates its five
      sections and is distinguished from per-task acceptance criteria; ≥2 skills reference it.
- [ ] **Step 3** — template carries `<intent-contract>`, `## Spec Change Log`, `## Review Triage Log`
      and the five frontmatter counters; `grep -rn 'plans/spec\.md' ai/ .claude/` returns only the
      updated rule; `active-context.md` is named as a spec location nowhere.
- [ ] **Step 4** — `model: sonnet`; `tools:` excludes `Agent`; symlink resolves after `./setup.sh`;
      `config-integrity.sh` exits 0.
- [ ] **Step 5** — `python3 scripts/hook_config_check.py` exits 0 with no `MATCHER_UNSUPPORTED`
      issues; `TeammateIdle` and `SubagentStop` wired; a worker completion produces a hook log line.
- [ ] **Step 6** — linter exits 1 only on violations absent from `scripts/skill_lint_baseline.json`;
      accepts a Verification section in a declared step file; enforces the `ai/agents` `tools:`
      invariant; wired into `git/hooks`.
- [ ] **Step 7** — rank-1 rate printed and enforced against a committed floor; 75/50 collision gates
      active; the full ~73-skill collision report is committed.
- [ ] **Step 8** — either both `"tech-lead": "off"` entries removed and the skill carries the spec
      handoff + acceptance gate, or the retirement decision is recorded here.
- [ ] **Step 9** — every `"off"` skill has a ledger entry with state and rationale; `tech-lead`'s
      entry records Step 8's outcome; `setup.sh` removes `retired` symlinks; built-ins excluded.
- [ ] **Step 10** — `lenses.toml` parses with five keys per lens; an empty-`instruction` lens is
      skipped in a dry run; each reference file ≤90 lines; findings carry `lens` and no `severity`
      (`grep -c severity` on the schemas → 0); collision report improves against the Step 7 baseline;
      superseded skills have shims + ledger entries + migrated eval cases.
- [ ] **Step 11** — all four merge rules unit-tested including an `id`-keyed array; DO-NOT-EDIT banner
      present; three-file fallback specified; missing `file:` path named-and-skipped, test-covered.
- [ ] **Step 12** — router regenerates idempotently from `manifest.csv`; linter fails on a manifest
      row naming a nonexistent skill or a skill absent from the manifest; six behaviors stated;
      session-init hook degrades without `jq`, with a payload-shape regression test.
- [ ] **Step 13** — each of four skills has ≥4 rationalization rows, ≥1 checkable red flag, and an
      evidence-naming Verification checklist; `cap/SKILL.md` reduced to activation + step-1 pointer;
      anti-shortcut instruction verbatim in each step file; `step-oneshot.md` preserves the
      single-pass path; both `wc -l` numbers recorded in the commit body; Step 6's linter passes.
- [ ] **Step 14** — `grep -c 'agent(' .claude/workflows/orchestrate.js` ≤ 3; every `agent()` has
      `schema` + `label` and is null-guarded; reviewer stage invokes `lensed-review` and passes
      artifact + contract only; acceptance stage reads the DoD or logs its absence;
      `Workflow({scriptPath, args:{dryRun:true}})` returns a schema-valid result.
- [ ] **Step 15** — no finding-level `severity` in `schemas.md`; a fixture whose only exclusion basis
      is the spec's own scope language routes `bad_spec`, not `defer`; `review_loop_iteration`
      forced to 6 yields `blocked` / `non-convergence`; `followup_review_recommended` matches a
      hand-computed fixture; no `run_in_background|detached` on unattended paths; a killed run leaves
      a terminal status file, including the unresolvable and ambiguous cases.
- [ ] **Step 16** — all four Tier-3 properties verified by running one behavioral case; every
      discipline skill carries time-pressure, sunk-cost, and authority-pressure cases.
- [ ] **Step 17** — `lensed-review` has baseline / vague / single-item / contradictory cases; grading
      reports distribution, not only count; the vague case shifts distribution less than the
      specific case.
- [x] **Step 18** — flags expressed as A0-A4 tiers in a machine-writable store; promotion requires a
      committed green eval run (`git cat-file -e HEAD:`, since `git ls-files` exits 0 on a merely
      staged file); demotion written by the gate on a stage-attributed `blocked`, with refusals
      excluded so an unattended run cannot ratchet itself down; `auto_ship`/`auto_clean` capped at A2
      by a resolver that refuses rather than clamps; the Part VIII gap re-accepted in writing with an
      enforced expiry. Verified: 29 tests + 3 subtests across `scripts/test_autonomy_tier.py` and
      `scripts/test_autonomy_demotion.py`.
      **Amended:** "the gate asserts ... failing closed" → the Stop hook cannot precede an
      irreversible action, so pre-action deny is **Step 19**; "every workflow and pipeline stage" →
      scoped to the five pipeline legs.

Cross-cutting:
- [ ] No step's artifacts were committed directly to `main` (`git log --first-parent main` shows only
      merges for this goal's work).
- [ ] Every completed step's `Accepts` check was re-run by the Coordinator, not self-reported by a
      worker (plan §19 step 2).

## Evidence to update

- `plans/2026-07-27-native-agent-orchestration.md` — the source design. If a step's implementation
  deviates from it, amend the plan in the same commit; never let the two drift.
- New artifacts, by step: `ai/references/definition-of-done.md`, `plans/specs/TEMPLATE.md`,
  `ai/agents/executor-implement.md`, `scripts/lib/skill_lint.py`, `scripts/validate_skills.py`,
  `scripts/skill_lint_baseline.json`, `scripts/run_evals.py`,
  `scripts/resolve_customization.py`, `evals/cases/`, `evals/fixtures/`,
  `evals/collision-baseline.md`, `ai/skills/REMOVALS.md`, `ai/skills/manifest.csv`,
  `ai/skills/lensed-review/`, `ai/skills/using-my-skills/SKILL.md`,
  `.claude/workflows/orchestrate.js`
- Edited: `.claude/settings.json` + `ai/config/claude/settings.base.json` (keep identical **modulo
  `$HOME` path portability** — verified 2026-07-28 that the two differ by 3 hunks today because base
  is deliberately de-absolutized, and that `config-integrity.sh` contains zero references to
  `settings.base`; the real check is the `diff <(jq -S .) <(jq -S .)` command in the plan, not a
  byte-comparison and not that hook),
  `.claude/hooks/teammate-quality-gate.sh`, `.claude/hooks/session-init.sh`,
  `.claude/hooks/git-pipeline-gate.sh`, `.claude-atomic.yaml`, `setup.sh`,
  `ai/rules/agent-user-global.md`, `ai/skills/cap/` (`SKILL.md`, `references/schemas.md`, step files),
  `ai/skills/tmux-orchestrator/SKILL.md`, `git/hooks/pre-commit`
- `evals/results/` — gitignored runtime evidence. Eval **runs** that justify an autonomy promotion
  must be committed as a report, not left only in this directory (plan Part VIII: promotion requires
  evidence *in the repo*).
- `plans/progress.md` — chronological step completion. `plans/decisions.md` — decisions and root
  causes. `plans/active-context.md` — the `goal:`/`status:`/`focus:` pointer, required the moment
  this goal is marked `active` in `goals/00-index.md`.

## Stop and ask if

- **Before starting any step.** No step carries standing authorization; go-ahead for one step never
  extends to the next. Do not begin Step N+1 until Step N's `Accepts` are verified.
- **Decision 1 is unresolved** (Appendix B) — the frozen-spec path: per-worker
  `plans/specs/<label>.md` (recommended; required for concurrent workers) vs the single
  `plans/spec.md` fixed by `ai/rules/agent-user-global.md:140`. Step 3 cannot start without it, and
  it changes a standing user-global rule.
- **Decision 2 is unresolved** (Appendix B) — `/tech-lead`: re-enable and retrofit, or retire. Step 9's
  ledger entry depends on the answer. Note it is `"off"` at **both** user and project scope;
  `skillOverrides` merge per key, so removing only the project entry will not re-enable it.
- **Any autonomy tier would rise**, or any `.claude-atomic.yaml` pipeline flag or `hook-config.yaml`
  level would change. The plan forbids a pipeline self-edit escalating its own tier; that carve-out
  is never satisfied by a flag combination, only by direct confirmation in the moment.
- **`auto_ship` or `auto_clean` would run above A2** — refuse and surface. Blast radius caps the
  tier regardless of accumulated evidence.
- **A step would consolidate or retire a skill without a shim** that pins the existing output
  contract, or would touch a Claude Code built-in.
- **Step 10 would reduce the review surface but the Step 7 collision baseline was never committed** —
  without the baseline there is no way to show the consolidation helped.
- **A worker returns `null`, empty, or a schema-invalid result and the temptation is to proceed.**
  That is a failure, not a success (plan §24). Never mark an unverified return complete.
- **Any bounded loop would exceed its bound** (3 retries, 3 doubt cycles, 5 re-derivations) — the
  correct response is to decompose the artifact, never to raise the bound.
- **This goal stalls or exceeds ~6 sessions of work.** 18 steps is large for one goal; propose
  splitting at a natural dependency boundary — Steps 1-9 (foundations, evals, lifecycle) and Steps
  10-18 (consolidation, orchestrator, ladder) — rather than leaving one goal `active` indefinitely.
- **`git remote -v` does not show the expected remote**, or `gh auth status` resolves to anything
  other than the personal `arjaygg` account, before any push or PR.
- **Work would be committed on `main`.** Branch first; the pre-commit hook refuses it, and that
  refusal is correct.
