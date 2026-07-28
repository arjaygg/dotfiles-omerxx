# Definition of Done

This is the **standing, project-wide bar** applied to every worker return, identical every time —
*"is it ready?"* It is separate from and applied **after** a task's own **acceptance criteria**,
which are per-task and answer a different question — *"did we build this thing?"* A return must
clear both. See `plans/2026-07-27-native-agent-orchestration.md` §19 for how this fits into the
verification sequence (re-run `Accepts` yourself, inspect the real diff, then apply this bar).

## Correctness

- The stated `Accepts` check was re-run by the Coordinator, not self-reported by the worker.
- The change does what the spec asked, not a plausible adjacent thing.
- No silent failure: errors propagate or are handled, never swallowed.
- Edge cases implied by the spec (empty input, missing file, concurrent access) are covered, not
  assumed away.

## Quality

- No dead code, commented-out blocks, or leftover debug output.
- No unexplained abstractions or speculative generality beyond what the task required.
- Naming and structure are consistent with the surrounding file/module.
- Comments (if any) explain a non-obvious *why*, not a restatement of *what*.

## Integration

- The change composes with existing callers/consumers — checked, not assumed.
- No unrelated files were touched beyond the stated `**Files:**` scope without a stated reason.
- Config, schema, or contract changes are reflected everywhere they're duplicated (e.g. both
  `.claude/settings.json` and `ai/config/claude/settings.base.json` stay byte-identical).

## Documentation

- Any new convention, decision, or non-obvious behavior is recorded where a future agent will look
  for it (`plans/decisions.md`, a durable `decisions/` record, or the relevant skill/rule file) —
  not left only in chat history.
- Evidence files named in the owning goal/plan's "Evidence to update" section are actually updated.

## Ship-readiness

- Work is isolated on a branch/worktree, never committed directly to `main`.
- The commit message follows the repo's conventional-commit + why-body format.
- No irreversible action (`auto_ship`, `auto_clean`, a force-push, a merge) ran above the
  authorized autonomy tier.
- The Coordinator — not the worker — made the final accept/reject call.
