# Goal 03 — Deterministically enforce model-tier and subagent-fan-out routing

## Objective

Convert the currently prose-only routing policy — "frontier models (Fable/Opus) for deep reasoning,
low-cost models (Haiku) for trivial work; use subagents to contain context; never exceed 3 agents in
a workflow" — into mechanisms that either hard-block or statically fail on violation, and explicitly
document which parts of that policy are structurally unenforceable in Claude Code.

## Why

The policy exists today only as guidance in `ai/skills/model-routing/SKILL.md` and
`ai/rules/agent-user-global.md`. Guidance is advisory: nothing fails when a subagent runs on the
wrong tier, when a `.claude/agents/*.md` file omits `model:` entirely, or when a workflow fans out
past three agents. The repo already has the enforcement surface to fix most of this
(`pre-tool-gate-v2.sh` for PreToolUse denials, `config-integrity.sh` for static config checks), so
the gap is unbuilt plumbing, not a missing capability.

There is also live drift the policy text does not reflect: `SKILL.md` documents
`model: "opusplan"` as the recommended default, but `.claude/settings.json:105` actually sets
`"model": "sonnet"`. Either the setting or the doc is wrong, and nothing currently detects it.

One boundary must stay stated rather than solved: **Claude Code exposes no hook that can switch the
main-loop model.** No `UserPromptSubmit` or `PreToolUse` hook can call `/model`. Main-session tier
selection is therefore permanently advisory (injected suggestion at best); only subagent and
workflow routing can be made deterministic. Any goal that claims to "enforce model routing" without
saying this is overpromising.

## Current state

Verified on `main` at `dca36bf`:

- `.claude/settings.json:105` → `"model": "sonnet"`; `:462` → `"advisorModel": "fable"`.
- 3 of 11 agent definitions have **no** `model:` frontmatter: `cicd-audit.md`, `cicd-monitor.md`,
  `cicd-review.md`.
- `.claude/agents/mcp_config_manager.md` pins `model: claude-3-5-sonnet-20241022` — a stale,
  deprecated model ID rather than an alias.
- Remaining agents are tiered: `haiku` (`cicd-auto-retry`, `claude-code-review-agent`,
  `go-build-resolver`), `sonnet` (`performance-optimizer`), `opus` (`database-reviewer`,
  `security-reviewer`, `silent-failure-hunter`).
- `pre-tool-gate-v2.sh` (911 lines) matcher is `Bash|Read|Edit|Write|MultiEdit|Grep|Glob|Agent` —
  **`Workflow` is not matched at all**, so no workflow-shaped call can currently be gated.
- `pre-tool-gate-v2.sh` §7 ("Agent — parallelism check") already inspects `Agent` calls and emits a
  `HINT`, i.e. the inspection point exists but only advises.
- `config-integrity.sh` is 60 lines and does not inspect `.claude/agents/*.md`.
- `advisor-escalate.py`/`.sh` already implement the recurrence-based escalation nudge; that layer is
  done and is not part of this goal.
- `goals/` exists with `00-index.md`, goals 01 and 02 both Completed. There is **no**
  `scripts/validate_goals.py` in this repo, so goal validation is manual here.

## Non-goals

- Do not attempt to switch the main-loop model from a hook — it is not possible; document the
  boundary instead of building a workaround.
- Do not modify `advisor-escalate.py`/`.sh` behavior; the advisor backstop is out of scope.
- Do not add a hard block that can strand a session (e.g. denying every `Agent` call lacking
  `model`) without a documented escape hatch and a dry-run/warn period first.
- Do not attempt reliable static analysis of arbitrary inline workflow scripts; cap enforcement to
  regex-detectable common shapes plus an explicit warn for undecidable cases.
- Do not restructure `ai/skills/model-routing/SKILL.md` beyond correcting the drift this goal
  uncovers and adding an "enforcement" section.
- Do not change any existing hard-deny, permission default, or symlink target.

## Steps

1. Resolve the `opusplan` vs `sonnet` drift: decide which is intended, then make
   `.claude/settings.json` and `ai/skills/model-routing/SKILL.md` agree. Record the decision in
   `plans/decisions.md`.
