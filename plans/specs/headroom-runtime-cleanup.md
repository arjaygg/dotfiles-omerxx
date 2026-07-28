# Headroom Runtime Cleanup — Frozen Specification

## Ownership

- `scripts/headroom_hardening.py`
- `scripts/test_headroom_hardening.py`
- `setup.sh`

## Task

Close the runtime gap between provider-only configuration and the acceptance target of exactly one healthy persistent Headroom proxy with no disposable MCP containers.

1. Make setup stop recognized Headroom MCP/orphan containers after the persistent proxy is installed or restarted.
2. Preserve the healthy `headroom-default` persistent provider proxy.
3. Keep cleanup idempotent and fail safely when Docker or Headroom is unavailable.
4. Add unit coverage proving only MCP/orphan containers are stopped and the persistent proxy is never selected.
5. Verify the focused `unittest` suite, shell syntax, and `git diff --check`.

## Constraints

- You are not alone in the worktree; preserve concurrent edits and never revert unrelated changes.
- Do not edit client configs or shared gate/benchmark files.
- Do not spawn subagents.
- Do not commit.
