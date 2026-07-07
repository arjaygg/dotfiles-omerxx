# Cap v4.0 — Autonomous One-Shot Rewrite Plan

## Context

Cap v3.2.0 is a capable orchestrator but not truly autonomous. It is implemented as a ~430-line SKILL.md
monolith where Claude reads prose instructions and manually drives Stark → Fury → Ironman → Hawk by
calling `Agent()` interactively. This means:

- Control flow lives in the model's reasoning, not in deterministic code — it can drift under compaction
- Subagents are spawned without the pctx/Serena init mandate, so they hit hook-blocks (Bash grep/cat blocked) and silently fail
- Handoffs between phases are prose + files — no schema, no typed validation
- Hawk's 4 adversarial agents are told to "read peer messages" — a tool that doesn't exist
- No Workflow tool usage anywhere in the repo means no resume, no journal, no phase progress in `/workflows`
- No PushNotification, no Monitor post-commit — user can't walk away

The user's ask: **truly one-shot and autonomous** — invoke `/cap build the login feature` and walk away.

---

## Approach: Workflow-First Cap v4.0

Cap's SKILL.md becomes a **thin entry point** (~80 lines) that parses `$ARGUMENTS` and instructs
the orchestrator to call `Workflow({script: <inline cap-workflow.js content>, args: {feature, mode, autonomous}})`.

The workflow script (`cap-workflow.js`) encodes the full orchestration pipeline using the
`Workflow` tool's primitives — `phase()`, `pipeline()`, `parallel()`, `log()`, `agent()` with
`schema` — so execution is deterministic, resumable via journal, and visible in `/workflows`.

This is the first use of the Workflow tool in this repo. All prior orchestration used hand-rolled
`Agent()` calls in SKILL.md prose.

### Known Assumptions Requiring First-Run Verification

Three mechanics are untested before implementation. Document as explicit risks so the fallback is clear:

| Assumption | Risk | Fallback |
|---|---|---|
| `Workflow({script: inline})` works when SKILL.md instructs the orchestrator to pass cap-workflow.js content inline | Low — this is the documented-safe pattern | If it can't pass ~350-line string, split into smaller phased scripts |
| `Workflow({scriptPath: 'ai/skills/cap/cap-workflow.js'})` works for re-invocations (resume/iterate) | Medium — spec examples use session-persisted paths | Use the session-dir path Workflow prints after first run |
| Workflow subagents can reach the `advisor()` tool | **High — advisor() is NOT in the Workflow script API** (only `agent/parallel/pipeline/log/phase/workflow/args/budget`). Subagents CAN reach MCP tools via ToolSearch, but advisor is not an MCP tool. | **Don't use advisor() inside the workflow script at all** — see Step 5 |

---

## Step 1 — Thin SKILL.md Entry Point

**Files:** `ai/skills/cap/SKILL.md`

Rewrite from 430 lines to ~80 lines. Keep:
- frontmatter (`desc`, `version: 4.0.0`, `model: opus`, `triggers`, `allowed-tools`)
- Argument parsing: `--mode feature|uplift`, `--autonomous`
- Single instruction block: "parse $ARGUMENTS, then call `Workflow({scriptPath: 'ai/skills/cap/cap-workflow.js', args: {...}})`"

Remove: all inline Stark/Fury/Ironman/Hawk prose instructions (moving to workflow script + references/).

**Accepts:** SKILL.md is ≤100 lines and contains a single `Workflow(scriptPath...)` invocation instruction.

---

## Step 2 — cap-workflow.js (Core Pipeline)

**Files:** `ai/skills/cap/cap-workflow.js` (new, ~350 lines)

### meta block
```js
export const meta = {
  name: 'cap-feature-workflow',
  description: 'End-to-end TDD feature workflow: scope → health → plan → tests → implement → review → finalize',
  phases: [
    { title: 'Scope',      detail: 'Define feature scope and acceptance criteria' },
    { title: 'Preflight',  detail: 'Code health gate on in-scope files' },
    { title: 'Plan',       detail: 'Stark writes architectural plan' },
    { title: 'Tests',      detail: 'Fury writes failing tests' },
    { title: 'Implement',  detail: 'Ironman makes tests pass' },
    { title: 'Review',     detail: 'Hawk: 4-dimension parallel adversarial review' },
    { title: 'Finalize',   detail: 'Full suite + race detector + PushNotification' },
  ],
}
```

### 7 Structured Schemas (enforced via schema option on every agent() call)

