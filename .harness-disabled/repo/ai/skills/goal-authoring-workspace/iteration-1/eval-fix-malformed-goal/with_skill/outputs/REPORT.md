# eval-fixmalformed-with-skill (with_skill) — final report

**Status:** Done, confirmed by agent.

## (a) Validator
BEFORE (exit 1):
```
ERROR: index entry has invalid goal filename: 2026-05-01-2-old-migration.md
ERROR: invalid goal filename: goals/2026-05-01-2-old-migration.md
FAIL: 2 goal validation error(s)
```
AFTER (exit 0):
```
PASS: 1 goal file(s) validated
```
Confirmed in both the working project and the copied outputs project.

## (b) Files created/renamed/modified/deleted
- RENAMED: `goals/2026-05-01-2-old-migration.md` → `goals/2026-05-01-02-old-migration.md` (seq must be
  zero-padded `NN` per `YYYY-MM-DD-NN-slug.md`; not a git repo, so implemented as Write new path + `rm` old
  path — index shows explicit DELETED of the old filename).
  - Same file also had headings fixed: before `# Goal 02` → Why → Objective → Current state → Steps →
    Acceptance criteria → Stop and ask if. After: Objective → Why → Current state → **Non-goals (added)** →
    Steps → Acceptance criteria → **Evidence to update (added)** → Stop and ask if.
- MODIFIED: `goals/00-index.md` — seq-02 filename reference corrected, outcome text refreshed.
- MODIFIED: `plans/active-context.md` — `goal:` pointer updated to corrected filename.
- DELETED: `goals/2026-05-01-2-old-migration.md` (old name, part of the rename).

Untouched: `scripts/validate_goals.py`, `goals/README.md`.

Final project copied to:
`.../eval-fix-malformed-goal/with_skill/outputs/project`

## Note from agent
The validator only reported the filename errors (heading/order check runs after the filename maps into the
index), but the agent corrected heading order + missing sections anyway per the skill's required-heading
convention — so the file is both validator-valid and structurally correct, not just patched to pass the
narrower check.
