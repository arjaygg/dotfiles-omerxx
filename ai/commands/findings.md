# /findings

Consolidate session discoveries into persistent Serena memories.

## When to use

Run at the end of any meaningful session — after completing a feature, fixing a bug, or making architectural discoveries. Ensures that what was learned doesn't get lost when the session ends.

## Procedure

1. **Review session artifacts:**
   - Read `plans/decisions.md` — look for entries added this session (today's date)
   - Read `plans/active-context.md` — what was the focus and what was discovered?
   - Recall any architectural surprises, gotchas, or patterns noticed during the session

2. **Cross-reference against existing memories:**
   - Call `Serena.listMemories()` and scan the list
   - Identify whether each discovery is already captured in an existing memory

3. **Write new or updated memories for anything NOT already captured:**

   **New architectural knowledge** → `architecture/<topic>`
   ```
   Serena.writeMemory({ memory_name: "architecture/topic", content: "..." })
   ```

   **Workflow or process discovery** → `workflows/<topic>`
   ```
   Serena.writeMemory({ memory_name: "workflows/topic", content: "..." })
   ```

   **Gotcha or footgun** → prefix with relevant system name, e.g. `gorm_batch_insert_gotcha`

   **Reference info** → `reference/<topic>`

4. **Update stale memories** — if a discovery CORRECTS an existing memory, update it:
   ```
   Serena.editMemory({ memory_name: "...", old_content: "...", new_content: "..." })
   ```

5. **Report:** Return a brief list of memories written/updated, and any decisions that didn't merit a memory (already in decisions.md).

## Scope discipline

- Only save what is **non-obvious** and **reusable across sessions** — not task-specific state
- Task progress → `plans/progress.md` (not memories)
- Architectural decisions with rationale → `plans/decisions.md` + memories for durable facts
- Ephemeral debugging steps → do NOT save