```js
const SCOPE_SCHEMA = {
  type: 'object', required: ['feature', 'criteria', 'affectedPkgs', 'boundedContext', 'ready'],
  properties: {
    feature:         { type: 'string' },
    criteria:        { type: 'array', items: { type: 'string' } },
    affectedPkgs:    { type: 'array', items: { type: 'string' } },
    boundedContext:  { type: 'string' },
    ready:           { type: 'boolean' },
    clarifyQuestion: { type: 'string' },  // set if ready=false
  }
}
// HEALTH_SCHEMA, PLAN_SCHEMA, TEST_SCHEMA, IMPL_SCHEMA, REVIEW_SCHEMA, VERDICT_SCHEMA
// all defined similarly — see references/schemas.md
```

### Phase pipeline

```js
// Scope (uses haiku for speed — pure classification task)
phase('Scope')
const scope = await agent(scopePrompt(args.feature), { schema: SCOPE_SCHEMA, model: 'haiku' })
if (!scope.ready) { log(`Scope unclear: ${scope.clarifyQuestion}`); return { blocked: true } }

// Preflight (feature mode only)
phase('Preflight')
if (args.mode !== 'uplift') {
  const health = await agent(healthPrompt(scope.affectedPkgs), { schema: HEALTH_SCHEMA })
  if (!health.passed) {
    log(`Health gate FAILED (${health.score}/10). Run /cap --mode uplift first.`)
    return { blocked: true, reason: 'health-gate', score: health.score }
  }
}

// Plan — with retry on gate failure
phase('Plan')
let plan = await agent(starkPrompt(scope), { schema: PLAN_SCHEMA })
if (!plan.valid) {
  log(`Plan gate failed. Retrying Stark: ${plan.feedback}`)
  plan = await agent(starkPrompt(scope, plan.feedback), { schema: PLAN_SCHEMA })
}

// Tests
phase('Tests')
let tests = await agent(furyPrompt(plan), { schema: TEST_SCHEMA })
if (!tests.ready) {
  log(`Tests not ready: ${tests.failureReason}. Retrying Fury.`)
  tests = await agent(furyPrompt(plan, tests.failureReason), { schema: TEST_SCHEMA })
}

// Implement
phase('Implement')
let impl = await agent(ironmanPrompt(plan, tests), { schema: IMPL_SCHEMA })
if (!impl.ready) {
  log('Impl gate failed. Retrying Ironman.')
  impl = await agent(ironmanPrompt(plan, tests, impl.failureLog), { schema: IMPL_SCHEMA })
}

// Review — 4-dimension parallel pipeline with adversarial verify per finding
phase('Review')
const REVIEW_DIMS = ['security', 'correctness', 'test-quality', 'resilience']
const reviewResults = await pipeline(
  REVIEW_DIMS,
  dim => agent(hawkDimPrompt(dim, plan, impl), { schema: REVIEW_SCHEMA, phase: 'Review' }),
  result => parallel(result.findings.map(f => () =>
    agent(verifyFindingPrompt(f), { schema: VERDICT_SCHEMA, phase: 'Review' })
      .then(v => ({ ...f, verified: v.isReal }))
  ))
)
const confirmed = reviewResults.flat().filter(Boolean).filter(f => f.verified)
const criticalHigh = confirmed.filter(f => ['CRITICAL','HIGH'].includes(f.severity))

if (criticalHigh.length > 0) {
  log(`${criticalHigh.length} CRITICAL/HIGH findings — sending Ironman back.`)
  impl = await agent(ironmanFixPrompt(plan, tests, criticalHigh), { schema: IMPL_SCHEMA })

  // Re-review after fix — loop-until-clean (max 1 re-review pass, matching v3.2.0 behavior)
  log('Re-reviewing after fix pass...')
  const reReviewResults = await pipeline(
    REVIEW_DIMS,
    dim => agent(hawkDimPrompt(dim, plan, impl), { schema: REVIEW_SCHEMA, phase: 'Review' }),
    result => parallel(result.findings.map(f => () =>
      agent(verifyFindingPrompt(f), { schema: VERDICT_SCHEMA, phase: 'Review' })
        .then(v => ({ ...f, verified: v.isReal }))
    ))
  )
  const reConfirmed = reReviewResults.flat().filter(Boolean).filter(f => f.verified)
  const stillCritical = reConfirmed.filter(f => ['CRITICAL','HIGH'].includes(f.severity))
  if (stillCritical.length > 0) {
    log(`WARNING: ${stillCritical.length} CRITICAL/HIGH findings remain after fix pass. Escalate.`)
    return { blocked: true, reason: 'review-gate', findings: stillCritical }
  }
}

// Finalize
phase('Finalize')
log(`Feature complete. Coverage: ${impl.coverage}%. Confirmed findings: ${confirmed.length}.`)
return { feature: scope.feature, testsPass: impl.testsPass, raceClean: impl.raceClean,
         coverage: impl.coverage, confirmedFindings: confirmed }
```

