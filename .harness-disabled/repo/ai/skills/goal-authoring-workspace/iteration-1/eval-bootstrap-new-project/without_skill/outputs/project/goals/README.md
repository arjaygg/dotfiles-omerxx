# Goals

This directory tracks the meaningful, multi-step objectives for **notify-svc**.
A "goal" is bigger than a single ticket but smaller than a roadmap — a piece of
work with a clear outcome, some risk, and a few milestones worth tracking.

## Conventions

- One file per goal: `goal-NN-short-slug.md` (zero-padded, sequential).
- Numbers are permanent. Never reuse or renumber a goal once created.
- Keep goals in this directory; keep the index below current.

## Goal file format

Each goal doc must contain the following sections (checked by `validate.sh`):

| Section          | Purpose                                                      |
| ---------------- | ----------------------------------------------------------- |
| Front matter     | `id`, `title`, `status`, `owner`, `created`, `updated`      |
| `## Context`     | Why this goal exists; the current state.                    |
| `## Objective`   | The single outcome, stated in one or two sentences.         |
| `## Success Criteria` | Checkboxes that are objectively verifiable.            |
| `## Milestones`  | Ordered, checkable steps toward the objective.              |
| `## Risks`       | Known risks / unknowns and how we'll handle them.           |

### Status values

`proposed` → `active` → `blocked` → `done` (or `abandoned`).

## Validating

Run the checker to confirm every goal doc is well-formed:

```sh
./goals/validate.sh
```

It verifies front matter fields and required sections are present in every
`goal-*.md` file. Exit code `0` means all goals are valid.

## Index

| ID | Title                                          | Status   |
| -- | ---------------------------------------------- | -------- |
| 01 | Migrate email notifications from cron polling to webhook triggers | proposed |
