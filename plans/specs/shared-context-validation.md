# Shared Context Validation — Frozen Specification

## Ownership

- `ai/context/context_gate.py`
- `scripts/test_context_gate.py`
- `scripts/context_retrieval_benchmark.py`
- `scripts/test_context_retrieval_benchmark.py`
- `scripts/fixtures/context-routing/complex.md`
- `.local/bin/lean_ctx_wrapper.sh`

## Task

Audit and harden the shared gate and LeanCtx benchmark against the accepted context-routing plan.

1. Preserve unrelated shell commands; only compound commands involving likely native file reads may warn.
2. Correctly classify direct reads, `cat`, `head`, `tail`, bounded `sed`, input redirection, and simple pipelines without allowing an unbounded read through a misleading command class.
3. Preserve fail-open behavior for malformed payloads and unparseable compound reads.
4. Verify exact `raw` and `full` bytes through the tracked portable wrapper.
5. Make the benchmark exercise a real task-aware focused read and cache reread; do not fake upstream success.
6. If LeanCtx 3.9.12 cannot meet focused-output or cache targets, retain a safe local workaround where feasible and report the reproducible remaining defect explicitly.
7. Add regression tests for every correction and run the focused `unittest` suite plus `git diff --check`.

## Constraints

- You are not alone in the worktree; preserve concurrent edits and never revert unrelated changes.
- Do not edit client-specific adapters or configuration.
- Do not spawn subagents.
- Use standard-library-only implementation code.
- Do not commit.
