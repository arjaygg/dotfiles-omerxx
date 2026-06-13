export const meta = {
  name: 'cap-v4',
  description: 'Cap v4.0 — Autonomous TDD orchestrator: Scope → Preflight → Plan → Tests → Implement → Review → Finalize',
  phases: [
    { title: 'Scope',     detail: 'Parse feature, identify bounded context and affected packages' },
    { title: 'Preflight', detail: 'Code health gate ≥9.5 on affected packages (feature mode)' },
    { title: 'Plan',      detail: 'Stark writes architectural plan to plans/active-context.md' },
    { title: 'Tests',     detail: 'Fury writes failing tests for all plan components' },
    { title: 'Implement', detail: 'Ironman makes all tests pass, race detector clean' },
    { title: 'Review',    detail: 'Hawk reviews 4 dimensions in parallel, adversarial verify' },
    { title: 'Finalize',  detail: 'Full test suite + race detector pass, optional PushNotification' },
  ],
}

// ── Schemas ───────────────────────────────────────────────────────────────────

const SCOPE_SCHEMA = {
  type: 'object',
  required: ['feature', 'deliverable', 'criteria', 'affectedPkgs', 'boundedContext', 'mode'],
  properties: {
    feature:        { type: 'string' },
    deliverable:    { type: 'string' },
    criteria:       { type: 'array', items: { type: 'string' } },
    affectedPkgs:   { type: 'array', items: { type: 'string' } },
    boundedContext: { type: 'string' },
    mode:           { type: 'string', enum: ['feature', 'uplift'] },
  },
}

const HEALTH_SCHEMA = {
  type: 'object',
  required: ['score', 'passed', 'worstFiles'],
  properties: {
    score:      { type: 'number' },
    passed:     { type: 'boolean' },
    worstFiles: { type: 'array', items: { type: 'string' } },
  },
}

const PLAN_SCHEMA = {
  type: 'object',
  required: ['planPath', 'components', 'interfaces', 'criteriaCount', 'valid'],
  properties: {
    planPath:      { type: 'string' },
    components:    { type: 'array', items: { type: 'string' } },
    interfaces:    { type: 'array', items: { type: 'string' } },
    criteriaCount: { type: 'number' },
    valid:         { type: 'boolean' },
    issues:        { type: 'array', items: { type: 'string' } },
  },
}

const TEST_SCHEMA = {
  type: 'object',
  required: ['testFiles', 'testCount', 'allFailing', 'valid'],
  properties: {
    testFiles:  { type: 'array', items: { type: 'string' } },
    testCount:  { type: 'number' },
    allFailing: { type: 'boolean' },
    valid:      { type: 'boolean' },
    issues:     { type: 'array', items: { type: 'string' } },
  },
}

