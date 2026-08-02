# Lifecycle Stop loop-breaker

**Status:** applied in `2bc47d8` under explicit human authorization on 2026-08-02.
`.claude/hooks/stop.sh` is lifecycle control plane — `agent-user-global.md` reserves
those edits for a human, and `lifecycle_adapter.py start --owned-path` refuses paths
that overlap it (`control_plane_owned`) — so it was published as a reviewable patch
first and applied only once authorised.

**Related:** `9ab3b53` (bridge emits the unbound Stop envelope), `e552f3d` (test
assertion), `scripts/test_lifecycle_stop_bridge.py`.

## Problem

Every other Stop gate can stop repeating itself. The lifecycle branch cannot.

| Gate | loop-breaker |
|---|---|
| `task-gate.sh:27-28` | `stop_hook_active` → exit 0 |
| `git-pipeline-gate.sh:47-48`, `:204-215` | `stop_hook_active` → exit 0, **plus** a session-scoped 2-deny degradation per `branch:signal` |
| lifecycle branch in `stop.sh:64-79` | **none** |

`stop.sh` returns from the lifecycle branch *before* `git-pipeline-gate.sh` runs, so
the one gate that would have degraded is never reached. `lifecycle_adapter.py:2651`
only type-checks `stop_hook_active`; it never decides on it.

Consequence: a single lifecycle block — whether the fail-closed block at `:76` or a
legitimate `awaiting_work` block from a bound run — recurs on every turn until the
client's own block cap fires. Observed in sessions `6e8af5a5` (8 blocks) and
`8232f66a` (9 blocks, then the client's `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` notice).

A fail-closed gate that cannot degrade is not fail-closed; it is fail-stuck.

## Why not just honour `stop_hook_active`

Already investigated and rejected — `plans/2026-07-25-agentic-git-pipeline.md`
L224-239: the flag is global across every registered Stop hook, does not identify
which hook blocked, and was observed already `true` on a spike script's first-ever
invocation. `git-pipeline-gate.sh:22-26` records the same finding, which is why it
pairs the flag with its own counter.

This patch adopts the counter half only.

## What the patch does

Adds `_lifecycle_degrade <key> <reason>` to `stop.sh`, modelled directly on
`git-pipeline-gate.sh:201-225`:

- state in `/tmp/.claude-lifecycle-stop-${session_id}`, session id sanitised to
  `[A-Za-z0-9._-]` before it reaches a path;
- counts blocks per key — `invalid` for the fail-closed path, `bound:<reason>` for an
  adapter block, so distinct reasons do not consume each other's budget;
- at `>= 2` prior blocks: emits nothing on stdout (Stop proceeds), writes
  `LIFECYCLE-STOP: degraded ... -- <reason>` to stderr, and fires an `osascript`
  notification so the signal is not silently swallowed;
- returns 0 to degrade, 1 to keep blocking.

Both block sites are routed through it. The bound branch now captures the adapter's
block into `$_BOUND_BLOCK` before deciding, rather than piping straight to stdout.

## Verification performed

- `bash -n` clean.
- `git apply --check` clean against `fix/lifecycle-stop-unbound-envelope`.
- Helper exercised in isolation over four calls: `BLOCK, BLOCK, DEGRADE, DEGRADE`.

Not yet covered: a dispatcher-level test. `HookDispatcherAndSettingsTests` is the
natural home, but that class currently hangs at
`test_stop_dispatcher_rejects_forged_bound_envelope` on `main` as well — a
pre-existing defect that should be fixed before adding cases there.

## Open design question

A bound run with zero tracked mutations has no work unit to mark ready, so it can only
exit via `release`, and `awaiting_work` blocks it in the meantime. Such a run should
reach a terminal state directly. That is a separate change to `git_lifecycle.py`, not
addressed here.