2. Assign explicit `model:` frontmatter to `cicd-audit.md`, `cicd-monitor.md`, and `cicd-review.md`
   using the tier table in `ai/skills/model-routing/SKILL.md`, and replace
   `mcp_config_manager.md`'s pinned `claude-3-5-sonnet-20241022` with a supported alias.
3. Extend `config-integrity.sh` to fail when any `.claude/agents/*.md` lacks a `model:` field or
   sets a value outside `{haiku, sonnet, opus, fable, inherit}` (aliases only — reject raw dated
   model IDs, which is what caught step 2's case).
4. Add `Workflow` to the `pre-tool-gate-v2.sh` matcher and add a section that counts `agent(`
   call sites plus `parallel([...])` / `pipeline(` arity in the submitted script; **warn** when the
   count exceeds 3 and the shape is confidently parsed, and warn-only (never deny) when the shape is
   undecidable.
5. Add a `pre-tool-gate-v2.sh` section for `Agent` that flags a tier mismatch: a call whose prompt
   matches a trivial-work pattern (short, imperative lookup/format/rename verbs, no
   design/why/root-cause keywords) but does not route to `haiku`, and conversely a deep-reasoning
   prompt routed to `haiku`.
6. Run both new gate sections in warn mode and collect at least one session's worth of real
   fire/no-fire evidence before proposing any promotion to `deny`. Promotion is a separate
   user-approved decision, not part of this goal's execution.
7. Add an "Enforcement" section to `ai/skills/model-routing/SKILL.md` mapping each policy clause to
   its actual mechanism and marking main-loop tier selection as advisory-only, with the reason.
8. Run `.claude/hooks/hook-integration-test.sh` and the repo `scripts/` test suite; confirm no
   existing hook regressed.

## Acceptance criteria

- Every `.claude/agents/*.md` file has an explicit `model:` set to a supported alias; no dated model
  IDs remain.
- `config-integrity.sh` exits non-zero on a deliberately introduced missing/invalid agent `model:`
  field, and zero on the clean tree — both demonstrated.
- `pre-tool-gate-v2.sh` matches `Workflow`, and a >3-agent workflow script produces a warning in a
  recorded test invocation; an undecidable script produces the undecidable-shape warning, not a
  denial.
- An `Agent` call with a trivial prompt on a non-`haiku` tier produces the tier-mismatch warning in
  a recorded test invocation.
- `.claude/settings.json` and `ai/skills/model-routing/SKILL.md` agree on the default model, with
  the choice recorded in `plans/decisions.md`.
- `ai/skills/model-routing/SKILL.md` states plainly that main-loop tier selection cannot be
  hook-enforced and explains why.
- `hook-integration-test.sh` passes; no previously passing test newly fails.
- No gate section is promoted from warn to deny within this goal.

## Evidence to update

- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md` (opusplan-vs-sonnet decision; warn-before-deny decision)
- `goals/00-index.md` (status transition)
- `.claude/settings.json`, `.claude/agents/*.md`
- `.claude/hooks/pre-tool-gate-v2.sh`, `.claude/hooks/config-integrity.sh`
- `ai/skills/model-routing/SKILL.md`
- `decisions/NNNN-deterministic-model-routing-enforcement.md` (durable ADR, once the warn→deny
  policy is settled)
- Recorded hook fire/no-fire outputs and `hook-integration-test.sh` results

## Stop and ask if

- Any new gate section would need to `deny` (exit 2) rather than warn in order to be useful — that
  changes session-blocking behavior and needs explicit approval.
- The `opusplan` vs `sonnet` drift turns out to be intentional for a reason not recorded in the repo.
- Reliable workflow fan-out counting proves to require parsing arbitrary JS rather than matching
  common shapes — that is a scope change, not a harder version of step 4.
- Enforcing a Haiku floor on trivial subagent work would degrade an existing agent's actual job
  (e.g. a `cicd-*` agent whose complexity genuinely varies).
- The work starts drifting toward the broader primitive/skill audit deferred by Goal 01.
