# Decision Records

This repository uses two decision-document layers on purpose:

- `plans/decisions.md`: concise, session-scoped decision log for fast resumption by agents and humans
- `decisions/NNNN-title.md`: durable decision record for long-lived architectural or workflow choices

Use the short form for active work. Promote important decisions to a full ADR when they need durable rationale.

## Purpose By Location

### `plans/decisions.md`

Use this file as the working decision index for the current stream of work.

Optimized for:
- low scan cost
- compaction and session handoff
- agent resumability
- quick human review during active work

Keep entries short. The reader should understand the current constraint in seconds.

### `decisions/`

Use this directory for decisions that should still make sense months later.

Optimized for:
- human auditability
- rationale and tradeoffs
- historical traceability
- onboarding and maintenance

A long-form decision record is the durable explanation. `plans/decisions.md` is the concise operational index.

## Promotion Rule

Keep a decision only in `plans/decisions.md` when it is mostly session context.

Promote a decision to `decisions/` when any of these are true:
- it changes architecture or toolchain behavior
- it affects multiple agents, tools, or workflows
- it introduces a long-lived constraint
- future contributors will likely ask "why did we do this?"
- rollback or migration would be non-trivial

When promoted:
1. create `decisions/NNNN-title.md`
2. keep the short entry in `plans/decisions.md`
3. add a `Record:` link in the short entry

## Structure Rules

Order content by what the primary reader needs first.

- Agent-oriented docs start with current state and immediate implications.
- Human-oriented durable docs start with the problem, decision, and rationale.
- Progress docs start with status and blockers.

## Recommended Structures

### `plans/active-context.md`

Use this order:
1. Current focus
2. Recent changes
3. Constraints and assumptions
4. Open questions or risks
5. Immediate next steps

### `plans/progress.md`

Use this order:
1. Goal or workstream
2. Milestones or phases
3. Checkbox status
4. Blockers
5. Verification state

### `plans/decisions.md`

Keep it append-only unless there is a strong reason to rewrite history.

Recommended entry shape:

```md
## ADL-004: Tool Priority Stack

Status: accepted
Decision: Prefer Serena -> native tools -> Bash(system-only)
Context: Bash-heavy sessions caused slower, noisier file operations and bypassed project-aware tooling.
Consequences: Hooks and agent instructions enforce the priority stack.
Record: decisions/0004-tool-priority-stack.md
```

Required fields:
- `Status`
- `Decision`
- `Context`
- `Consequences`

Optional fields:
- `Record`
- `Date`
- `Supersedes` or `Superseded by`

### `decisions/NNNN-title.md`

Recommended template:

```md
# Architecture Decision Record: Tool Priority Stack

Status: Accepted
Date: 2026-03-23

## Context
What problem exists? What constraints matter?

## Decision
What was chosen?

## Alternatives Considered
What other options were considered and why were they rejected?

## Consequences
What becomes easier, harder, required, or forbidden now?

## Rollout
What changed, or what still needs to change?

## References
Links to plans, PRs, commits, issues, or external docs.
```

## Writing Guidance

Prefer:
- direct statements
- concrete consequences
- stable identifiers
- links to source material

Avoid:
- long narrative in `plans/decisions.md`
- hiding the actual decision under too much context
- using one ADR file per tiny session-only choice
- treating `plans/` as the permanent archive

## Source Of Truth

Use this document as the canonical convention.

Short summaries belong in:
- `CLAUDE.md` for repo operating rules
- `ai/rules/context-and-compaction.md` for compaction and handoff behavior
