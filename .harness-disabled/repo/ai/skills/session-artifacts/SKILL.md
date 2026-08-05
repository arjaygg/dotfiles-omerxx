---
name: session-artifacts
description: >
  Templates and conventions for the three session artifacts kept in `plans/` —
  `active-context.md` (ephemeral focus pointer, read at compaction), `decisions.md`
  (rolling ADL log), and `progress.md` (rolling checkbox task state). Use when
  creating or updating any of these files, or when recording an architectural
  decision or a root cause.
triggers:
  - active-context.md
  - decisions.md
  - progress.md
  - session artifacts
  - ADL
  - architecture decision log
---

# Session Artifacts

Three files under `plans/` (create if missing). `plans/` is gitignored and ephemeral —
reviewable plans belong in a tracked location such as `docs/plans/`.

| File | Lifecycle |
|---|---|
| `active-context.md` | Ephemeral per-session state. Keep it <=30 lines. It is read at compaction, so keep it current. Archive or delete when starting a new unrelated task. |
| `decisions.md` | Rolling log — append across sessions; never delete or archive history. A project's own docs may designate it a durable ADL log spanning months. |
| `progress.md` | Rolling log — append/update across sessions; never delete history. |

## When to update

- **`active-context.md`** — whenever focus shifts, a significant discovery lands, or direction changes.
- **`decisions.md`** — on any architectural choice or root-cause finding.
- **`progress.md`** — as task state changes.

## `decisions.md` — ADL entry format

```
## YYYY-MM-DD — <Decision title>
**Decision:** <what was chosen>
**Why:** <reasoning>
**Alternatives rejected:** <and why>
**Assumptions:** <what must hold for this to be correct>
```

## `progress.md` — checkbox format

```
## In Progress
- [ ] task being worked on

## Done
- [x] completed task

## Blocked
- [ ] blocked task (reason)
```

## Plan File Naming and Location

Plan files are named `YYYY-MM-DD-<context>.md`, where `<context>` is a 3-5 word kebab-case
summary of the task (e.g. `2026-03-02-refactor-auth-flow.md`). Use the current date as the
prefix; multiple plans on the same day each get their own context. Session-state plans default
to `plans/` (the `plansDirectory` in `~/.claude/settings.json`; create it if missing) — a
project's own docs may route reviewable/tracked plans elsewhere (e.g. `docs/plans/`), and that
routing wins.

## Working From a Dated Plan File

When working from a dated plan file (`plans/YYYY-MM-DD-<context>.md`):

1. Add `plan: plans/YYYY-MM-DD-<context>.md` to `active-context.md` at session start.
2. Add `step: N of M` and `focus: <current step title>` to `active-context.md`.
3. Each `## Step N` in the plan must declare `**Files:**` and `**Accepts:**` fields.
4. Use `TodoWrite` to convert plan steps to an ordered checklist for single-agent execution
   before executing. `TaskCreate` is a separate mechanism for multi-agent coordination, not a
   substitute for this checklist.
5. Check off `progress.md` checkboxes when each `TodoWrite` item is completed.
6. Do not begin Step N+1 until Step N's `**Accepts:**` criteria are met.

## `active-context.md` — plan pointer fields

```
plan: plans/YYYY-MM-DD-<context>.md
step: N of M
focus: <current step title>
```
