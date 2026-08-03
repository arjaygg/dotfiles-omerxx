---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — harness-runtime-audit

<intent-contract>
Produce reproducible runtime-health evidence for the harness, separating green tests from actual
artifact/behavior verification and finding broken, stale, conflicting, or dead mechanisms.
</intent-contract>

## Task

Audit executable health from the worktree. Discover the supported validation entrypoints from code
and config rather than narrative docs. Run a bounded representative suite covering configuration
generation/topology, hook wiring and schemas, policy/eval gates, setup/symlink integrity, agent and
skill manifests, orchestration/lifecycle adapters, and cross-client parity. Inspect live symlink
targets and generated-vs-source drift without changing them. Investigate failures far enough to
classify root cause, affected capability, and whether the failure is current, flaky, or obsolete.

## Files

- Worktree root: `/Users/axos-agallentes/.dotfiles/.trees/agent-factory-gap-plan`
- In scope: executable files/configs under `scripts/`, `.claude/hooks/`, `.claude/scripts/`,
  `ai/`, `evals/`, `setup.sh`, client configs, test files, and live symlink metadata under `$HOME`.
- Excluded as evidence: `docs/`, `decisions/`, `goals/`, and all existing `plans/` except this spec.

## Acceptance

- Returns exact commands, exit status, concise result counts, and affected capability.
- Uses at least two independent signals before labeling a mechanism broken or healthy.
- Verifies claimed artifacts/activation, not just command exit 0.
- Identifies stale tests, false-green checks, conflicting gates, unreachable paths, and live/source drift.
- Separates confirmed findings from hypotheses and lists checks not run because of cost or risk.
- Makes no edits and returns compact results; do not paste full logs.

## Constraints

- Read-only and non-destructive: do not edit files, install software, mutate live config, push, or open PRs.
- Run Serena `initial_instructions` and LeanCtx task scoping before file access.
- Use LeanCtx/Serena for discovery and compressed commands; re-run exact claims through `lean-ctx raw`.
- Do not treat narrative docs/plans as evidence.
- Do not spawn nested subagents.

## Spec Change Log

- 2026-08-03: Initial frozen scope.

## Review Triage Log

- None.
