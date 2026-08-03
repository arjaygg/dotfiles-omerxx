---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — factory-target-rubric

<intent-contract>
Produce a compact, decision-ready rubric derived only from the supplied Agent Factory target. The
Coordinator must be able to score verified harness evidence against it without rereading the source.
</intent-contract>

## Task

Read `/Users/axos-agallentes/git/agent-harness/docs/The_Agent_Factory.md`. Extract the target maturity
model, autonomy model, operating-loop capabilities, governance principles, platform capabilities,
and horizon outcomes. Convert each into an observable criterion, evidence that would prove it,
and disconfirming evidence. Flag ambiguities or contradictions in the target itself.

## Files

- Read-only target: `/Users/axos-agallentes/git/agent-harness/docs/The_Agent_Factory.md`
- Frozen spec: `plans/specs/factory-target-rubric.md`
- Do not inspect repository `docs/` or existing `plans/` as harness evidence.

## Acceptance

- Returns a matrix with criterion, target level, proof required, and failure signal.
- Separates declared ambition from current-state claims made by the target document.
- Defines a repeatable maturity-scoring method rather than a prose impression.
- Lists target ambiguities that the final plan must resolve explicitly.
- Returns only compact findings and exact source-line references; no raw file dump.

## Constraints

- Read-only: do not edit any file.
- Run Serena `initial_instructions` and LeanCtx task scoping before file access.
- Use exact/raw evidence for quotes, counts, and line references.
- Do not use repo docs/plans to infer current harness behavior.
- Do not spawn nested subagents.

## Spec Change Log

- 2026-08-03: Initial frozen scope.

## Review Triage Log

- None.
