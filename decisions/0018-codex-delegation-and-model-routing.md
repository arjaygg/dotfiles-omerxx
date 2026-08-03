# 0018 — Codex delegation policy and subagent model-tier enforcement

**Status:** Accepted (hard-deny on two checks, warn-only on three)
**Date:** 2026-08-03
**Goal:** `goals/2026-08-03-06-codex-delegation-routing.md`
**Extends:** `decisions/0013-deterministic-model-routing-enforcement.md` (same hard/warn/unenforceable
split, applied to Codex)
**Consistent with:** `decisions/0014-fixed-opus-coordinator-override.md` (a fixed coordinator plus a
cheap default worker tier — the same routing shape, expressed in Codex's model family)

## Decision

Extend the model-routing and delegation policy to Codex CLI along three lines:

- **Documentation, not duplication.** `ai/rules/codex-delegation.md` carries only the Codex delta —
  context admission, delegation triggers, the ≤30-line return contract, the escalation ladder,
  context hygiene. Roles (Coordinator/Executor), the `plans/specs/<label>.md` path, anti-nesting, and
  fresh-vs-fork stay in `ai/rules/agent-user-global.md`, which is already Codex's
  `model_instructions_file`. The Codex tier table goes into `ai/skills/model-routing/SKILL.md`
  beside the existing Claude and Cursor tables, not into a fourth file.
- **Tiers.** `gpt-5.6-sol` coordinator (pinned in `~/.codex/config.toml`), `gpt-5.6-terra` standard
  worker, `gpt-5.6-luna` default cheap worker, `gpt-5.4-mini` pure extraction, `gpt-5.5` second
  opinion, `gpt-5.6-sol` at `xhigh`/`max` as evidence-gated escalation. Selection rule: the cheapest
  tier whose failure mode is machine-detectable and whose task needs no judgement absent from the
  spec; step up exactly one tier on failure.
- **Enforcement.** New `.codex/hooks/pre-agent-gate.sh`, wired as a second `PreToolUse` entry in
  `.codex/hooks.json`:
  - **Hard deny (`exit 2`):** subagent `model` outside the six-slug enum. Deterministic — a fixed
    set, mirroring `check_agent_models()` in `.claude/hooks/config-integrity.sh`.
  - **Hard deny (`exit 2`):** a `plans/specs/*.md` path named in the prompt that does not exist on
    disk. Deterministic — a filesystem fact.
  - **Warn:** no explicit `model` (silently inherits the most expensive tier); no spec referenced at
    all; more than 3 spawns inside a rolling 60s window.
  - **Fail open** on empty input, malformed JSON, or missing `jq`.

## Why

The Codex side had no tier table anywhere in the harness (`grep` for `gpt-5.6-*` across `ai/` and
`.codex/` returned only vendored `.venv` matches) and no agent or model gate at all — `.codex/hooks/`
covered context routing and bash safety only. Meanwhile the coordinator was already pinned to
`gpt-5.6-sol` with no recorded rationale, which is precisely the undocumented-drift state 0013 and
0014 exist to prevent on the Claude side.

The hard/warn boundary is inherited from 0013 rather than re-litigated, because the same reasoning
holds: hard-fail only where the check has deterministic ground truth, and keep everything
judgement-dependent visible-but-non-blocking until session evidence justifies promotion. Two checks
here clear that bar (a fixed enum; a file that exists or does not). Three do not:

- **Fan-out** is a rolling-window proxy. `PreToolUse` sees spawns and never completions, so the hook
  cannot know how many agents are actually concurrent. Denying on a proxy would strand legitimate
  sequential work. Same conclusion as ADL-022, reached for a different reason (missing completion
  signal rather than unparseable script text).
- **Tier-vs-difficulty** was deliberately not ported from Claude's §7b. It is keyword matching, not
  classification, and Codex has no fire/no-fire evidence base to justify importing its false-positive
  surface.
- **The return contract** has no observation point — no hook sees a subagent's return payload.

Duplication was the other live risk. A first pass at this work restated three rules that
`agent-user-global.md` already carries, against that file's own § File And Tool Discipline. Policy
restated in two places drifts in one of them.

## Alternatives rejected

- **A standalone Codex rule file carrying the full policy including roles, spec path, and
  anti-nesting:** rejected — duplicates `agent-user-global.md`, which Codex already loads via
  `model_instructions_file`. Two copies drift; the harness has been bitten by this before (ADL-020,
  ADL-023).
- **A fourth tier table in the new rule file rather than a Codex section in `model-routing/SKILL.md`:**
  rejected — the skill already holds Claude and Cursor tables and is the file the router surfaces on
  tier questions. Splitting tiers across files would leave the skill silently wrong for one client.
- **Hard-denying the fan-out and tier-unset checks immediately:** rejected — neither has
  deterministic ground truth at `PreToolUse`. 0013's non-goal against denying on heuristics applies
  unchanged.
- **Porting the §7b keyword tier-mismatch heuristic to Codex:** rejected — see Non-goals in the goal
  doc. No evidence base, and the heuristic's own ADR keeps it warn-only on Claude.
- **Installing the gate machine-wide in `~/.codex/hooks.json`:** rejected for this change —
  `~/.codex/` is outside the repo's tracked surface. `.dotfiles/.codex/hooks.json` is project-scoped
  and reviewable; machine-wide installation is a separate, explicit decision.
- **Inventing an agent-definition schema for `~/.codex/agents/`:** rejected — `agents_dir` appears in
  the 0.146.0 binary but the directory does not exist and no schema could be verified. Prescribing
  behaviour and a per-call `model` argument is what the evidence supports.

## Consequences

- A Codex subagent spawn on an unrecognised model slug now fails closed. **When OpenAI ships a new
  tier, the enum in `pre-agent-gate.sh` and the table in `model-routing/SKILL.md` must be updated in
  the same commit, or valid spawns will be denied.** This is the intended failure direction, but it
  is a real maintenance obligation.
- Editing the hook or its wiring invalidates the `trusted_hash` recorded in `config.toml`
  `[hooks.state]`. Codex will re-prompt for hook trust on the next session after this lands.
- `.dotfiles/.codex/hooks.json` is project-scoped: the gate applies when Codex runs with this repo as
  cwd, not machine-wide. Global coverage requires the same `PreToolUse` entry in `~/.codex/hooks.json`.
- The gate's field extractors are best-effort across Codex payload shapes. A Codex upgrade that
  changes the subagent payload will cause the gate to fail open silently — the fixtures in the goal
  doc's Evidence section must be rerun after a version bump.
- Main-loop tier selection remains manual on Codex exactly as on Claude: the coordinator model is a
  `config.toml` value, and no hook can change a session's own model. 0013's documented gap is
  unchanged, not closed.
- No warn-only check is promoted to deny by this ADR. Promotion requires a real session's fire/no-fire
  evidence and a separate decision, mirroring Goal 03 Step 6.

## Related

- `goals/2026-07-26-03-deterministic-model-routing-enforcement.md` — the Claude-side original.
- `goals/2026-07-28-05-native-agent-orchestration-harness.md` — orchestration harness, anti-nesting
  enforcement, autonomy ladder.
- `ai/rules/codex-delegation.md`, `ai/skills/model-routing/SKILL.md` § Codex equivalent / Enforcement.
- `.codex/hooks/pre-agent-gate.sh`, `.codex/hooks.json`.
