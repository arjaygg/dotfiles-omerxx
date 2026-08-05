---
name: aside
description: Pause current task to answer a side question, then resume. Syntax: /aside <question>
---

# /aside — Side Question (Non-Blocking)

**Usage:** `/aside <question>`

Pause the current task to answer a side question without losing context, then automatically resume.

## Behavior

1. **Pause** — note the exact task state (current file, line, next action)
2. **Answer** — address `$argument` concisely; read-only access only (no file edits)
3. **Resume** — return to the paused task with a one-line reminder of where you left off

## Example

```
User: /aside is the approach we're taking thread-safe?

ASIDE: is the current approach thread-safe?
No — the shared cache object in src/cache/store.ts:34 is mutated without locking.
Under concurrent requests this is a race condition. Low risk in single-process Node.js
but would be a real problem with worker threads or clustering.

WARNING: This could affect the feature we're building. Want to address this now or
continue and fix it in a follow-up?
---
Resuming: adding the event handler in src/handler.ts
```

## Rules

- Never modify files during an aside — read-only access only
- The aside is a conversation pause, not a new task — the original task must always resume
- Keep answers focused: the goal is to unblock the user quickly, not deliver a lecture
- If an aside sparks a larger discussion, finish the current task first unless the aside reveals a blocker
- Asides are not saved to session files unless explicitly relevant to the task outcome
