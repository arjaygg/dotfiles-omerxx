---
name: goal-authoring
description: Conventions for creating and maintaining a project's goals/ directory — handoff-ready objective documents (as distinct from plans/, which holds session state). Covers the required goals/README.md, the YYYY-MM-DD-NN-slug.md filename format, the exact required heading order (Objective, Why, Current state, Non-goals, Steps, Acceptance criteria, Evidence to update, Stop and ask if), the goals/00-index.md status board, and the scripts/validate_goals.py + pre-commit hook that enforce it. USE THIS SKILL whenever the user asks to "create a goal", "write a goal doc", "set up a goals directory", "author a goal for this repo", or references a Goal NN by number — and also when a project already has a goals/ directory and the user wants a new dated goal file added, an existing one updated, or its status changed on the index. This is a deterministic authoring/validation convention, not a place for open-ended brainstorming — if the project has no goals/ directory yet, offer to bootstrap one before writing the first goal file.
triggers:
  - create a goal
  - write a goal doc
  - author a goal
  - set up a goals directory
  - goal authoring convention
  - goals/00-index.md
  - Goal NN
  - validate_goals.py
---

# Goal Authoring

`goals/` holds handoff-ready objective documents — something you could paste into a brand-new session with zero prior context and it would know exactly what to do, why, and when to stop. This is different from `plans/`, which holds ephemeral session state (decisions, progress, active focus) for the session that's actually doing the work. A goal outlives the session that wrote it; a plan doesn't.

This convention only works because it's deterministic and machine-checkable. Don't freelance the heading names, the filename format, or the status values below — the whole point is that any agent, in any session, can look at `goals/00-index.md` and a goal file and know precisely where things stand without asking.

## Step 0: does this project already have a `goals/` directory?

Check before doing anything else. The behavior forks:

- **No `goals/` directory yet** → this is a bootstrap. Go to "Bootstrapping a new project" below, then come back here for the actual goal content.
- **`goals/` already exists** → skip straight to "Writing a goal file" or "Updating the index," whichever the user asked for. Don't re-bootstrap an existing convention or overwrite its `README.md`/`00-index.md` — read what's there first.

## Bootstrapping a new project

Copy the bundled templates into the target project (the project the user is actually working in — not into this dotfiles repo, unless the user is specifically working on dotfiles itself):

