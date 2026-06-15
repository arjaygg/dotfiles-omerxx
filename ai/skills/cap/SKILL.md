---
name: cap
description: >
  Cap v4.0 — One-shot autonomous orchestrator for Go, Python, and TypeScript. Drives stark
  (plan) → fury (tests) → ironman (implement) → hawk (review) via the Workflow tool.
  Deterministic, resumable, and visible in /workflows. Enforces TDD, Lean-Agile, DDD, SOLID,
  Evolutionary Architecture. Auto-detects language from project files (go.mod → Go,
  pyproject.toml → Python, tsconfig.json → TypeScript, multiple → polyglot).
  Use for: "build this feature", "implement end to end", "orchestrate this", "run cap",
  "full TDD cycle", "automate the workflow", "multi-agent workflow". NOT for planning only
  (use /stark), tests only (use /fury), implementing only (use /ironman), review only (/hawk).
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
version: 4.0.0
model: sonnet
allowed-tools:
  - Read
  - Workflow
  - advisor
---

# Cap v4.0 — Autonomous Orchestrator

Cap orchestrates the full development pipeline via the **Workflow tool**. You do not manually
drive agents — you parse args, invoke the Workflow, then review the result.

The workflow script encodes all orchestration deterministically: retry loops, schema-validated
handoffs, pipeline-based Hawk review, adversarial verify, and optional PushNotification.
Progress is visible in real-time via `/workflows`.

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

## Step 2 — Invoke the Workflow

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

## Step 3 — Post-Workflow Review (non-autonomous only)

After the Workflow returns, if `autonomous` is **false**:

Call `advisor()` with the workflow result for final sanity check:
- All 7 phases completed? (check `result.blocked` — false = success)
- No CRITICAL/HIGH findings remaining? (`result.criticalHighRemaining === 0`)
- Tests count reasonable for scope? (`result.testsCount`)
- Plan acceptance criteria met?

Report the advisor's verdict to the user.

If `autonomous` is **true**, the workflow's Finalize agent already sent a PushNotification.
Skip the advisor call and report the result summary directly.

---

## Step 4 — Report to User

```
Cap v4.0 — Done
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

If the workflow returned `blocked: true`, report the blocking reason and recommended action
(e.g. "Code health gate failed — run /cap --mode uplift first").

---

## Principles Enforced by the Workflow Script

All 6 principles are enforced via schema gates and agent instructions in `cap-workflow.js`:

1. **Test-First (TDD):** Fury writes failing tests before Ironman touches source
2. **Lean-Agile:** Minimum changes — only what's needed to pass tests
3. **DDD:** Scope agent identifies bounded context; all prompts reference it
4. **SOLID:** Stark and Ironman prompts enforce single-responsibility and interface-injection
5. **Evolutionary Architecture:** Extend patterns, no unnecessary abstractions
6. **Continuous Feedback:** Schema validation at every phase — invalid output retries, never proceeds
