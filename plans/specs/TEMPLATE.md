---
status: draft
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — <label>

One spec per worker. Path: `plans/specs/<label>.md` — never `plans/spec.md`, never
`plans/active-context.md`. `<label>` should match the worker's branch/task label so
concurrent workers never collide on the same file.

<intent-contract>
State the outcome the worker must produce, in terms the Coordinator can verify without
re-deriving the work: the task, exact files in scope, acceptance criteria, and constraints.
This region is the contract — if the worker's result doesn't satisfy it, the spec (not the
worker's judgment) is what gets amended.
</intent-contract>

## Task

<what the worker must do, and why>

## Files

<exact files/paths in scope — the worker should not touch anything outside this list without
flagging it back to the Coordinator>

## Acceptance

<concrete, checkable criteria — mirror the goal/plan doc's `**Accepts:**` clause if one exists>

## Constraints

<anti-nesting reminder, branch/worktree rules, commit discipline, anything the worker must not do>

## Spec Change Log

<append-only log of amendments to this spec after the worker started, each with a date and
the reason — e.g. a §6 doubt-cycle finding or a §24 review-triage result that changed scope>

## Review Triage Log

<append-only log of review findings against the worker's output and their disposition —
fixed / deferred / rejected — so a re-reviewer doesn't re-litigate settled findings>
