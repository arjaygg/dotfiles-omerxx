---
status: draft
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — lifecycle-safety-foundation

<intent-contract>
Make every existing git-lifecycle entrypoint fail closed before the new autonomous
controller is introduced. Remove known bypasses, align the CI producer/consumer
contract, and preserve the current public command paths through one canonical
implementation. This change must not enable autonomous merge or modify remote
repository settings.
</intent-contract>

## Task

Harden the existing stack creation, checkpoint, CI-watch, Stop-gate, Cursor commit
guard, and stack-ship paths. Add behavioral regression tests for each corrected
contract. Keep the implementation focused on safety prerequisites for the later
shared lifecycle controller.

## Files

- `.claude/scripts/stack-ship.sh`
- `scripts/stack-ship.sh`
- `ai/skills/ci-watch/SKILL.md`
- `scripts/ai/pipeline-status.sh`
- `scripts/ai/checkpoint.sh`
- `.claude/hooks/task-gate.sh`
- `.claude/scripts/pr-stack/create-stack.sh`
- `.cursor/hooks/before-shell-git-commit.sh`
- `.cursor/hooks.json`
- `scripts/test_pipeline_status.py`
- `scripts/test_stack_ship_non_interactive.py`
- `scripts/test_lifecycle_safety_foundation.py` (new)
- `plans/specs/2026-08-01-lifecycle-safety-foundation.md`

## Acceptance

1. `stack-ship` refuses draft, closed, conflicting, stale-head, missing-required-check,
   pending-check, failed-check, and unknown-check PRs. It verifies the PR head OID
   against the local branch and uses server auto-merge with
   `--match-head-commit`; it never uses `--admin` and never continues after a failed
   dependent merge. Multi-branch shipment remains confirmation-only and is not
   automated by this change.
2. `scripts/stack-ship.sh` delegates to the canonical
   `.claude/scripts/stack-ship.sh`; no second merge algorithm remains.
3. `ci-watch` writes `**SHA:** <full SHA>` and no longer triggers deployment.
   `pipeline-status.sh` requires a non-empty exact SHA before emitting
   `merge_due`.
4. `checkpoint.sh` never runs `git add .`, raw `git commit`, or `--no-verify`.
   It requires explicit paths, stages only those paths, and commits through
   `scripts/ai/commit.sh`.
5. `task-gate.sh` emits the valid Stop-hook
   `{"decision":"block","reason":"..."}` response at block level.
6. `create-stack.sh` never copies `.env`, edits `.gitignore`, creates an initial
   raw commit, deletes unrelated metadata refs, or runs broad repository repair.
   It refuses creation when `.trees/` is not already ignored.
7. Cursor's raw-commit guard parses command and cwd correctly and is registered
   in `.cursor/hooks.json`.
8. Behavioral tests cover every refusal and compatibility path above using
   temporary repositories and stubbed `gh`; no test invokes the real network.
9. Existing focused lifecycle tests plus the new suite pass, modified shell files
   pass `bash -n`, and JSON files parse.

## Constraints

- Branch: `feature/agentic-git-lifecycle`.
- Work only under
  `/Users/axos-agallentes/.dotfiles/.trees/agentic-git-lifecycle`.
- Do not touch the dirty main checkout.
- Do not change `.claude-atomic.yaml`, autonomy tiers, branch protection, GitHub
  rulesets, or enable automatic merge.
- Do not use `--admin`, force push, destructive reset, or hook bypass flags.
- Perform all implementation yourself; do not spawn subagents.
- Commit only through `~/.dotfiles/scripts/ai/commit.sh` after all acceptance
  checks pass.

## Spec Change Log

- 2026-08-01: Initial safety-foundation contract created from the approved
  agentic lifecycle plan.

## Review Triage Log

- None yet.
