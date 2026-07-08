---
name: cap
description: >
  Cap v4.1 — One-shot autonomous orchestrator for Go, Python, and TypeScript. Drives stark
  (plan) → fury (tests) → ironman (implement) → hawk (review). Uses Claude Code
  Workflows when that primitive is available, otherwise runs the same phases through a
  portable sequential fallback for agents such as Codex. Enforces TDD, Lean-Agile, DDD, SOLID,
  Evolutionary Architecture. Auto-detects language from project files (go.mod → Go,
  pyproject.toml → Python, tsconfig.json → TypeScript, multiple → polyglot).
  Use for: "build this feature", "implement end to end", "orchestrate this", "run cap",
  "full TDD cycle", "automate the workflow", "multi-agent workflow". NOT for planning-only,
  tests-only, implementing-only, or review-only requests — cap runs those phases inline
  (the standalone /stark, /fury, /ironman, /hawk skills are currently disabled).
triggers:
  - /cap
  - orchestrate
  - subagent driven development
  - multi-agent workflow
  - build this feature
  - implement end to end
  - run the full workflow
  - full TDD cycle
  - build and test
  - implement the whole thing
  - automate the workflow
  - cap workflow
  - do the full feature
  - stark fury ironman hawk
version: 4.1.0
model: sonnet
---

# Cap v4.1 — Adaptive Autonomous Orchestrator

Cap orchestrates the full development pipeline with the best primitive available in the
current coding agent.

- **Claude Code with Workflow support:** use the Workflow path for deterministic orchestration,
  retries, schema-validated handoffs, pipeline Hawk review, adversarial verify, resumability,
  and `/workflows` visibility.
- **Agents without Workflow support, including Codex:** use the portable path. Run the same
  Cap phases directly with the agent's native tools or subagents. Do not call `Workflow`,
  `advisor`, or `PushNotification` when those primitives are not available.

---

## Step 1 — Parse Arguments

From `$ARGUMENTS`, extract:

| Parameter | How to extract | Default |
|---|---|---|
| `feature` | Everything after stripping flags (--mode, --autonomous, --resume) | required |
| `mode` | `--mode <value>` | `feature` |
| `autonomous` | Presence of `--autonomous` flag | `false` |
| `resumeRunId` | `--resume <wf_xxx_id>` | none |

If `feature` is empty: ask the user for the feature description before proceeding.

---

## Step 2 — Select Runtime

Choose exactly one runtime before doing implementation work:

1. **Workflow runtime:** use only when the current agent exposes a callable `Workflow` tool or
   primitive in its available tool list.
2. **Portable runtime:** use when `Workflow` is absent, unknown, unsupported, or unavailable.

Do **not** probe by calling `Workflow` speculatively. If the tool is not clearly available,
assume the portable runtime.

Claude Code usually supports the Workflow runtime. Codex, Gemini, Cursor, and generic skill
hosts should be treated as portable unless their tool list explicitly includes Workflow.

---

## Step 3A — Workflow Runtime

Read the workflow script:

```
Read('ai/skills/cap/cap-workflow.js')
```

Pass it inline to the Workflow tool (inline `script:` is the safe first-invocation pattern):

```
Workflow({
  script: <content of cap-workflow.js>,
  args: {
    feature: "<parsed feature>",
    mode: "<feature|uplift>",
    autonomous: <true|false>,
  }
})
```

**For resume:** Use the `scriptPath` and run ID printed by a prior invocation:

```
Workflow({
  scriptPath: "<scriptPath from prior run>",
  resumeFromRunId: "<wf_xxx_id>",
  args: { feature: "...", mode: "...", autonomous: false }
})
```

Note: the Workflow tool prints `scriptPath` in its result — save it for the user so they can
use `--resume <runId>` in a future invocation without re-reading the script file.

---

## Step 3B — Portable Runtime

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

---

## Step 4 — Post-Run Review

After either runtime completes, if `autonomous` is **false** and `advisor` is available:

Call `advisor()` with the workflow result for final sanity check:
- All 7 phases completed? (check `result.blocked` — false = success)
- No CRITICAL/HIGH findings remaining? (`result.criticalHighRemaining === 0`)
- Tests count reasonable for scope? (`result.testsCount`)
- Plan acceptance criteria met?

Report the advisor's verdict to the user.

If `advisor` is unavailable, perform the same sanity check yourself and report the verdict.

If `autonomous` is **true** and the Workflow runtime was used, the workflow's Finalize agent
already sent a PushNotification. Skip the advisor call and report the result summary directly.

If `autonomous` is **true** in portable runtime, do not attempt PushNotification unless the host
agent explicitly provides it.

---

## Step 5 — Report to User

```
Cap v4.1 — Done
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Feature:   <feature>
Language:  <language>
Tests:     <testsCount> passing
Coverage:  <coveragePct>%
Findings:  <findingsResolved> resolved, 0 critical/high remaining
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Resume ID: <runId>  (use /cap --resume <runId> to replay)
Script:    <scriptPath>
```

For portable runtime, use:

```
Resume ID: n/a (portable runtime)
Script:    n/a (Workflow unavailable)
```

If the run returned `blocked: true`, report the blocking reason and recommended action
(e.g. "Code health gate failed — run /cap --mode uplift first").

---

## Principles Enforced

All 6 principles are enforced via Workflow schema gates when Workflow is available, or via the
portable runtime's phase contracts when it is not:

1. **Test-First (TDD):** Fury writes failing tests before Ironman touches source
2. **Lean-Agile:** Minimum changes — only what's needed to pass tests
3. **DDD:** Scope agent identifies bounded context; all prompts reference it
4. **SOLID:** Stark and Ironman prompts enforce single-responsibility and interface-injection
5. **Evolutionary Architecture:** Extend patterns, no unnecessary abstractions
6. **Continuous Feedback:** Schema validation at every phase — invalid output retries, never proceeds
