---
status: frozen
review_round: 5
---

# Frozen Spec — Claude lifecycle adapter final hardening

<intent-contract>
Replace the adapter's best-effort guards with a fail-closed Claude execution
boundary. A bound run must be the only route to lifecycle mutation; commits,
network actions, policy, sessions, hooks, and CI watchers must remain pinned to
the evidence approved at run start. Preserve useful read/test workflows through
an explicit allowlist, but deny unknown Bash and mutation-capable pctx execution.
</intent-contract>

## Scope

- `scripts/ai/lifecycle_adapter.py`
- `scripts/ai/git_lifecycle.py` only if a recovery transition is required
- `scripts/ai/commit.sh`
- `scripts/ai/autonomy-tier.sh`
- `.claude/hooks/lifecycle-hook.sh`
- `.claude/hooks/lifecycle-envelope.py`
- `.claude/hooks/lifecycle-pretool.sh`
- `.claude/hooks/stop.sh`
- `.claude/hooks/sessionstart.sh`
- `.claude/hooks/userpromptsubmit.sh`
- `ai/config/claude/settings.base.json`
- `.claude-atomic.yaml`
- `.claude/scripts/pr-stack/create-stack.sh`
- `.claude/scripts/pr-stack/create-pr.sh`
- `.claude/hooks/worktree-create.sh`
- focused lifecycle, hook, wrapper, and policy tests
- lifecycle policy docs/spec review log

## Acceptance

1. Bash is default-deny in an opted-in repository. The hook first resolves the
   real Claude session and bound run, then permits only:
   - the exact resolved tracked `lifecycle_adapter.py` with a matching explicit
     session ID;
   - narrowly parsed read-only commands;
   - explicit trusted validation command shapes while the run is editable.
   Shell operators, redirects, substitutions, aliases, nested interpreters,
   unknown scripts, lookalike adapter basenames, canonical mutation wrappers,
   Git ref/worktree/index mutation, and mutating `gh api`/PR forms are denied.
2. `mcp__pctx__execute_typescript` is included in PreToolUse lifecycle matching
   and denied while lifecycle control is enabled. Metadata-only pctx discovery
   remains available. This branch does not claim general MCP sandboxing.
3. Hook payloads use event-specific schema validation. Enabled adapter output is
   an explicit versioned processed/bound/unbound envelope; empty or wrong-shaped
   output, missing bridge/adapter, parser/repository errors, or unavailable
   helpers fail closed. Only proven non-repository/disabled and exact unbound
   Stop state may silently fall back.
4. CLI mutation commands have no `"default"` session fallback. Session IDs are
   validated and injected into hook guidance. A locked reverse run-to-session
   binding prevents two live sessions from sharing a nonterminal run. Session
   release/takeover behavior is explicit and audited.
5. Owned paths may not equal, contain, or be an ancestor of lifecycle control
   plane files: policy, hooks/settings, controller/adapter, autonomy resolver,
   canonical commit/stack entrypoints, or their configuration. Start and every
   write gate enforce this independently.
6. Run start atomically snapshots the human-owned lifecycle policy, current
   origin fetch/push identity, normalized GitHub repository, expected actor, and
   rollout approval under the git common directory. Actions resolve autonomy
   from that immutable snapshot, reject policy/remote drift, and honor the live
   `git-pipeline-gate` off switch. The origin must be one equal normalized HTTPS
   fetch/push URL, and the expected actor is read only from human-owned policy.
7. Push verifies fresh action evidence and the pinned remote, uses a bounded
   noninteractive process group, and sends
   `<inspected-sha>:refs/heads/<validated-branch>`. PR creation verifies that
   exact remote SHA and approved actor/repository with a token selected for that
   actor, never pushes again, and only records an actor-owned open non-draft
   exact PR.
8. Commit builds an immutable private index/tree from the approved paths,
   validates that exact index, creates the approved commit tree and expected
   parent, and updates the intended branch with an expected-parent CAS. A
   concurrent default-index/ref mutation cannot enter the commit. Mutable
   repository Git hooks are disabled only for lifecycle private commits;
   adapter-owned message/intent behavior remains enforced, ordinary commits keep
   normal hook behavior, and crash recovery leaves a deterministic state.
9. Every external process runs in its own process group with a bounded timeout,
   noninteractive Git network behavior, TERM/KILL escalation, and reaping on
   timeout, signals, or other `BaseException`. No descendant may continue
   mutating after timeout or lock release.
10. A CI watcher marker is not a lease. Only a validated marker plus a currently
    held execution lock is active. Failed, timed-out, dead, malformed, or stale
    markers restart under the spawn lock; Stop blocks unless watcher readiness or
    a live duplicate lease is proven.
11. Required-check reconciliation preserves documented `gh` exit 1 failure and
    exit 8 pending results only when JSON agrees. Passing additionally requires
    authoritative complete merge-readiness evidence and a second identical open
    non-draft exact-PR observation; partial/missing evidence stays unknown.
