# 0013 — Deterministic model-routing and subagent fan-out enforcement

**Status:** Accepted (warn-only)
**Date:** 2026-07-26
**Goal:** `goals/2026-07-26-03-deterministic-model-routing-enforcement.md`

## Decision

Convert the prose-only model-tier and subagent-fan-out routing policy (documented in
`ai/skills/model-routing/SKILL.md` and `ai/rules/agent-user-global.md`) into mechanisms that
either hard-fail or warn on violation, split along a hard boundary:

- **Hard-enforced (fail-closed, `exit 1`):** every `.claude/agents/*.md` must declare a `model:`
  field set to one of `{haiku, sonnet, opus, fable, inherit}` — aliases only, dated model IDs
  rejected. Enforced by `check_agent_models()` in `.claude/hooks/config-integrity.sh`.
- **Warn-only (never denies):** two new `pre-tool-gate-v2.sh` sections —
  - Section 8: counts `agent(` call sites in a `Workflow` script's `tool_input.script`; warns
    `fan-out-exceeds-3` when count > 3 and confidently parsed, warns `fan-out-undecidable` when
    `parallel(`/`pipeline(` wraps a `.map(` chain or bare variable (runtime-dependent size).
  - Section 7b: flags `Agent` tool calls where an explicit `model` override looks mismatched to
    the prompt — trivial prompt pinned off-haiku, deep-reasoning prompt pinned to haiku. No-ops
    when `model` is unset (inherit), since the hook cannot see the resolved tier at PreToolUse
    time.
- **Structurally unenforceable, documented not solved:** main-loop model tier selection
  (`opusplan`/`sonnet`/etc. for the top-level session). Claude Code exposes no hook that can
  invoke `/model` or otherwise switch the main-loop model — this is stated directly in
  `model-routing/SKILL.md`'s new Enforcement section, with the reason.
- Resolved a live drift as part of this work: `.claude/settings.json` had `"model": "sonnet"`
  while `SKILL.md` documented `opusplan` as the recommended default. Changed the tracked settings
  file to `opusplan` to match the documented (and un-contradicted) policy.

## Why

The policy existed only as prose guidance with no enforcement, and had already drifted silently
once (`sonnet` vs the documented `opusplan` default) with no record of an intentional change. A
prose policy that isn't checked degrades to whatever the last accidental edit left in place. At
the same time, reliably judging "is this prompt trivial or deep-reasoning" or "how many agents
will this workflow script actually spawn at runtime" from static regex/keyword matching is not
achievable without false positives that could strand a legitimate session or degrade an agent's
actual job — so a hard deny at this stage would trade a real (if imperfect) heuristic for a
worse failure mode. The chosen split puts a hard fail only where the check is genuinely
deterministic (a fixed enum of 5 aliases), and keeps everything judgment-dependent in warn-only
mode until real session evidence justifies (or rules out) promotion to deny.

## Alternatives rejected

- **Hard-deny the new Workflow fan-out and Agent tier-mismatch gates immediately:** rejected —
  the goal's own non-goals explicitly forbid adding a hard block without a documented escape
  hatch and a prior dry-run/warn period, and reliable static analysis of arbitrary workflow
  scripts (to get an exact runtime fan-out count) is explicitly out of scope.
  Regex/keyword heuristics are a starting classifier, not a validated one.
- **Leave the `opusplan`/`sonnet` drift as two independently "correct" values and reconcile the
  docs to match the tracked settings instead:** rejected — no evidence anywhere (commit history,
  `plans/decisions.md`, `plans/active-context.md`) shows an intentional decision to abandon
  `opusplan`; the drift traces to `settings-symlink-guard.sh`'s known copy-back behavior
  (previously flagged in `plans/active-context.md`'s 2026-07-08 entry), not a policy change.
- **Skip the base-template (`ai/config/claude/settings.base.json`) entirely and only fix the
  tracked `.claude/settings.json`:** rejected once `scripts/` testing surfaced that the template
  is asserted byte-equal to the tracked settings file by
  `test_phase0_boundary.py::test_claude_base_template_matches_sanitized_tracked_settings` — leaving
  it unmirrored would silently reintroduce the exact kind of undocumented drift this ADR exists to
  close.

## Consequences

- `.claude/agents/*.md` model frontmatter is now a checked invariant, not a convention — any new
  agent file must declare a valid `model:` alias or `config-integrity.sh` fails the tree.
- Both new gate sections are live in warn-only mode; expect stderr warnings to start appearing for
  >3-agent `Workflow` scripts and mismatched `Agent` tier pins. This is intentional signal
  collection, not noise to suppress.
- Main-loop tier selection remains a standing, explicitly-documented gap: switching `opusplan` vs
  `sonnet` vs `fable` for the top-level session is, and will remain, a manual `/model` action —
  no hook-based enforcement is possible here without a Claude Code platform change.
- Promotion of either warn-only gate to `deny` is an explicit future decision, gated on collecting
  real session fire/no-fire evidence first (Step 6 of the originating goal). This ADR does not
  authorize that promotion.

## Related

- `plans/decisions.md` ADL-020 (opusplan/sonnet drift), ADL-021 (agent model hard-fail),
  ADL-022 (warn-only gates + fire/no-fire evidence), ADL-023 (base-template drift fix).
- `ai/skills/model-routing/SKILL.md` — Enforcement section.
- `.claude/hooks/config-integrity.sh`, `.claude/hooks/pre-tool-gate-v2.sh`.
