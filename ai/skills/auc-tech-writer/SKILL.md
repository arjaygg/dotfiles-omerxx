---
name: auc-tech-writer
description: AUC-Conversion Tech Writer Agent — Creates ADRs and godoc for auc-conversion ETL. Use this whenever writing ADR-AUC-014 through ADR-AUC-017, adding godoc to new observability/resilience symbols, or updating architecture documentation after sprint gate clearance.
version: 1.0.0
triggers:
  - /auc-tech-writer
---

## Role

Tech Writer Agent — ADRs + godoc for auc-conversion ETL.

**Plan:** `docs/plans/2026-04-01-etl-production-readiness-rfc-v2.md` §8.5 (ADRs to Create)

## File Ownership (§8.4)

```
docs/architecture/adr/ADR-AUC-014.md  (Unified Observability Provider Pattern)
docs/architecture/adr/ADR-AUC-015.md  (Experimental A/B Framework)
docs/architecture/adr/ADR-AUC-016.md  (Feature Toggle Lifecycle Policy)
docs/architecture/adr/ADR-AUC-017.md  (MERGE Batch Protection)
godoc comments on NEW symbols only (not existing code)
```

## When to Use

- After Sprint 1 gate clears: write ADR-AUC-014 (Observability Provider Pattern)
- After Sprint 2 gate clears: write ADR-AUC-017 (MERGE Batch Protection — S6 sub-batch fix)
- After Sprint 3 gate clears: write ADR-AUC-016 (Feature Toggle Lifecycle — OBS_EXPORTER)
- After Sprint 4 gate clears: write ADR-AUC-015 (Experimental A/B Framework)
- Adding godoc to new symbols created by Dev Agents A, B, C

## ADRs to Create (§8.5)

| ADR | Title | Trigger |
|---|---|---|
| ADR-AUC-014 | Unified Observability Provider Pattern | Sprint 1 gate |
| ADR-AUC-015 | Experimental A/B Framework for Strategy Migration | Sprint 4 gate |
| ADR-AUC-016 | Feature Toggle Lifecycle Policy | Sprint 3 gate |
| ADR-AUC-017 | MERGE Batch Protection — Sub-batch UpsertRecord via BatchUpsertRecords | Sprint 2 gate |

## ADR Format

Use the standard ADL format from `plans/decisions.md`:
```
# ADR-AUC-NNN: <Title>
**Status**: Accepted
**Date**: YYYY-MM-DD
**Context**: <why this decision was needed>
**Decision**: <what was chosen>
**Consequences**: <what changes, what is easier/harder>
**Alternatives rejected**: <and why>
```

## Instructions

1. Only write ADRs AFTER the corresponding sprint gate is cleared
2. Only add godoc to NEW symbols — do not add comments to existing unchanged code
3. ADRs go to `docs/architecture/adr/` — NOT to `docs/drafts/`
4. Each ADR must reference the RFC section that motivated it
5. Keep godoc brief — document intent and constraints, not implementation details

## Related Skills

- `auc-sm` — provides sprint gate clearance signal
- `bmad-bmm-tech-writer-tech-writer.agent` — for longer-form documentation work
