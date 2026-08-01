---
status: draft
retry_count: 1
doubt_cycle_iteration: 0
review_loop_iteration: 1
followup_review_recommended: true
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
- `.claude/scripts/pr-stack/create-pr.sh`
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
14. The hook bridge exposes enabled/disabled/error tri-state. Missing, crashing,
    or nonzero adapter execution in an opted-in repository fails closed; only
    explicit non-repo/disabled and Stop `lifecycle_bound:false` fall back silently.
15. A per-run action lock serializes fresh inspect, state reload, action, and
    post-inspect. Commit performs a post-stage CAS over HEAD, action, ready paths,
    and ready content fingerprint; duplicate ticks neither duplicate nor demote.
16. PR/CI facts prove current repository owner, intended head/base branch, exact
    SHA, and open non-draft state. Passing checks require a second identical PR
    observation, and command/status inconsistencies record unknown.
17. Push validates one matching origin fetch/push URL and uses only explicit
    `--set-upstream origin HEAD:refs/heads/<validated-branch>` without force or
    inherited refspec behavior.
18. Stop allows detached CI watching immediately. Merge/sync/cleanup defer with
    one durable block per run/action/head/session, then allow; editing and
    unauthorized reversible actions continue blocking.
19. Watchers use separate spawn and execution locks, require a child-ready
    handshake, bound default polls, command timeouts, and bounded backoff.
20. Stack creation supports adapter-required `--strict`; Charcoal tracking
    failure is nonzero so an untracked stack cannot advance controller state.
21. Start serializes binding precheck, controller start, and persistence. A new
    run whose binding cannot persist is durably halted blocked.
22. Canonical PR creation scopes `GH_TOKEN` only to `gh`; git push relies on its
    configured credential helper and never receives that token.
23. Adapter audit append is locked, partial-write safe, no-follow regular-file
    mode 0600, retry-idempotent, and excludes command/env/token/prompt/path data.
24. PreToolUse ownership covers NotebookEdit and direct Bash lifecycle mutation
    bypasses while permitting the adapter and non-mutating test/read commands.
    Broad MCP parity remains outside this Claude-only branch.
25. Hermetic tests cover races, CAS mutation, PR churn, bridge/config failure,
    watcher readiness/budget, strict tracking, push refspec, token isolation,
    NotebookEdit/Bash bypass, and bounded Stop behavior without network access.

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
- 2026-08-01: Review triage added fail-closed bridge, serialized/CAS actions,
  exact PR/CI and push pinning, bounded Stop/watchers, strict stack creation,
  atomic binding, hardened audit, and Claude mutation-tool coverage. Canonical
  `create-pr.sh` entered scope because auto-PR now depends on token isolation.

## Review Triage Log

- Accepted: all twelve coordinator findings covering hook bridge failure modes,
  action races, PR/CI freshness, push pinning, Stop termination, watcher
  lifetime, strict stack tracking, start/bind atomicity, PR token scope, audit
  integrity, mutation-tool bypasses, and their post-review regression tests.
- Deferred: local approval-receipt redesign. The existing tracked human-policy
  model remains authoritative; replacing it is cross-cutting and not required
  for these reversible action safeguards.
- Deferred: broad MCP and cross-tool mutation gating. This branch is the Claude
  adapter boundary; parity belongs in a later cross-tool branch.
- Deferred: removal of all worktree configuration copying. That is separate
  hardening; this branch still requires strict tracking and exact-base creation
  so copying failure cannot silently advance lifecycle state.
