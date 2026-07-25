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

## `active-context.md` — plan pointer fields

When working from a dated plan file, carry these fields (see
`ai/rules/agent-user-global.md` § Plan Documents):

```
plan: plans/YYYY-MM-DD-<context>.md
step: N of M
focus: <current step title>
```
