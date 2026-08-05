# eval-bootstrap-baseline (without_skill) — final report

**Status:** Done, confirmed by agent.

## (a) Validation approach (self-invented — no skill/convention given)
Wrote its own checker `goals/validate.sh` (bash), treating a goal doc valid if it:
1. matches filename `goal-NN-slug.md`
2. opens with `---` front-matter block
3. has required front-matter keys (id, title, status, owner, created, updated)
4. status is one of proposed/active/blocked/done/abandoned
5. has required sections (Context, Objective, Success Criteria, Milestones, Risks)

Result: `OK: goal-01-webhook-migration.md`, exit 0. Ran a negative sanity check (deliberately malformed
`goal-99-broken.md`) to confirm the checker actually fails bad input (exit 1), then removed it and re-ran
clean. Re-verified green from the copied outputs location.

## (b) Files created
- `goals/README.md` — convention doc: numbering rules, required format, status lifecycle, validation
  instructions, goal index table.
- `goals/goal-01-webhook-migration.md` — Goal 01 (cron-polling → webhook-trigger migration): front matter +
  Context, Objective, Success Criteria, Milestones M1–M6, Risks.
- `goals/validate.sh` — executable validator (chmod +x).

No existing files modified (project-root `README.md` untouched).

**Key divergence from the with-skill convention:** this baseline invented an entirely different
filename scheme (`goal-NN-slug.md`, no date), a front-matter-based format instead of heading-based, and a
different validator language/logic (bash regex+front-matter vs. python heading-order check). This is exactly
the kind of variance the eval is meant to surface — with no skill, each baseline run free-invents its own
convention.

Final project copied to:
`.../eval-bootstrap-new-project/without_skill/outputs/project`
