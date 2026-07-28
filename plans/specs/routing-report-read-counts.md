# Routing Report Read Counts — Frozen Specification

## Ownership

- `scripts/context_routing_report.py`
- `scripts/test_context_routing_report.py`

## Task

Keep post-tool and unrelated telemetry from inflating full-file read counts.

1. Count only actual file-read decisions in `reads.full` and `reads.focused`.
2. Preserve decision, returned-token, cache, false-positive, dead-end, and reference summaries across all relevant events.
3. Add regression coverage with post-output and unrelated-tool rows.
4. Verify targeted tests, Python compilation, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not edit metrics generation, hooks, health report, or client files.
- Do not spawn subagents.
- Do not commit.