**Accepts:** `cap-workflow.js` exists, meta block is a pure literal, all 7 schemas defined, all
7 phases have correct `phase()` calls, pipeline() handles Hawk review.

---

## Step 3 — Fresh Agent Init Mandate in All Subagent Prompts

**Files:** Prompt helper functions within `cap-workflow.js`

Every `agent()` prompt string must start with the pctx init mandate block so fresh subagents
don't hit the `pre-tool-gate-v2.sh` hook that blocks Bash grep/cat before Serena init:

```
MANDATORY SESSION INIT (run before accessing any project files):
Call mcp__pctx__execute_typescript with a script that calls:
  Promise.all([Serena.initialInstructions(), LeanCtx.ctxCall({name:"ctx_intent", arguments:{query:"<task>"}})])
```

This applies to all 6 prompt helpers: `starkPrompt`, `furyPrompt`, `ironmanPrompt`,
`hawkDimPrompt`, `healthPrompt`, `ironmanFixPrompt`.

**Accepts:** Each prompt helper begins with the init mandate block verbatim.

---

## Step 4 — Extract Subagent Prompts to References

**Files:**
- `ai/skills/cap/references/stark-prompt.md` (new — extracted from old SKILL.md Step 2)
- `ai/skills/cap/references/fury-prompt.md` (new — extracted from old SKILL.md Step 3)
- `ai/skills/cap/references/ironman-prompt.md` (new — extracted from old SKILL.md Step 4)
- `ai/skills/cap/references/hawk-prompt.md` (new — extracted from old SKILL.md Step 5)
- `ai/skills/cap/references/schemas.md` (new — schema documentation for humans)

The prose prompt bodies from old SKILL.md move into these files. In `cap-workflow.js`, each
prompt helper interpolates scope/plan/tests/findings into the template string:

```js
// cap-workflow.js
function starkPrompt(scope, feedback) {
  return `${STARK_PROMPT_TEMPLATE}

Feature: ${scope.feature}
Criteria:\n- ${scope.criteria.join('\n- ')}
Affected packages: ${scope.affectedPkgs.join(', ')}
Bounded context: ${scope.boundedContext}
${feedback ? `\nFeedback from prior attempt: ${feedback}` : ''}`;
}
```

`STARK_PROMPT_TEMPLATE` etc. are string constants at the top of the file containing the
verbatim prompt body from the old SKILL.md (keeping DDD/SOLID/TDD enforcement instructions).

**Accepts:** `references/` has 5 files; prompts in workflow script are interpolated templates,
not inline prose monoliths.

---

## Step 5 — Autonomous Mode + PushNotification

**Files:** `ai/skills/cap/SKILL.md` (arg parsing), `ai/skills/cap/cap-workflow.js` (Finalize phase)

**Critical distinction:** `--autonomous` affects quality gates and notifications — NOT whether the
workflow runs in background (Workflow is always non-blocking structurally). These are separate axes.

| Axis | Default | `--autonomous` |
|---|---|---|
| Background execution | Always (Workflow is non-blocking) | Same |
| Quality gates (schema validation) | Always enforced | Always enforced — these are never skipped |
| Advisor checkpoints | One checkpoint **in main session** after workflow returns | Skipped |
| PushNotification on completion | Off | On |

**What this means for cap-workflow.js:**
- `advisor()` is **not available inside Workflow scripts** (not in the script API: `agent/parallel/pipeline/log/phase/workflow/args/budget`). Remove all advisor() calls from the script entirely.
- The one advisor checkpoint lives in SKILL.md's post-invocation block — after `Workflow({...})` returns, the main-session orchestrator reads the result and calls `advisor()` if not `--autonomous`.

```js
// In cap-workflow.js Finalize phase — PushNotification via subagent
phase('Finalize')
const finalize = await agent(finalizePrompt(impl, args.autonomous), {label: 'finalize'})
// autonomous=true: finalize agent includes PushNotification call in its instructions
```

