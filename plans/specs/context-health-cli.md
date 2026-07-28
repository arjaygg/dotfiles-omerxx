# Context Health Report CLI — Frozen Specification

## Ownership

- `scripts/context_health_report.py`
- `scripts/test_context_health_report.py`

## Task

Make the report runnable both as `python3 scripts/context_health_report.py` and `python3 -m scripts.context_health_report` from the repository root.

1. Fix only the package/import bootstrap needed for direct invocation.
2. Add a subprocess regression test that avoids live Docker/network dependencies.
3. Preserve report schema and existing behavior.
4. Verify targeted unit tests, Python compilation, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not edit report dependencies or client/config files.
- Do not spawn subagents.
- Do not commit.
