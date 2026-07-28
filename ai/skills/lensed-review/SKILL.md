---
name: lensed-review
description: >
  Lensed Review — the one review mechanism for this repo. Runs a config-declared set of
  "lenses" (correctness, security, resilience, style, doubt) against code or docs; each lens
  loads its reference file just-in-time and emits findings in the shared finding contract.
  Supersedes hawk, pr-review, code-health, and bmad-custom-pr-review, which now shim to this.
  Triggers: review this, code review, review my changes, review this PR, adversarial review,
  code health check, /lensed-review.
triggers:
  - /lensed-review
  - review this
  - review my code
  - review my changes
  - code review
  - adversarial review
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - TaskUpdate
  - TaskGet
---

# Lensed Review

There is **one** review implementation in this repo: this skill. The orchestrator's reviewer
stage invokes it rather than embedding its own review logic. Legacy skills that used to duplicate
this logic (`hawk`, `pr-review`, `code-health`, `bmad-custom-pr-review`) are now shims that forward
here while preserving their old output contracts — see `ai/skills/REMOVALS.md` for the retirement
record.

**Anti-drift:** this file never claims what a lens does or which lenses are enabled — that is
config, not prose. Read the resolved lenses from `lenses.toml` and work from those, not from
memory of what used to be true.

## How it works

1. Read `lenses.toml`. Each entry has exactly five keys: `code`, `applies_to`, `when`, `after`,
   `instruction`. An entry with `instruction = ""` is **disabled** — skip it entirely, do not load
   its reference file.
2. Determine which lenses run:
   - Default review: every enabled lens whose `applies_to` matches the target (`code`/`docs`/`any`)
     and whose `when` prose is satisfied.
   - Explicitly requested lens (e.g. "run the security lens"): runs regardless of `applies_to`/
     `when`, as long as it isn't disabled.
3. For each lens that runs, load `references/lens-<code>.md` **just-in-time** — only when that
   lens actually executes. Do not pre-load every reference file.
4. A lens whose `after` field names another lens receives that lens's findings as input (the
   `doubt` lens works this way — it is the adversarial pass over another lens's findings, not a
   separate harness).
5. Every finding — from every lens — conforms to the shared finding contract in
   `ai/skills/cap/references/schemas.md`: `lens` (required), `location`, `trigger_condition`,
   `guard_snippet`, `potential_consequence`. No `severity`/`priority` field; the Coordinator
   assigns severity at triage time, not this skill.

## Activation

Invoke via `/lensed-review`, or when the user asks for a code/doc review in any of the trigger
phrasings above. If the user names a specific lens ("just check security"), run only that lens per
step 2 above.

## Customization

Shipped defaults live in `customize.toml` (do not edit it — it is overwritten on update).
Overrides resolve base → `.claude/custom/lensed-review.toml` →
`.claude/custom/lensed-review.user.toml`. Get the merged result with
`python3 scripts/resolve_customization.py lensed-review`.

**If the resolver is unavailable or fails, use the three-file fallback:** read all three paths
yourself in that order and apply the merge rules by hand — scalars override, tables deep-merge,
arrays of tables keyed by `code` or `id` replace on matching key and append on new, all other
arrays append. Do **not** fall back to reading only `customize.toml`: that silently drops every
override. Name which layers you applied, and any `file:` value you could not read.

## Verification

Confirm each of these against the actual run, not from memory:

- Every lens you claim to have run has a non-empty `instruction` in `lenses.toml`, and you
  loaded reference files only for lenses that ran.
- Every finding carries a `lens` matching a real lens `code`, and no `severity` field; any
  lens with an `after` value ran after that lens, over its findings.

## Do not

- Do not inline any lens's instructions in this file — they belong in `references/lens-*.md`.
- Do not create or modify anything named `review` (Claude Code built-in — untouchable).
- Do not re-implement `hawk`/`pr-review`/`code-health`/`bmad-custom-pr-review`'s logic elsewhere;
  route through this skill instead.