12. Failure intent/demotion persists before audit. A durable pending/completed
    action journal is written before execution and reconciled idempotently before
    any later action can advance. Audit uses secure no-follow directory
    traversal, owned single-link regular files, complete JSONL parsing,
    incomplete-tail repair, parsed-event deduplication, fsync, and redacted
    diagnostics. Audit failure cannot restore autonomy or permit advancement.
13. `autonomy-tier.sh` rejects duplicate policy blocks/keys and incomplete,
    malformed, expired, unsigned, unknown-stage, or invalid-basis overrides.
14. `.trees` must be a real non-symlink directory physically contained beneath
    the repository immediately before worktree creation and configuration copy.
15. `create-pr.sh` handles failed `gh` execution without `set -e` skipping its
    branch and returns a bounded redacted reason.
16. A failed commit validation has an explicit recovery path back to editable
    state without bypassing or silently reporting success.
17. Tests reproduce every final-review bypass and race, including lookalike
    adapter scripts, direct wrappers, nested interpreters, Git aliases/ref
    plumbing, mutating GitHub API, forged/wrong-shaped hook envelopes,
    cross-session binding, control-plane ownership, policy/remote/SHA drift,
    concurrent index mutation, dead watchers, partial required checks, audit
    tails, malformed overrides, and symlinked `.trees`.
18. Focused and inherited lifecycle/config suites, shell syntax, JSON parsing,
    executable bits, and `git diff --check` pass without network access.

## Constraints

- Work only on `feature/claude-lifecycle-adapter`.
- Do not enable merge, sync, cleanup, force push, admin merge, or remote setting
  changes.
- Do not add third-party dependencies.
- Do not weaken the shared controller's exact-evidence contract.
- Keep lifecycle disabled or fail closed if any acceptance item cannot be made
  enforceable without a larger sandbox architecture; document the residual
  boundary instead of claiming protection.

## Review Basis

Three independent final reviews agreed that the prior passing test suite did not
prove the enforcement boundary. This spec accepts their overlapping command,
bridge, session, policy, watcher, network, commit-CAS, timeout, CI, audit, and
stack-path findings as release blockers.

## Review Triage Log

- Round 5 (2026-08-02): bounded child cleanup now blocks and ignores
  catchable terminal signals while terminating, closing streams, and proving
  the complete process group gone. Repeated mixed signals cannot replace the
  first exit semantics or leave descendants alive.
- Round 5: every action journal carries a cryptographically random attempt ID
  and immutable evidence ID. Strict stack creation writes a secure durable
  completion receipt only after independently verifying the exact base,
  intended contained worktree/common-dir identity, and Charcoal parent
  metadata. Pending stack reconciliation requires that exact receipt;
  missing, malformed, or stale receipts demote `auto_stack` and halt the run.
- Round 4 (2026-08-02): the loaded settings command now captures the
  `PreToolUse` dispatcher status and output, then applies its own inline strict
  allow/deny envelope validation. Missing, failed, empty, malformed, duplicate,
  wrong-event/binding/run-id, and invalid native payloads emit an exit-zero
  hard deny without trusting the mutable dispatcher validator.
- Round 4: lifecycle exact-base stack creation disables repository hooks for
  every child Git process. Exact-SHA push, tracking-ref update, and upstream
  mutation also disable hooks; the Git credential environment clears `GH_TOKEN`
  while the process-scoped askpass token remains inaccessible to disabled
  pre-push/reference hooks. Ordinary non-lifecycle Git hook behavior is unchanged.
- Round 3 (2026-08-02): fixed shell-expansion/option probes, repository-module
  execution in trusted validation, and outer bridge output trust.
  Disabled/unbound fallback now requires an explicit validated envelope.
- Round 3: `.claude-atomic-intent` uses atomic replacement rather than following
  a destination symlink. `EnterWorktree`/`ExitWorktree` are lifecycle-denied,
  and the worktree hook independently checks physical `.trees` containment.
- Round 3: lifecycle private commits no longer execute mutable repository Git
  hooks. Ordinary `commit.sh` behavior remains hook-compatible.
- Round 3: contract capture rejects missing, multiple, non-HTTPS, or unequal
  origin identities before persistence. Mutation credentials are selected with
  `gh auth token --user` for the policy actor, verified through `/user`, held
  only in process memory/environment, and shared with pinned HTTPS push or PR
  creation. PR/check commands name the pinned repository explicitly and verify
  resulting authorship.
- Round 3: process-group cleanup covers interrupts and signals; action execution
  writes a durable reconciliation journal before side effects; PR errors expose
  only the bounded structured redaction emitted by `create-pr.sh`.
- Round 3 residual boundary: general MCP sandboxing remains out of scope as
  stated in Acceptance 2. No listed lifecycle acceptance item requires disabling
  rollout; `lifecycle.enabled` remains `true`.