```markdown
<!-- In SKILL.md entry point — AFTER Workflow invocation -->
If not --autonomous, call advisor() with the workflow result for final quality review.
```

**SKILL.md arg parsing:** `autonomous: ARGUMENTS.includes('--autonomous')` → passed as `args`.

**Accepts:** Default (no flag): workflow runs, then `advisor()` in main session reviews results.
`--autonomous`: no advisor checkpoint, PushNotification fires when Finalize completes.

---

## Step 6 — Fix Hawk's Broken Cross-Agent Messaging

**Files:** `ai/skills/hawk/SKILL.md`

Remove the "read peer messages from other agents" contract in adversarial mode — the tool doesn't
exist (no MCP inter-agent messaging in Claude Code). Cap's `pipeline()` already handles aggregation
by collecting `REVIEW_SCHEMA` output from all 4 dimension agents and deduplicating in JavaScript.

Update Hawk SKILL.md to document the new reality:
> Each dimension agent returns structured REVIEW_SCHEMA findings. Cap aggregates, deduplicates
> (by file+line±3), and runs adversarial verify per unique finding. No inter-agent messaging needed.

**Accepts:** Hawk SKILL.md has no reference to "read peer messages"; documents pipeline-aggregation.

---

## What Stays the Same

- All 6 enforcement principles: TDD, Lean-Agile, DDD, SOLID, Evolutionary Architecture, CI Feedback
- Phase ordering: scope → preflight → plan → tests → implement → review → finalize
- Code health gate (9.5 in feature mode, skipped in uplift)
- `plans/active-context.md` as shared plan artifact
- Coverage regression detection (surfaced in Hawk findings)
- `--mode feature|uplift` flag semantics

---

## New Capabilities Gained

| Capability | How |
|---|---|
| **Resumable** | Workflow journal — `Workflow({scriptPath, resumeFromRunId})` |
| **Visible progress** | `/workflows` shows live 7-phase tree |
| **Typed handoffs** | `schema` option enforces structured output per phase |
| **Parallel review** | `pipeline()` over 4 Hawk dimensions — wall-clock = slowest single dimension |
| **Adversarial verify** | Every confirmed finding gets a refutation attempt before reporting |
| **Init mandate** | Fresh subagents get pctx init — no hook-block surprises |
| **One-shot autonomous** | Workflow handles full pipeline without model babysitting |
| **PushNotification** | Desktop notify on completion |
| **Budget-aware** | `budget.remaining()` can scale review depth in future |

---

## Files Changed

| File | Change |
|---|---|
| `ai/skills/cap/SKILL.md` | Rewrite — thin entry ~80 lines |
| `ai/skills/cap/cap-workflow.js` | New — ~350 lines |
| `ai/skills/cap/references/stark-prompt.md` | New |
| `ai/skills/cap/references/fury-prompt.md` | New |
| `ai/skills/cap/references/ironman-prompt.md` | New |
| `ai/skills/cap/references/hawk-prompt.md` | New |
| `ai/skills/cap/references/schemas.md` | New |
| `ai/skills/hawk/SKILL.md` | Minor — remove broken messaging contract |

All changes isolated to `ai/skills/cap/` and `ai/skills/hawk/`. No hooks, rules, or settings touched.

---

## Verification

> **Note:** `cap-workflow.js` cannot be syntax-checked with `node --input-type=module` — `phase`, `agent`, `pipeline` are runtime-injected globals that Node doesn't know about. Testing requires a live Workflow invocation.

1. **Schema correctness:** Read all 7 schemas manually — verify `required` arrays and `type` fields before running
2. **First-run test (trivial feature):** `/cap add a debug log statement to ai/skills/cap/SKILL.md` — confirm `/workflows` shows 7-phase progress tree
3. **Structured output:** Inspect workflow result — Scope phase must return SCOPE_SCHEMA object (not prose)
4. **Init mandate check:** Verify each subagent prompt string starts with the pctx init block
5. **Resume:** Start a real run, interrupt mid-Implement phase, re-invoke with `resumeFromRunId` — Scope/Plan/Tests phases must return from cache
6. **Re-review loop:** Force a CRITICAL finding (mock or real) — confirm Ironman is sent back and re-review runs
7. **Autonomous flag:** `/cap --autonomous add debug log` — verify no advisor() prompt appears, PushNotification fires at Finalize
8. **scriptPath re-invoke:** After first run, note the persisted script path from Workflow output; re-invoke with `scriptPath:` that path to verify resume works
