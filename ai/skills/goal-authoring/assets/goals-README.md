# Goals

Reusable `/Goal`-style prompts live here.

Use `plans/` for session state, decisions, and progress logs. Use `goals/` for handoff-ready objectives that can be pasted into a fresh goal/session.

## Deterministic convention

### Directory layout

- Keep goal files directly under `goals/`.
- Keep `goals/00-index.md` as the ordered table of contents.
- Do not create subdirectories unless there are multiple independent goal sets in the same repo.

### Filename format

Goal files MUST be named:

```text
YYYY-MM-DD-NN-slug.md
```

Where:
- `YYYY-MM-DD` is the date the goal was authored or materially split.
- `NN` is a zero-padded sequence number (`01`, `02`, ...).
- `slug` is lowercase kebab-case and describes the objective.

Examples:
- `2026-07-13-01-phase2-fk-extract-recovery.md`
- `2026-07-13-05-phase6-synthesis-preflight-gate.md`

### Required sections

Every goal file MUST include these exact headings, in this order:

1. `# Goal NN — <title>`
2. `## Objective`
3. `## Why`
4. `## Current state`
5. `## Non-goals`
6. `## Steps`
7. `## Acceptance criteria`
8. `## Evidence to update`
9. `## Stop and ask if`

### Best-practice checklist

Before considering a goal ready:

- The objective is one concrete outcome, not a vague workstream.
- Acceptance criteria are observable files, reports, tests, counts, or explicit user sign-off.
- Steps are ordered and can be executed by a fresh agent without hidden context.
- Production-touching actions are clearly gated behind explicit user go-ahead.
- Guardrails mention read-only DB access, PII discipline, and no concurrent production jobs when relevant.
- Known blockers and unresolved decisions are named explicitly.
- The goal references canonical evidence paths, not only narrative memory.
- The goal says when to stop and ask rather than guessing.

## Tracking convention

`goals/00-index.md` is the status board. Every goal file must appear there exactly once.

Allowed statuses:

- `pending` — not started.
- `active` — current goal in progress; at most one active goal is allowed.
- `blocked` — cannot make progress without user input or external state change.
- `done` — acceptance criteria met.
- `superseded` — replaced by another goal or no longer applicable.

When a goal becomes active, `plans/active-context.md` must include:

```md
goal: goals/YYYY-MM-DD-NN-slug.md
status: active
focus: <current step or blocker>
```

Chronological progress belongs in `plans/progress.md`. Decisions and root-cause conclusions belong in `plans/decisions.md`. Do not turn goal files into progress logs.

## Validation

Run:

```bash
python3 scripts/validate_goals.py
```

The validator checks filename format, index membership/status, active-goal pointer consistency, and required heading order.

The repo-local pre-commit hook wrapper is `scripts/pre-commit-goals.sh`. Install it with:

```bash
ln -sf ../../scripts/pre-commit-goals.sh .git/hooks/pre-commit
```

The hook runs validation only when staged files touch `goals/**` or `plans/active-context.md`.
