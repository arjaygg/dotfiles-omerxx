# Claude LeanCtx Doctor Compatibility — Frozen Specification

## Ownership

- `.claude/CLAUDE.md`
- `scripts/guidance_adapter_check.py`
- `scripts/test_guidance_adapter_check.py`

## Task

Make the tracked Claude entrypoint recognizable to `lean-ctx doctor` without duplicating shared context policy.

1. Add the smallest supported `<!-- lean-ctx -->` marker block to `.claude/CLAUDE.md`.
2. Do not add a second import of `ai/rules/context-and-compaction.md` or repeat its detailed rules.
3. Extend guidance validation so the marker and exactly-one shared import remain enforced.
4. Verify targeted tests, instruction budgets, and `git diff --check`.

## Constraints

- Preserve concurrent edits; you are not alone in the worktree.
- Do not edit settings, hooks, shared gate/benchmark, or other client files.
- Do not spawn subagents.
- Do not commit.
