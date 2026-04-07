# /ia

Surface Information Architecture for context before implementation.

## When to use

Run before any implementation task that touches data models, APIs, or entity relationships. Essential for:
- Adding new features that interact with core entities
- Modifying table structures or schemas
- Building queries or bulk operations
- Designing API contracts
- Understanding entity lifecycles and state transitions

Prevents Claude from guessing struct relationships on every feature request.

## Procedure

1. **Load Information Architecture**
   - Call `Serena.readMemory("architecture/information-architecture")`
   - This surfaces Objects, Relationships, Lifecycles, Source of Truth, and API Boundaries

2. **Scan the relevant section**
   - Identify which domain entities are involved in the current task
   - Note relationships (1:1, 1:n, n:m) between them
   - Check Source of Truth to understand where state lives

3. **Reference during implementation**
   - When writing code that touches multiple entities, refer back to the IA
   - Ensure queries/operations respect documented relationships
   - Validate assumptions against the Lifecycles section

## Related commands

- `/findings` — Consolidate session discoveries into persistent memories
- `/explore` — Deep codebase navigation using pctx/Serena and LeanCtx
