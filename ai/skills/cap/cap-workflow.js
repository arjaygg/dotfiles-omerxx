export const meta = {
  name: 'cap-v4',
  description: 'Cap v4.0 — Autonomous TDD orchestrator for Go, Python, and TypeScript: Scope → Preflight → Plan → Tests → Implement → Review → Finalize',
  phases: [
    { title: 'Scope',     detail: 'Parse feature, detect language (go/python/typescript/polyglot), identify bounded context and affected packages' },
    { title: 'Preflight', detail: 'Code health gate ≥9.5 on affected packages (feature mode)' },
    { title: 'Plan',      detail: 'Stark writes architectural plan to plans/active-context.md' },
    { title: 'Tests',     detail: 'Fury writes failing tests for all plan components' },
    { title: 'Implement', detail: 'Ironman makes all tests pass (race detector clean for Go)' },
    { title: 'Review',    detail: 'Hawk reviews 4 dimensions in parallel, adversarial verify' },
    { title: 'Finalize',  detail: 'Full test suite pass, optional PushNotification' },
  ],
}

// ── Schemas ───────────────────────────────────────────────────────────────────

const SCOPE_SCHEMA = {
  type: 'object',
  required: ['feature', 'deliverable', 'criteria', 'affectedPkgs', 'boundedContext', 'mode', 'language'],
  properties: {
    feature:        { type: 'string' },
    deliverable:    { type: 'string' },
    criteria:       { type: 'array', items: { type: 'string' } },
    affectedPkgs:   { type: 'array', items: { type: 'string' } },
    boundedContext: { type: 'string' },
    mode:           { type: 'string', enum: ['feature', 'uplift'] },
    language:       { type: 'string', enum: ['go', 'python', 'typescript', 'polyglot'] },
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
    raceClean:    { oneOf: [{ type: 'boolean' }, { type: 'null' }] },
    changedFiles: { type: 'array', items: { type: 'string' } },
    coveragePct:  { type: 'number' },
    valid:        { type: 'boolean' },
    issues:       { type: 'array', items: { type: 'string' } },
    language:     { type: 'string' },
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

// ── Language configuration map ────────────────────────────────────────────────
// Each key maps to all language-specific commands and review check strings.
// Scope agent detects language; all downstream phases index into this map.

const LANG_CONFIG = {
  go: {
    testCmd:      'go test ./...',
    raceCmd:      'go test -race ./...',
    coverCmd:     'go test ./... -coverprofile=/tmp/cap-cov.out && go tool cover -func=/tmp/cap-cov.out | grep total',
    healthCmd:    'make code-health-json 2>/dev/null || echo SKIP',
    linters:      'golangci-lint run, gosec ./..., govulncheck ./...',
    testFileExt:  '_test.go',
    testPatterns: 'Go: t.Run() subtests, t.Parallel(), table-driven tests with []struct{name string; input; want}; use require (not assert)',
    implPatterns: 'Go: fmt.Errorf("...%w", err) wrapping, context.Context as first param, inject via interfaces, no naked goroutines',
    reviewChecks: {
      architecture: `Checks:
1. Repository pattern violation: Direct DB/GORM access outside pkg/repo/ → HIGH
2. Missing factory constructor: Exported struct instantiated with {} outside tests → MEDIUM
3. K8s manifest in wrong repo: *.yaml with kind: Deployment|Service → HIGH
4. OSS compliance: Raw prometheus.io/client_golang without internal wrapper → HIGH
5. Circular imports: Packages importing each other → CRITICAL
6. Downstream blast radius: Changed interface used by downstream packages → MEDIUM`,
      quality: `Checks:
1. Missing table-driven tests: Repeated t.Run() without a slice of test cases → MEDIUM
2. Missing godoc: Exported symbols without documentation comments → LOW (interface methods → MEDIUM)
3. Error handling: fmt.Errorf/errors.New without project error constructors → MEDIUM
4. Cognitive complexity: Nesting depth >4 → MEDIUM; >6 → HIGH
5. Dead code/unused params: _ param or clearly unused variables → LOW
6. Code health score: make code-health-json | scorer 0 — severity by score band`,
      resilience: `Checks:
1. Missing circuit breaker: New HTTP/DB/K8s calls without circuit breaker wrapping → HIGH
2. Goroutine leaks: go func(...) without context cancellation or done channel → HIGH
3. Context not propagated: Side-effect functions without ctx context.Context first param → MEDIUM
4. Hardcoded timeouts: time.Duration literals not sourced from config → MEDIUM
5. Missing graceful shutdown: New long-running goroutines not in shutdown handler → HIGH
6. Downstream cascade risk: Changed functions called by scheduler/worker pool → MEDIUM`,
      security: `Checks:
1. SQL injection: gorm.Raw/db.Exec with string concatenation or fmt.Sprintf with user input → CRITICAL
2. Missing auth middleware: New HTTP routes without middleware → HIGH
3. Hardcoded secrets: Connection strings, passwords, API keys in non-test source → CRITICAL
4. Missing request validation: json.Decode(r.Body) without post-decode validation → HIGH
5. Unsafe type assertions: x.(Type) without comma-ok pattern → MEDIUM
6. Govulncheck: Run if mcp__mcp_gopls__govulncheck available → CRITICAL if found`,
    },
  },
  python: {
    testCmd:      'python -m pytest --tb=short 2>/dev/null || echo SKIP',
    raceCmd:      null,
    coverCmd:     'python -m pytest --cov --cov-report=term-missing 2>/dev/null || echo SKIP',
    healthCmd:    'python -m ruff check . --output-format=json 2>/dev/null || echo SKIP',
    linters:      'python -m ruff check ., python -m mypy .',
    testFileExt:  'test_*.py or *_test.py',
    testPatterns: 'Python: pytest fixtures in conftest.py, @pytest.mark.parametrize for table-driven tests, assert statements',
    implPatterns: 'Python: type hints on all public functions, dataclasses/Pydantic models, context managers (with/as), async def with proper exception handling',
    reviewChecks: {
      architecture: `Checks:
1. Circular imports: Modules importing each other → CRITICAL
2. Missing type hints: Public functions/methods without type annotations → MEDIUM
3. Layer violation: Business logic in route handlers or data access in domain objects → HIGH
4. God module: Single file >500 LOC doing multiple unrelated things → MEDIUM
5. Missing __init__.py: Package directories missing module marker (Python <3.3) → LOW
6. Downstream blast radius: Changed public API used by other modules → MEDIUM`,
      quality: `Checks:
1. Missing parametrize: Repeated similar test functions without @pytest.mark.parametrize → MEDIUM
2. Missing docstrings: Public classes/functions without docstrings → LOW (public API → MEDIUM)
3. Exception swallowing: bare except: or except Exception: pass → HIGH
4. Cognitive complexity: Nesting depth >4 → MEDIUM; >6 → HIGH
5. Dead code: unused imports, variables never read → LOW
6. ruff/mypy issues: run python -m ruff check . and python -m mypy . — severity by error type`,
      resilience: `Checks:
1. Missing context manager: File/DB/network resources opened without with statement → HIGH
2. Async exception handling: async def without try/except or proper cancellation → MEDIUM
3. Hardcoded timeouts: timeout values as literals not from config → MEDIUM
4. Missing retry logic: Network calls without retry/backoff on transient errors → MEDIUM
5. Unhandled task cancellation: asyncio.Task without cancellation shield where needed → MEDIUM
6. Downstream cascade risk: Changed shared utilities used broadly → MEDIUM`,
      security: `Checks:
1. SQL injection: raw SQL string with format/f-string/% with user input → CRITICAL
2. subprocess shell=True: subprocess.run(cmd, shell=True) with user-controlled input → CRITICAL
3. Path traversal: open() with user-supplied path without sanitization → HIGH
4. Hardcoded secrets: API keys, passwords, tokens in non-test source → CRITICAL
5. Pickle deserialization: pickle.loads() on untrusted data → HIGH
6. Missing input validation: API endpoints without schema validation (Pydantic/marshmallow) → HIGH`,
    },
  },
  typescript: {
    testCmd:      'npx jest --passWithNoTests 2>/dev/null || npx vitest run 2>/dev/null || echo SKIP',
    raceCmd:      null,
    coverCmd:     'npx jest --coverage --coverageReporters=text 2>/dev/null || npx vitest run --coverage 2>/dev/null || echo SKIP',
    healthCmd:    'npx eslint . --format=json 2>/dev/null || echo SKIP',
    linters:      'npx tsc --noEmit, npx eslint .',
    testFileExt:  '*.test.ts, *.spec.ts',
    testPatterns: 'TypeScript: Jest describe/it/expect, beforeEach/afterEach, jest.fn() mocks; or Vitest describe/it/expect',
    implPatterns: 'TypeScript: strict null checks, discriminated unions, async/await with try/catch, no implicit any, camelCase functions / PascalCase types',
    reviewChecks: {
      architecture: `Checks:
1. Circular dependencies: Module importing from its own consumers → CRITICAL
2. Barrel file abuse: index.ts re-exporting everything leading to import cycles → MEDIUM
3. Module boundary violation: Internal implementation details exported without cause → MEDIUM
4. Missing type exports: Public API types not exported from module index → LOW
5. Mixed concerns: UI components containing business logic or direct API calls → HIGH
6. Downstream blast radius: Changed exported type/interface used widely → MEDIUM`,
      quality: `Checks:
1. Implicit any: Variables or params typed as any without explicit annotation → MEDIUM
2. Strict mode disabled: tsconfig.json missing "strict": true → HIGH
3. Missing test coverage: Exported functions/components with no test file → MEDIUM
4. Cognitive complexity: Nesting depth >4 → MEDIUM; >6 → HIGH
5. Dead code: Unused exports, variables, or imports → LOW
6. ESLint/tsc issues: run npx eslint . and npx tsc --noEmit — severity by rule`,
      resilience: `Checks:
1. Unhandled Promise rejection: .then() without .catch() or await without try/catch → HIGH
2. Null/undefined guards: Optional chaining missing on nullable access paths → MEDIUM
3. Missing error boundaries: React component trees without error boundary → MEDIUM
4. Hardcoded timeouts: setTimeout/setInterval values as magic literals → LOW
5. Missing loading/error states: Async operations without loading indicator → MEDIUM
6. Type assertion abuse: as SomeType without runtime validation → MEDIUM`,
      security: `Checks:
1. XSS via innerHTML: dangerouslySetInnerHTML or innerHTML with user data → CRITICAL
2. Prototype pollution: Object.assign/merge with user-controlled keys → HIGH
3. eval() usage: eval(), new Function(), or dynamic import with user input → CRITICAL
4. Hardcoded secrets: API keys, tokens in non-test source → CRITICAL
5. Missing CSRF protection: State-mutating API calls without CSRF token → HIGH
6. Deserialization: JSON.parse on untrusted input without schema validation → MEDIUM`,
    },
  },
  polyglot: {
    testCmd:      '# Run each detected language test suite',
    raceCmd:      null,
    coverCmd:     '# Aggregate coverage across languages',
    healthCmd:    '# Run all applicable health checks',
    linters:      'run all applicable linters for each detected language',
    testFileExt:  'varies by language',
    testPatterns: 'Use the test patterns for the primary language of each changed file',
    implPatterns: 'Apply language-specific patterns per file being changed',
    reviewChecks: {
      architecture: 'Check architecture for each language present. Look for cross-language boundary violations and shared-state coupling.',
      quality:      'Apply quality checks for each language present using appropriate tools (ruff, eslint, golangci-lint).',
      resilience:   'Check resilience patterns for each language present (goroutines for Go, async for Python/TS).',
      security:     'Apply security checks for each language present (CRITICAL findings get priority regardless of language).',
    },
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
4. (Episodic memory) Use ToolSearch with query "mcp__supermemory__search". If the tool
   is available, call it with query "${taskDesc}" to surface relevant past decisions,
   patterns, and context from previous sessions on this codebase.
5. (Structural graph) Check if graphify-out/graph.json exists in the project root.
   If yes, read graphify-out/GRAPH_REPORT.md for community structure and god nodes
   before searching files — this is 71x more token-efficient than raw Grep/Glob.
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
- Detect the project language by checking root-level files:
  * go.mod or *.go files present → language: "go"
  * pyproject.toml, requirements.txt, setup.py, or *.py files present → language: "python"
  * tsconfig.json + package.json, or *.ts/*.tsx files present → language: "typescript"
  * Multiple language markers detected → language: "polyglot"
  * When ambiguous, prefer the language of the majority of files being changed
- Identify the DDD bounded context and affected packages/modules (e.g. pkg/scheduler for Go, src/services for TS, app/domain for Python)
- List 3-7 concrete acceptance criteria as verifiable checkboxes
- Set mode to "${mode}" (override to "feature" if not "uplift")

Return SCOPE_SCHEMA JSON only. The language field is required.`
}

function preflightPrompt(scope) {
  const lang = LANG_CONFIG[scope.language] || LANG_CONFIG.go
  return `${pctxInit('cap preflight code health gate')}

You are Cap's preflight checker. Run the code health gate on the affected packages and report results.

Affected packages: ${scope.affectedPkgs.join(', ')}
Language: ${scope.language}

Instructions:
- Run: claude /code-health --gate 9.5 ${scope.affectedPkgs.join(' ')}
- If the command is unavailable, run: ${lang.healthCmd} | head -50
- If the output contains "SKIP", log a warning and set score=10, passed=true (graceful degradation — tool not installed)
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
  const lang = LANG_CONFIG[scope.language] || LANG_CONFIG.go
  return `${pctxInit('fury test writing for ' + scope.feature)}

You are Fury, the QA agent. Write failing tests for all components in the plan.

Plan: plans/active-context.md (read it first)
Components to test: ${plan.components.join(', ')}
Feature: "${scope.feature}"
Language: ${scope.language}
${feedback && feedback.length > 0 ? `\nFeedback from prior attempt:\n${feedback.map(i => `- ${i}`).join('\n')}` : ''}

Instructions:
- Read plans/active-context.md before writing any tests
- Write tests FIRST in test files (${lang.testFileExt}) — never touch implementation files
- BDD structure: Given-When-Then (Arrange, Act, Assert)
- ${lang.testPatterns}
- Cover edge cases: nil/null inputs, boundaries, error paths, async failures
- Run: ${lang.testCmd} — verify each fails for the right reason (NOT a compile/import error)

Success condition: ALL tests must FAIL (they are pre-implementation — passing means a bug).

Return TEST_SCHEMA JSON. Set valid=false and list issues if any component lacks coverage or tests don't fail correctly.`
}

function ironmanPrompt(scope, plan, tests, findings) {
  const lang = LANG_CONFIG[scope.language] || LANG_CONFIG.go
  const fixPassHeader = findings
    ? `This is a FIX PASS. Address these Hawk review findings FIRST:\n${findings.map(f => `- [${f.severity}] ${f.file}:${f.line} — ${f.description}\n  Fix: ${f.fix}`).join('\n')}\n`
    : ''
  const raceStep = lang.raceCmd
    ? `- When all unit tests pass: ${lang.raceCmd}`
    : `- No race detector for ${scope.language} — set raceClean: null in output`
  return `${pctxInit('ironman implementation for ' + scope.feature)}

You are Ironman, the Implementation Agent. Make the failing tests pass.
${fixPassHeader}
Plan: plans/active-context.md (read it first)
Failing tests: ${tests.testFiles.join(', ')}
Feature: "${scope.feature}"
Language: ${scope.language}

Instructions:
- Read plan and all test files before touching source
- Implement MINIMAL changes — only what's needed for tests to pass${findings ? ' and findings to be fixed' : ''}
- ${lang.implPatterns}
- Do NOT refactor beyond what's in the plan
- Run after each component: ${lang.testCmd}
- ${raceStep}
- Capture coverage: ${lang.coverCmd}

Return IMPL_SCHEMA JSON. Set language: "${scope.language}". Set raceClean: ${lang.raceCmd ? 'true/false based on race output' : 'null (not applicable)'}. Set valid=false if any test fails.`
}

function hawkDimPrompt(dim, scope, impl) {
  const files = impl.changedFiles.join(', ')
  const lang = LANG_CONFIG[scope.language] || LANG_CONFIG.go
  const checks = lang.reviewChecks[dim.key] || dim.fallbackChecks || 'Apply standard code review checks for this dimension.'
  return `${pctxInit('hawk ' + dim.key + ' review')}

You are a code reviewer specializing in ${dim.label} for ${scope.language} projects. Review the changed files below.

Changed files: ${files}
Feature context: "${scope.feature}"
Language: ${scope.language}

${checks}

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
  const lang = LANG_CONFIG[scope.language] || LANG_CONFIG.go
  const raceStep = lang.raceCmd
    ? `2. Run: ${lang.raceCmd} (confirm race detector clean)`
    : `2. Skip race detector — not applicable for ${scope.language}`
  return `${pctxInit('cap finalize and commit')}

You are Cap's finalization agent. Run the final verification sequence and commit.

Feature: "${scope.feature}"
Language: ${scope.language}
Changed files: ${impl.changedFiles.join(', ')}
Confirmed findings (all should be resolved): ${confirmed.length === 0 ? 'none' : confirmed.map(f => f.description).join(', ')}

Instructions:
1. Run: ${lang.testCmd} (confirm all tests pass)
${raceStep}
3. Run: ${lang.coverCmd} (capture final coverage)
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

// Language-specific checks live in LANG_CONFIG[language].reviewChecks[dim.key]
// REVIEW_DIMS holds only language-agnostic metadata (key, label, toolPriority)
const REVIEW_DIMS = [
  {
    key: 'architecture',
    label: 'Architecture',
    toolPriority: 'Serena.findSymbol → Serena.findReferencingSymbols → Serena.getSymbolsOverview → Grep',
    fallbackChecks: 'Check for circular imports, layer violations, and downstream blast radius.',
  },
  {
    key: 'quality',
    label: 'Quality',
    toolPriority: 'Serena.getSymbolsOverview → Serena.findReferencingSymbols → Grep',
    fallbackChecks: 'Check for missing tests, documentation, error handling, and cognitive complexity.',
  },
  {
    key: 'resilience',
    label: 'Resilience',
    toolPriority: 'Serena.findSymbol → Serena.findReferencingSymbols → Grep',
    fallbackChecks: 'Check for missing circuit breakers, resource leaks, hardcoded timeouts, and error propagation.',
  },
  {
    key: 'security',
    label: 'Security',
    toolPriority: 'Serena.getSymbolsOverview → Grep → Serena.findReferencingSymbols',
    fallbackChecks: 'Check for injection vulnerabilities, hardcoded secrets, missing auth, and unsafe deserialization.',
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
log(`Scope: ${scope.affectedPkgs.join(', ')} | language: ${scope.language} | context: ${scope.boundedContext} | criteria: ${scope.criteriaCount || scope.criteria.length}`)

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
const raceStatus = impl.raceClean === null ? 'n/a' : impl.raceClean ? 'clean' : 'FAILED'
log(`Impl: all ${tests.testCount} tests pass. Race: ${raceStatus}. Coverage: ${impl.coveragePct || '?'}%`)

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
  language: scope.language,
  mode: scope.mode,
  testsCount: tests.testCount,
  coveragePct: impl.coveragePct,
  findingsResolved: confirmed.length,
  criticalHighRemaining: 0,
  autonomous,
}
