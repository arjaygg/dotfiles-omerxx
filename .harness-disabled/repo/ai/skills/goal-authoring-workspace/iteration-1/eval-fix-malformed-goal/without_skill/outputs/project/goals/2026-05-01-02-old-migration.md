# Goal 02 — Old migration

## Objective

Migrate worker-queue off the deprecated backend onto the new one with no message loss.

## Why

The old queue backend is being deprecated by the vendor at the end of the quarter.

## Current state

Half the workers have been switched over manually; the rest still point at the old backend.

## Non-goals

- Changing the message schema or worker business logic.
- Migrating unrelated services that share the old backend but are out of scope for this cutover.

## Steps

1. Point remaining workers at the new backend.
2. Decommission the old backend.

## Acceptance criteria

All workers process from the new backend; old backend has zero traffic for 24h.

## Evidence to update

- Backend traffic dashboard showing zero traffic on the old backend for 24h.
- Worker configuration confirming every worker targets the new backend.

## Stop and ask if

Any in-flight messages would be dropped during cutover.