1. Create `goals/` if it doesn't exist.
2. Copy `assets/goals-README.md` → `goals/README.md` (this is the same convention doc you're reading now, adapted for the target repo — read it once installed so future sessions in that repo have a self-contained reference).
3. Copy `assets/00-index-template.md` → `goals/00-index.md`.
4. Copy `scripts/validate_goals.py` → `<project>/scripts/validate_goals.py`. This script assumes it lives at `<project-root>/scripts/validate_goals.py` (it resolves its own project root via `Path(__file__).resolve().parents[1]`) — don't relocate it without updating that line.
5. Copy `scripts/pre-commit-goals.sh` → `<project>/scripts/pre-commit-goals.sh`.
6. Offer to install the pre-commit hook (this modifies the user's local git hooks — confirm before running it, don't do it silently):
   ```bash
   ln -sf ../../scripts/pre-commit-goals.sh .git/hooks/pre-commit
   ```
   This hook only fires validation when staged changes touch `goals/**` or `plans/active-context.md` — it's a no-op the rest of the time, so it's safe to install even in repos where goals aren't used on every commit.

A repo with no `goals/` directory is a valid, permanent state too — `validate_goals.py` prints `OK: no goals/ directory` and exits 0 if the directory is absent. Don't treat "this repo has no goals/" as something that needs fixing unless the user asked for it.

**Public-repo caution:** before bootstrapping into a repo, consider whether it's public. A public repo's `goals/` directory is visible to anyone — don't default sensitive company/personal objective content into a public repo just because that's where you happen to be working. If unsure, ask, or check with `gh repo view --json visibility`.

## Filename convention

Goal files MUST be named:

```
YYYY-MM-DD-NN-slug.md
```

- `YYYY-MM-DD` — the date the goal was authored or materially split into a new goal.
- `NN` — a zero-padded sequence number (`01`, `02`, ...), unique within the repo, matching the `#` column in `00-index.md`.
- `slug` — lowercase kebab-case, describes the objective.

Examples: `2026-07-13-01-phase2-fk-extract-recovery.md`, `2026-07-13-05-phase6-synthesis-preflight-gate.md`.

## Required headings, in order

Every goal file MUST contain these exact headings, in this exact order (a validator checks position, not just presence — a heading in the wrong place is treated the same as a missing one):

1. `# Goal NN — <title>`
2. `## Objective`
3. `## Why`
4. `## Current state`
5. `## Non-goals`
6. `## Steps`
7. `## Acceptance criteria`
8. `## Evidence to update`
9. `## Stop and ask if`

## Writing a good goal

A goal file that passes the validator but is still useless to a fresh agent has failed at its actual job. Before considering one ready:

- The objective is one concrete outcome, not a vague workstream ("ship the migration" not "improve data quality").
- Acceptance criteria are observable — files, reports, tests, counts, explicit user sign-off — not vibes.
- Steps are ordered and executable by a fresh agent without hidden context that only lives in your head or this session's chat history.
- Anything that touches production is clearly gated behind explicit user go-ahead — don't let a goal file imply autonomy it shouldn't have.
- Guardrails call out read-only DB access, PII handling, and no-concurrent-prod-jobs constraints when they're relevant to this goal.
- Known blockers and unresolved decisions are named explicitly, not glossed over.
- The goal points at canonical evidence paths (specific files, dashboards, test suites), not just narrative memory of what was checked.
- The goal says when to stop and ask, rather than leaving a fresh agent to guess how far its authority extends.

## Tracking convention: `goals/00-index.md`

Every goal file must appear exactly once in the index, with one of these statuses:

- `pending` — not started.
- `active` — in progress; **at most one** goal may be active at a time in the repo.
- `blocked` — can't progress without user input or an external state change.
- `done` — acceptance criteria met.
- `superseded` — replaced by another goal, or no longer applicable.

When a goal becomes `active`, `plans/active-context.md` must contain a pointer line matching it:

```
goal: goals/YYYY-MM-DD-NN-slug.md
status: active
focus: <current step or blocker>
```

Write this pointer block in the same turn you mark the goal `active` — don't leave it for later. It's easy to create the goal file and index row, then move on to the actual work and forget `plans/active-context.md` entirely, especially when it started out as an unfilled skeleton template. A goal marked `active` in the index with no matching pointer is exactly the inconsistency the validator exists to catch — treat filling in the pointer as part of *making* the goal active, not a follow-up step.

Chronological progress belongs in `plans/progress.md`; decisions and root-cause conclusions belong in `plans/decisions.md`. Don't let a goal file turn into a running log — that's what `plans/` is for. A goal file describes the destination and how to verify arrival, not a diary of the trip.

## Validating

Before telling the user a goal is ready — new file, status change, or index update — run the validator from the project root:

```bash
python3 scripts/validate_goals.py
```

It checks: filename format, index membership (every goal file listed exactly once, every listed file actually exists), valid/unique status values, at-most-one-active enforcement, the active-goal ↔ `plans/active-context.md` pointer match, and required-heading presence/order. A clean run prints `PASS: N goal file(s) validated` and exits 0; anything else prints `ERROR:` lines to stderr and exits 1 — treat a non-zero exit the same as a failing test, not a warning to skim past.

If the repo already has `scripts/pre-commit-goals.sh` installed as `.git/hooks/pre-commit`, this also runs automatically on any commit touching `goals/**` or `plans/active-context.md` — but don't rely on the hook alone during interactive work; run the validator yourself before reporting completion.
