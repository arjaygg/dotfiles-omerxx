---
status: draft
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — claude-lifecycle-adapter

<intent-contract>
Connect Claude Code to the shared lifecycle controller and execute only the
reversible, policy-authorized transitions: exact-base stack creation, canonical
commit, push, PR creation/update, and CI observation. Pre-write and Stop hooks
must make lifecycle use unavoidable in opted-in repositories. Merge, sync, and
cleanup remain fail-closed for the next bounded-merge stack branch.
</intent-contract>

## Task

Add a Claude-specific session adapter, hook integration, and deterministic
executor around `scripts/ai/git_lifecycle.py`. Reuse the canonical stack and
commit scripts. Preserve the old pipeline gate only as fallback when no
lifecycle run is bound to the Claude session.

## Files

- `scripts/ai/lifecycle_adapter.py` (new)
- `scripts/ai/git_lifecycle.py`
- `scripts/ai/autonomy-tier.sh`
- `scripts/test_lifecycle_adapter.py` (new)
- `scripts/test_git_lifecycle.py`
- `scripts/test_autonomy_tier.py`
- `scripts/test_executable_bits.py`
- `.claude/scripts/pr-stack/create-stack.sh`
- `scripts/test_lifecycle_safety_foundation.py`
- `.claude/hooks/lifecycle-hook.sh` (new)
- `.claude/hooks/stop.sh`
- `.claude/hooks/sessionstart.sh`
- `.claude/hooks/userpromptsubmit.sh`
- `ai/config/claude/settings.base.json`
- `.claude-atomic.yaml`
- `ai/skills/auto-ship/SKILL.md`
- `ai/rules/hyper-atomic-commits.md`
- `plans/specs/2026-08-01-claude-lifecycle-adapter.md`

## Acceptance

1. `lifecycle_adapter.py` exposes `start`, `ready`, `next-unit`, `status`,
   `tick`, `watch`, and `hook`. `start` binds the run to the effective Claude
   session in the shared git directory; every command is idempotent.
2. Repositories opt in with an explicit lifecycle block in
   `.claude-atomic.yaml`. Outside opted-in repositories every hook is a silent
   no-op.
3. A standalone Claude PreToolUse hook for `Edit|Write|MultiEdit`:
   - denies a tracked write when no run is bound;
   - denies paths outside the run's owned boundary;
   - permits only `editing` or `awaiting_work`;
   - denies writes after readiness/commit until the agent refreshes readiness or
     starts the next work unit;
   - uses the exact Claude deny JSON and hard-block prefix.
4. UserPromptSubmit and SessionStart inject concise lifecycle status/instructions.
   Stop invokes `tick` after `task-gate`; a bound run supersedes the legacy
   `git-pipeline-gate`, while an unbound session retains the legacy fallback.
5. Each `tick` re-inspects fresh controller state and executes at most one
   mutating transition at a time, then re-inspects:
   - `create_stack`: canonical stack creation pinned to the controller's exact
     base SHA;
   - `commit`: stage only controller-approved paths, run
     `validate-changeset.sh`, then `commit.sh` with the approved subject/body;
   - `push`: ordinary upstream push, never force;
   - `open_pr`: reuse an exact-head existing PR or invoke canonical `stack pr`,
     then record the exact PR fact.
6. `auto_stack` becomes a first-class reversible autonomy stage. It and
   `auto_commit`, `auto_push`, and `auto_pr` require effective A2 or higher.
   Resolver failure or a lower tier yields `approval_required`; it never executes
   optimistically. Action failure appends adapter audit evidence and writes only
   the existing downward demotion marker for that stage.
7. `wait_ci` performs exact-head GitHub reconciliation using required PR checks.
   Missing required checks, pending, failed, unknown, stale, and malformed data
   never record passing CI. A single background watcher per run/SHA may poll and
   record a terminal result without keeping the Stop hook open.
8. `merge_eligible`, `sync`, and `cleanup` are never executed in this branch.
   Stop returns a clear block/approval result and does not call `stack-ship`,
   merge, delete, or clean.
9. Stack creation accepts `--base-sha`, verifies it is the exact commit and an
   ancestor of the named base, and creates the linked worktree from that SHA
   even if the base branch moves.
10. Adapter actions and hook results are append-audited under the git common
    lifecycle directory without command strings, tokens, or environment values.
    A crash after any external action is recoverable by fresh inspection.
11. `ai/config/claude/settings.base.json` is the canonical settings edit. Hook
    paths use portable `$HOME/.dotfiles` shell form. Existing dispatchers keep
    first-block-wins semantics and valid JSON output.
12. Tests use temporary repositories and stubbed `git`/`gh`/stack commands;
    they cover all action/tier/hook/CI branches, exact path staging, crash
    recovery, duplicate watcher suppression, legacy fallback, malformed input,
    settings wiring, and shell syntax. No test accesses the network.
13. All focused lifecycle, hook, autonomy, syntax, JSON, and executable-bit
    tests pass; `git diff --check` passes.

## Constraints

- Branch: `feature/claude-lifecycle-adapter`, stacked on
  `feature/git-lifecycle-controller`.
- Work only under
  `/Users/axos-agallentes/.dotfiles/.trees/claude-lifecycle-adapter`.
- Do not modify remote settings or enable merge/cleanup.
- Do not add dependencies or duplicate stack/commit algorithms.
- Runtime code must never edit `.claude-atomic.yaml`, hook config, or tracked
  settings; it may only append untracked audit data and create demotion markers.
- Perform all implementation yourself; do not spawn subagents.
- Commit only through `~/.dotfiles/scripts/ai/commit.sh` after acceptance passes.

## Spec Change Log

- 2026-08-01: Initial Claude adapter contract created after the shared
  controller passed coordinator verification.

## Review Triage Log

- None yet.
