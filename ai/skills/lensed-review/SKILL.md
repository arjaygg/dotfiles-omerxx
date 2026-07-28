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

There is **one** review implementation in this repo: this skill. The orchestrator's reviewer stage
invokes it rather than embedding its own logic; the skills that used to duplicate it now shim here,
preserving their old output contracts (retirement record: `ai/skills/REMOVALS.md`).

**Anti-drift:** this file never says what a lens does or which are enabled — that is config, not
prose. Read the resolved lenses from `lenses.toml`, not from memory of what used to be true.

## How it works

1. Read `lenses.toml`. Each entry has exactly five keys: `code`, `applies_to`, `when`, `after`,
   `instruction`. An entry with `instruction = ""` is **disabled** — skip it entirely, do not load
   its reference file.
2. Which lenses run: by default every enabled lens whose `applies_to` matches the target
   (`code`/`docs`/`any`) and whose `when` prose is satisfied. A lens the user names explicitly
   ("just check security") runs regardless of `applies_to`/`when` unless it is disabled — and then
   it runs alone.
3. For each lens that runs, load `references/lens-<code>.md` **just-in-time** — only when that
   lens actually executes. Do not pre-load every reference file.
4. A lens whose `after` field names another lens receives that lens's findings as input (the
   `doubt` lens works this way — it is the adversarial pass over another lens's findings, not a
   separate harness).
5. Every finding conforms to the contract in `ai/skills/cap/references/schemas.md`: `lens`
   (required), `location`, `trigger_condition`, `guard_snippet`, `potential_consequence`. No
   `severity`/`priority` — the Coordinator assigns severity at triage, not this skill.

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

Confirm against the actual run, not from memory: every lens you claim to have run has a non-empty
`instruction`; reference files were loaded only for lenses that ran; every finding carries a `lens`
matching a real lens `code` and no `severity`; any lens with an `after` value ran after that lens,
over its findings.

## Do not

Never inline a lens's instructions here (they belong in `references/lens-*.md`), never create or
modify anything named `review` (Claude Code built-in), and never re-implement a shimmed skill's
logic elsewhere — route through this skill.
