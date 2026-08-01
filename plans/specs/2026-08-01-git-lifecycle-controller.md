---
status: draft
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — git-lifecycle-controller

<intent-contract>
Build the shared, deterministic decision engine that tells every agent when a
stack, commit, push, PR, CI wait, merge enrollment, sync, or cleanup is due.
The controller must combine an agent-declared semantic work-unit boundary with
fresh git evidence, remain read-only while inspecting, and fail closed whenever
evidence is incomplete or contradictory. This step does not execute lifecycle
actions or change autonomy policy.
</intent-contract>

## Task

Add a dependency-free Python CLI that stores versioned run manifests under the
shared git directory and computes exactly one next lifecycle action. It must see
staged, unstaged, untracked, conflicted, and active-operation state rather than
using the current staged-only atomic detector. Add hermetic behavioral and
decision-matrix tests.

## Files

- `scripts/ai/git_lifecycle.py` (new)
- `scripts/test_git_lifecycle.py` (new)
- `scripts/test_executable_bits.py`
- `plans/specs/2026-08-01-git-lifecycle-controller.md`

## Acceptance

1. CLI commands:
   - `start`: create a run with task, base branch/SHA, intended branch, owned
     paths, worktree, and one initial work unit.
   - `ready`: mark the work unit semantically complete only with a conventional
     subject, meaningful body, zero open tasks, and one or more passing
     validation evidence entries.
   - `record`: record PR/CI/merge/sync facts with their source and exact SHA.
   - `inspect`: perform no writes and emit one JSON action plus reason/evidence.
   - `halt`: append a durable `done` or `blocked` terminal status.
2. State lives at
   `<git-common-dir>/agent-lifecycle/runs/<run-id>.json`; audit events append to
   `<git-common-dir>/agent-lifecycle/audit.jsonl`. Writes use a repository-wide
   lock and atomic replace. Schema version and timestamps are explicit.
3. Branch/path input is validated: branch names use the repository's supported
   prefixes; owned paths are normalized repository-relative paths and reject
   absolute paths, `..`, `.git`, duplicates, and paths outside the worktree.
4. `inspect` detects staged, unstaged, untracked, conflicts, merge/rebase/
   cherry-pick/revert/bisect operations, current/upstream/base SHAs, and every
   changed path. It never invokes network commands.
5. Decision priority is deterministic:
   `blocked` invariant → `create_stack` → `editing`/`awaiting_work` →
   `commit` → `push` → `open_pr` → `wait_ci` → `merge_eligible` →
   `sync` → `cleanup` → `done`.
   A commit is due only when the semantic work unit is ready, all evidence
   passes, its owned diff is non-empty, no foreign path is dirty, no conflict or
   git operation is active, and the current branch is not trunk.
6. Remote facts are accepted only when keyed to the current exact head SHA.
   Missing, stale, abbreviated, contradictory, or non-authoritative facts yield
   `wait_ci` or `blocked`, never `merge_eligible`.
7. Cleanup is due only after an exact remote merge receipt, successful sync
   receipt, and proof that the worktree is clean. Child-stack and active-session
   enforcement are deferred to the execution adapter and must be surfaced as
   required evidence, not assumed.
8. Re-running `start`, `ready`, `record`, or `halt` with the same idempotency key
   produces no duplicate transition or audit event. Concurrent writers cannot
   corrupt state.
9. Tests use temporary git repositories and cover the complete decision matrix,
   dirty-state combinations, path escapes, stale SHA, idempotency, lock
   contention, shared state across linked worktrees, and inspect read-only
   behavior. No test accesses the network.
10. `inspect` completes under 500 ms at p95 in the current repository, the new
    script is executable, all new/focused tests pass, and `git diff --check`
    passes.

## Constraints

- Branch: `feature/git-lifecycle-controller`, stacked on
  `feature/agentic-git-lifecycle`.
- Work only under
  `/Users/axos-agallentes/.dotfiles/.trees/git-lifecycle-controller`.
- Do not modify hooks, skills, `.claude-atomic.yaml`, remote settings, or existing
  action scripts in this step.
- `inspect` must be pure/read-only; lifecycle mutations belong to later adapters.
- Use Python standard library only.
- Do not spawn subagents.
- Commit only through `~/.dotfiles/scripts/ai/commit.sh` after acceptance passes.

## Spec Change Log

- 2026-08-01: Initial controller contract created from the approved lifecycle
  plan and the verified safety-foundation branch.
- 2026-08-01: Corrective review scope added: registered linked-worktree
  transitions, repeatable fingerprint-bound work units, per-commit ownership
  history, strict validation evidence, durable audit reconciliation, explicit
  receipts, duplicate-run refusal, normalized failures, and a phased decision
  engine.

## Review Triage Log

- 2026-08-01: Coordinator and independent review rejected the first draft.
  Accepted all ten findings for corrective implementation without weakening
  tests or expanding the frozen four-file scope.
- 2026-08-01: Corrective implementation verified with the focused lifecycle
  suites, inspect p95 below 500 ms, a materially smaller controller, and a
  six-line/CC3 phased `decide` function.
