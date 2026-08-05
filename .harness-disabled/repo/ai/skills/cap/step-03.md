# Cap Step 3 — Portable Runtime

If a step says read fully and follow step-XX, you read and follow step-XX. No exceptions.

Use this path for Codex and any agent that does not expose Workflow.

Read the reusable phase prompts before starting:

```
Read('ai/skills/cap/references/stark-prompt.md')
Read('ai/skills/cap/references/fury-prompt.md')
Read('ai/skills/cap/references/ironman-prompt.md')
Read('ai/skills/cap/references/hawk-prompt.md')
Read('ai/skills/cap/references/schemas.md')
```

Then run the Cap phases sequentially. If the host agent supports subagents, delegate each phase
to the best matching native subagent. If it does not, execute the phase yourself in the current
session while preserving the same deliverables and schema checks.

1. **Scope:** parse feature, mode, acceptance criteria, affected packages, language, and bounded
   context. Save the working context in `plans/active-context.md`.
2. **Preflight:** unless `mode=uplift`, inspect code health enough to decide whether feature work
   is reasonable. If the codebase is too unhealthy to proceed, stop and recommend `/cap --mode uplift`.
3. **Stark:** create or update the architecture plan in `plans/active-context.md` using the Stark
   prompt and `PLAN_SCHEMA`.
4. **Fury:** write failing tests first using the Fury prompt and `TEST_SCHEMA`. Verify they fail
   for the intended behavioral reason.
5. **Ironman:** implement the minimum code needed for tests to pass using the Ironman prompt and
   `IMPL_SCHEMA`.
6. **Hawk:** review changed files across architecture, quality, resilience, and security using
   the Hawk prompt and `REVIEW_SCHEMA`.
7. **Fix loop:** address all CRITICAL/HIGH findings, then rerun relevant tests and review checks.
   Continue until none remain or a real blocker is found.
8. **Finalize:** report results using the standard Cap summary. Set resume fields to `n/a`
   because portable runs do not have Workflow run IDs or script paths.

Portable resume behavior:
- If `--resume <wf_xxx_id>` is provided without Workflow support, explain that Workflow replay is
  unavailable in this agent.
- Continue from the current repo state and `plans/active-context.md` when present.
- Do not invent a Workflow run ID.

Portable validation rules:
- Treat the schemas in `references/schemas.md` as self-check contracts.
- Never proceed from a phase with `valid: false` unless the next action directly fixes its issues.
- Preserve TDD: tests before implementation.
- Preserve minimum-change discipline: avoid unrelated refactors.

## Next

Read fully and follow **step-04.md** (Post-Run Review).