const IMPL_SCHEMA = {
  type: 'object',
  required: ['testsPassed', 'raceClean', 'changedFiles', 'valid'],
  properties: {
    testsPassed:  { type: 'boolean' },
    raceClean:    { type: 'boolean' },
    changedFiles: { type: 'array', items: { type: 'string' } },
    coveragePct:  { type: 'number' },
    valid:        { type: 'boolean' },
    issues:       { type: 'array', items: { type: 'string' } },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  required: ['dimension', 'findings'],
  properties: {
    dimension: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'category', 'file', 'line', 'description', 'fix', 'confidence'],
        properties: {
          severity:    { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
          category:    { type: 'string' },
          file:        { type: 'string' },
          line:        { type: 'number' },
          description: { type: 'string' },
          fix:         { type: 'string' },
          confidence:  { type: 'number' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['isReal', 'reasoning'],
  properties: {
    isReal:           { type: 'boolean' },
    reasoning:        { type: 'string' },
    adjustedSeverity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
  },
}

// ── Init block injected into every fresh subagent prompt ─────────────────────

function pctxInit(taskDesc) {
  return `
PCTX INIT REQUIRED (run before any Read, Grep, Glob, or Serena call):
1. Use ToolSearch to load: mcp__pctx__list_functions, mcp__pctx__execute_typescript
2. Call mcp__pctx__list_functions
3. Call mcp__pctx__execute_typescript with:
   async function run() {
     const [, ] = await Promise.all([
       Serena.initialInstructions(),
       LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "${taskDesc}" } })
     ]);
     return { ready: true };
   }
Without steps 1-3, Grep will be blocked by the pre-tool-gate hook.
`.trim()
}

// ── Prompt helpers ────────────────────────────────────────────────────────────

function scopePrompt(feature, mode) {
  return `${pctxInit('cap scope analysis')}

You are Cap's scoping assistant. Analyze the following feature request and return structured scope.

Feature request: "${feature}"
Mode hint: "${mode}"

Instructions:
- Load project architecture via Serena.readMemory("project_architecture_and_patterns") first
- Identify the DDD bounded context and affected Go packages (e.g. pkg/scheduler)
- List 3-7 concrete acceptance criteria as verifiable checkboxes
- Set mode to "${mode}" (override to "feature" if not "uplift")

Return SCOPE_SCHEMA JSON only.`
}

function preflightPrompt(scope) {
  return `${pctxInit('cap preflight code health gate')}

You are Cap's preflight checker. Run the code health gate on the affected packages and report results.

Affected packages: ${scope.affectedPkgs.join(', ')}

Instructions:
- Run: claude /code-health --gate 9.5 ${scope.affectedPkgs.join(' ')}
- If the command is unavailable, run: make code-health-json 2>/dev/null | head -30
- Parse the score from the output
- List the worst 3 files by score if gate fails

Return HEALTH_SCHEMA JSON only.`
}

function starkPrompt(scope, feedback) {
  return `${pctxInit('stark architectural planning for ' + scope.feature)}

You are Stark, the Architect. Write a complete architectural plan to plans/active-context.md.

Feature: "${scope.feature}"
Deliverable: ${scope.deliverable}
Acceptance criteria:
${scope.criteria.map(c => `- ${c}`).join('\n')}
Affected packages: ${scope.affectedPkgs.join(', ')}
Bounded context: ${scope.boundedContext}
${feedback && feedback.length > 0 ? `\nFeedback from prior attempt — fix these:\n${feedback.map(i => `- ${i}`).join('\n')}` : ''}

Instructions:
- Load project architecture via Serena.readMemory("project_architecture_and_patterns") first
- Apply DDD: identify aggregates, value objects, domain events
- Apply SOLID: single responsibility, inject dependencies via interfaces
- Extend existing patterns — no new abstractions without necessity (Evolutionary Architecture)
- Write to plans/active-context.md with sections:
  * Context (domain, bounded context, why)
  * Components (explicit file paths, type names, function signatures — zero placeholders)
  * Interfaces (all new interfaces with method signatures)
  * Testing Strategy (behaviors to test, edge cases, table-driven examples)
  * Error Handling (error types, wrapping, user-facing messages)
  * Acceptance Criteria (checkboxes)

Return PLAN_SCHEMA JSON. Set valid=false and list issues if any section is incomplete or has placeholders.`
}

function furyPrompt(scope, plan, feedback) {
  return `${pctxInit('fury test writing for ' + scope.feature)}

You are Fury, the QA agent. Write failing tests for all components in the plan.

Plan: plans/active-context.md (read it first)
Components to test: ${plan.components.join(', ')}
Feature: "${scope.feature}"
${feedback && feedback.length > 0 ? `\nFeedback from prior attempt:\n${feedback.map(i => `- ${i}`).join('\n')}` : ''}

Instructions:
- Read plans/active-context.md before writing any tests
- Write tests FIRST in <package>_test.go — never touch implementation files
- BDD structure: Given-When-Then (Arrange, Act, Assert)
- Table-driven tests for multiple scenarios
- Cover edge cases: nil inputs, boundaries, concurrent access, error paths
- Go: use require (not assert), t.Run() for subtests, t.Parallel() for concurrent-safe tests
- Run go test ./... — verify each fails for the right reason (NOT a compile error)

Success condition: ALL tests must FAIL (they are pre-implementation — passing means a bug).

Return TEST_SCHEMA JSON. Set valid=false and list issues if any component lacks coverage or tests don't fail correctly.`
}

function ironmanPrompt(scope, plan, tests, findings) {
  const fixPassHeader = findings
    ? `This is a FIX PASS. Address these Hawk review findings FIRST:\n${findings.map(f => `- [${f.severity}] ${f.file}:${f.line} — ${f.description}\n  Fix: ${f.fix}`).join('\n')}\n`
    : ''
  return `${pctxInit('ironman implementation for ' + scope.feature)}

You are Ironman, the Implementation Agent. Make the failing tests pass.
${fixPassHeader}
Plan: plans/active-context.md (read it first)
Failing tests: ${tests.testFiles.join(', ')}
Feature: "${scope.feature}"

Instructions:
- Read plan and all test files before touching source
- Implement MINIMAL changes — only what's needed for tests to pass${findings ? ' and findings to be fixed' : ''}
- DDD: aggregates in domain layer, repos in infrastructure layer, domain events for side effects
- SOLID: single responsibility, inject via interfaces
- Do NOT refactor beyond what's in the plan
- Run after each component: go test -v ./path/to/package
- When all unit tests pass: go test -race ./...
- Capture coverage: go test ./... -coverprofile=/tmp/cap-cov.out && go tool cover -func=/tmp/cap-cov.out | grep total

Return IMPL_SCHEMA JSON. Set valid=false if any test fails or race detector reports issues.`
}

function hawkDimPrompt(dim, scope, impl) {
  const files = impl.changedFiles.join(', ')
  return `${pctxInit('hawk ' + dim.key + ' review')}

You are a Go code reviewer focusing on ${dim.label}. Review the changed files below.

Changed files: ${files}
Feature context: "${scope.feature}"

${dim.checks}

Tool priority: ${dim.toolPriority}

Return REVIEW_SCHEMA JSON: { dimension: "${dim.key}", findings: [...] }
Each finding must include severity, category, file, line, description, fix, and confidence (0-1).`
}

function verifyFindingPrompt(finding) {
  return `${pctxInit('adversarial verify hawk finding')}

You are an adversarial verifier. Your job is to REFUTE the following finding if it is a false positive.
Default to isReal=false if you are uncertain.

Finding to verify:
- Severity: ${finding.severity}
- Category: ${finding.category}
- File: ${finding.file}:${finding.line}
- Description: ${finding.description}
- Proposed fix: ${finding.fix}
- Original confidence: ${finding.confidence}

Instructions:
- Read the file at ${finding.file} (lines around ${finding.line}) to check the claim
- Is the issue actually present in the code? Could parameterization already exist in a non-obvious form?
- Is the severity correctly calibrated?
- If the finding is real, set isReal=true and optionally adjustedSeverity if severity is wrong
- If refuting, explain specifically what the reviewer got wrong

Return VERDICT_SCHEMA JSON.`
}

function finalizePrompt(scope, impl, confirmed, autonomous) {
  return `${pctxInit('cap finalize and commit')}

You are Cap's finalization agent. Run the final verification sequence and commit.

Feature: "${scope.feature}"
Changed files: ${impl.changedFiles.join(', ')}
Confirmed findings (all should be resolved): ${confirmed.length === 0 ? 'none' : confirmed.map(f => f.description).join(', ')}

Instructions:
1. Run: go test ./... (confirm all tests pass)
2. Run: go test -race ./... (confirm race detector clean)
3. Run: go test -cover ./... (capture final coverage)
4. Run: git status (verify all changes are tracked)
5. Use /smart-commit to create a conventional commit with the feature description
${autonomous ? '6. Use PushNotification to send a desktop notification: "Cap v4.0 complete: ' + scope.feature + '"' : ''}

Report: "Finalize complete. Tests: N passing. Coverage: X%. Commit: <hash>."`
}

// ── Deduplication helper ──────────────────────────────────────────────────────

function dedupeFindings(allFindings) {
  const seen = new Map()
  for (const f of allFindings) {
    const locKey = `${f.file}:${Math.round(f.line / 3)}`
    const semKey = `${f.file}:${f.category}:${f.description.toLowerCase().slice(0, 20)}`
    const existing = seen.get(locKey) || seen.get(semKey)
    if (existing) {
      const sev = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
      if (sev.indexOf(f.severity) < sev.indexOf(existing.severity)) {
        seen.set(locKey, f)
        seen.set(semKey, f)
      }
    } else {
      seen.set(locKey, f)
      seen.set(semKey, f)
    }
  }
  return [...new Set(seen.values())]
}

// ── Review dimension definitions ──────────────────────────────────────────────

const REVIEW_DIMS = [
  {
    key: 'architecture',
    label: 'Architecture',
    toolPriority: 'Serena.findSymbol → Serena.findReferencingSymbols → Serena.getSymbolsOverview → Grep',
    checks: `Checks:
1. Repository pattern violation: Direct DB/GORM access outside pkg/repo/ → HIGH
2. Missing factory constructor: Exported struct instantiated with {} outside tests → MEDIUM
3. K8s manifest in wrong repo: *.yaml with kind: Deployment|Service → HIGH
4. OSS compliance: Raw prometheus.io/client_golang without internal wrapper → HIGH
5. Circular imports: Packages importing each other → CRITICAL
6. Downstream blast radius: Changed interface used by downstream packages → MEDIUM`,
  },
  {
    key: 'quality',
    label: 'Quality',
    toolPriority: 'Serena.getSymbolsOverview → Serena.findReferencingSymbols → Grep',
    checks: `Checks:
1. Missing table-driven tests: Repeated t.Run() without a slice of test cases → MEDIUM
2. Missing godoc: Exported symbols without documentation comments → LOW (interface methods → MEDIUM)
3. Error handling: fmt.Errorf/errors.New without project error constructors → MEDIUM
4. Cognitive complexity: Nesting depth >4 → MEDIUM; >6 → HIGH
5. Dead code/unused params: _ param or clearly unused variables → LOW
6. Code health score: make code-health-json | scorer 0 — severity by score band`,
  },
  {
    key: 'resilience',
    label: 'Resilience',
    toolPriority: 'Serena.findSymbol → Serena.findReferencingSymbols → Grep',
    checks: `Checks:
1. Missing circuit breaker: New HTTP/DB/K8s calls without circuit breaker wrapping → HIGH
2. Goroutine leaks: go func(...) without context cancellation or done channel → HIGH
3. Context not propagated: Side-effect functions without ctx context.Context first param → MEDIUM
4. Hardcoded timeouts: time.Duration literals not sourced from config → MEDIUM
5. Missing graceful shutdown: New long-running goroutines not in shutdown handler → HIGH
6. Downstream cascade risk: Changed functions called by scheduler/worker pool → MEDIUM`,
  },
  {
    key: 'security',
    label: 'Security',
    toolPriority: 'Serena.getSymbolsOverview → Grep → Serena.findReferencingSymbols',
    checks: `Checks:
1. SQL injection: gorm.Raw/db.Exec with string concatenation or fmt.Sprintf with user input → CRITICAL
2. Missing auth middleware: New HTTP routes without middleware → HIGH
3. Hardcoded secrets: Connection strings, passwords, API keys in non-test source → CRITICAL
4. Missing request validation: json.Decode(r.Body) without post-decode validation → HIGH
5. Unsafe type assertions: x.(Type) without comma-ok pattern → MEDIUM
6. Govulncheck: Run if mcp__mcp_gopls__govulncheck available → CRITICAL if found`,
  },
]

// ── Main orchestration ────────────────────────────────────────────────────────

const { feature, mode = 'feature', autonomous = false } = args || {}

if (!feature) {
  log('ERROR: args.feature is required. Pass feature description via args.')
  return { error: 'missing-feature' }
}

// Phase 1 — Scope
phase('Scope')
log(`Scoping: "${feature}" (mode: ${mode})`)
const scope = await agent(scopePrompt(feature, mode), { label: 'scope', schema: SCOPE_SCHEMA })
if (!scope) return { error: 'scope-agent-failed' }
log(`Scope: ${scope.affectedPkgs.join(', ')} | context: ${scope.boundedContext} | criteria: ${scope.criteriaCount || scope.criteria.length}`)

// Phase 2 — Preflight (feature mode only)
phase('Preflight')
let health = { score: 10, passed: true, worstFiles: [] }
if (scope.mode === 'feature') {
  log(`Running code health gate on: ${scope.affectedPkgs.join(', ')}`)
  health = await agent(preflightPrompt(scope), { label: 'preflight', schema: HEALTH_SCHEMA })
  if (!health) return { error: 'preflight-agent-failed' }
  if (!health.passed) {
    log(`⚠️  Code health gate FAILED (score: ${health.score}/10 < 9.5). Worst files: ${health.worstFiles.join(', ')}`)
    log('Recommended: run /cap --mode uplift to refactor first, then retry /cap (feature mode).')
    return { blocked: true, reason: 'health-gate', score: health.score, worstFiles: health.worstFiles }
  }
  log(`Code health: ${health.score}/10 — gate passed`)
} else {
  log('Uplift mode — preflight gate skipped')
}

// Phase 3 — Plan (with retry loop)
phase('Plan')
let plan = null
let planAttempt = 0
while (!plan || !plan.valid) {
  planAttempt++
  if (planAttempt > 3) {
    log('Plan validation failed 3 times. Aborting.')
    return { blocked: true, reason: 'plan-validation', issues: plan ? plan.issues : [] }
  }
  const label = planAttempt > 1 ? `stark:retry-${planAttempt}` : 'stark'
  if (planAttempt > 1) log(`Plan retry ${planAttempt}: ${plan.issues.join(', ')}`)
  plan = await agent(starkPrompt(scope, plan ? plan.issues : null), { label, schema: PLAN_SCHEMA })
  if (!plan) return { error: 'stark-agent-failed' }
}
log(`Plan valid: ${plan.components.length} components, ${plan.criteriaCount} criteria`)

// Phase 4 — Tests (with retry loop)
phase('Tests')
let tests = null
let testAttempt = 0
while (!tests || !tests.valid) {
  testAttempt++
  if (testAttempt > 3) {
    log('Test writing failed 3 times. Aborting.')
    return { blocked: true, reason: 'test-validation', issues: tests ? tests.issues : [] }
  }
  const label = testAttempt > 1 ? `fury:retry-${testAttempt}` : 'fury'
  if (testAttempt > 1) log(`Tests retry ${testAttempt}: ${tests.issues.join(', ')}`)
  tests = await agent(furyPrompt(scope, plan, tests ? tests.issues : null), { label, schema: TEST_SCHEMA })
  if (!tests) return { error: 'fury-agent-failed' }
}
log(`Tests: ${tests.testCount} failing as expected across ${tests.testFiles.length} files`)

// Phase 5 — Implement (with retry loop)
phase('Implement')
let impl = null
let implAttempt = 0
while (!impl || !impl.valid) {
  implAttempt++
  if (implAttempt > 3) {
    log('Implementation failed 3 times. Aborting.')
    return { blocked: true, reason: 'impl-validation', issues: impl ? impl.issues : [] }
  }
  const label = implAttempt > 1 ? `ironman:retry-${implAttempt}` : 'ironman'
  if (implAttempt > 1) log(`Impl retry ${implAttempt}: ${impl.issues.join(', ')}`)
  impl = await agent(ironmanPrompt(scope, plan, tests, null), { label, schema: IMPL_SCHEMA })
  if (!impl) return { error: 'ironman-agent-failed' }
}
log(`Impl: all ${tests.testCount} tests pass. Race: clean. Coverage: ${impl.coveragePct || '?'}%`)

// Phase 6 — Review (4-dim pipeline + adversarial verify)
phase('Review')
log('Launching Hawk review across 4 dimensions...')

async function runReviewRound(implResult) {
  const dimResults = await pipeline(
    REVIEW_DIMS,
    dim => agent(hawkDimPrompt(dim, scope, implResult), {
      label: `hawk:${dim.key}`,
      phase: 'Review',
      schema: REVIEW_SCHEMA,
    }),
    (result, dim) => {
      if (!result || !result.findings || result.findings.length === 0) return []
      return parallel(result.findings.map(f => () =>
        agent(verifyFindingPrompt(f), {
          label: `verify:${dim.key}:${f.severity.toLowerCase()}`,
          phase: 'Review',
          schema: VERDICT_SCHEMA,
        }).then(v => v ? { ...f, verified: v.isReal, adjustedSeverity: v.adjustedSeverity || f.severity } : null)
      ))
    }
  )

  const allVerified = dimResults.flat().filter(Boolean).filter(f => f.verified)
  const deduped = dedupeFindings(allVerified)
  deduped.sort((a, b) => ['CRITICAL','HIGH','MEDIUM','LOW'].indexOf(a.adjustedSeverity) - ['CRITICAL','HIGH','MEDIUM','LOW'].indexOf(b.adjustedSeverity))
  return deduped
}

let confirmed = await runReviewRound(impl)
log(`Review: ${confirmed.length} confirmed findings (${confirmed.filter(f => ['CRITICAL','HIGH'].includes(f.adjustedSeverity)).length} critical/high)`)

const criticalHigh = confirmed.filter(f => ['CRITICAL', 'HIGH'].includes(f.adjustedSeverity))
if (criticalHigh.length > 0) {
  log(`${criticalHigh.length} CRITICAL/HIGH findings — sending Ironman back for a fix pass`)
  impl = await agent(ironmanPrompt(scope, plan, tests, criticalHigh), {
    label: 'ironman:fix-pass',
    schema: IMPL_SCHEMA,
  })
  if (!impl || !impl.valid) {
    log('WARNING: fix pass produced invalid impl. Proceeding with best effort.')
  }

  log('Re-reviewing after fix pass...')
  const reConfirmed = await runReviewRound(impl)
  const stillCritical = reConfirmed.filter(f => ['CRITICAL', 'HIGH'].includes(f.adjustedSeverity))
  if (stillCritical.length > 0) {
    log(`WARNING: ${stillCritical.length} CRITICAL/HIGH remain after fix pass. Escalating to user.`)
    return { blocked: true, reason: 'review-gate', findings: stillCritical }
  }
  confirmed = reConfirmed
  log(`Re-review: ${confirmed.length} remaining findings (all MEDIUM/LOW)`)
}

// Phase 7 — Finalize
phase('Finalize')
log('Running final verification sequence...')
await agent(finalizePrompt(scope, impl, confirmed, autonomous), {
  label: 'finalize',
  phase: 'Finalize',
})

return {
  feature: scope.feature,
  mode: scope.mode,
  testsCount: tests.testCount,
  coveragePct: impl.coveragePct,
  findingsResolved: confirmed.length,
  criticalHighRemaining: 0,
  autonomous,
}
