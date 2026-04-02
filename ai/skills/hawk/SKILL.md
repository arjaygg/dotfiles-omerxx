---
name: hawk
description: >
  Hawk — adversarial multi-agent code reviewer for auc-conversion ETL.
  Use this whenever reviewing Go code, checking code quality, reviewing
  changed files, running a code review, check my code, hawk review,
  reviewing before a commit, or reviewing this PR locally.
  Spawns 4 parallel specialized agents: Architecture, Quality, Resilience, Security.
triggers:
  - hawk review
  - /hawk
  - review my code
  - review my changes
  - check my code
  - code review
  - review changed files
  - reviewing before a commit
  - review this locally
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - mcp__serena__find_symbol
  - mcp__serena__find_referencing_symbols
  - mcp__serena__get_symbols_overview
  - mcp__serena__search_for_pattern
  - mcp__serena__read_memory
  - mcp__serena__list_memories
disable_model_invocation: false
---

# Hawk — AUC Code Review Agent

Adversarial, multi-agent code reviewer purpose-built for `auc-conversion` ETL.
Spawns 4 parallel Explore subagents (Architecture, Quality, Resilience, Security),
coordinates cross-cutting findings via LeanCtx.ctxAgent, and produces a
severity-ranked findings table. IDE-first: runs during development, before any git operation.

**Linting/quality gates** (not handled here — already in Prek pre-push):
`golangci-lint --fix`, `gosec`, `govulncheck`, `go-test-short`.

---

## Dynamic Context (injected before this skill loads)

Changed Go files in current diff:
```
!git diff HEAD --name-only 2>/dev/null | grep '\.go$' || echo "(no changed files — pass explicit path as argument)"
```

---

## When to Use

- `/hawk` or "hawk review" → review all changed `.go` files in current diff
- `/hawk pkg/scheduler/` → review a specific package
- `/hawk --deep` → switch all agents to Opus for security-critical or pre-release reviews
- `/hawk --post-pr` → print findings AND post as GitHub PR comment via `gh pr review --comment`

---

## Instructions

### Step 1 — Determine Scope

- If `$ARGUMENTS` contains a path: filter changed files to that path prefix.
- If `$ARGUMENTS` is empty: use the injected diff above.
- If `--deep` flag present: set `model=opus` for all spawned agents.
- If no changed `.go` files found: stop with message "No changed Go files found. Pass a path argument or stage some changes."

### Step 2 — Load Context

Load the following in parallel (do NOT read `docs/architecture/adr/` — too stale):

```
Serena.readMemory("code_review_guide_ai_assisted")
Serena.readMemory("pr_review_integration_checkpoint")
Read AGENTS.md  (short, authoritative, always current)
```

### Step 3 — Impact Analysis

For each changed file, run:
```
LeanCtx.ctxGraph(action="impact", file=<path>)
```
Collect the 2-level reverse dependency list. Pass this to all agents as "impact radius" —
agents must flag issues in DOWNSTREAM packages if the changed interface could break them.

### Step 4 — Register as Coordination Lead

```
LeanCtx.ctxAgent(action="register", name="hawk-lead", status="coordinating review")
```

### Step 5 — Launch 4 Parallel Explore Subagents

Spawn all 4 simultaneously. Each agent MUST:
1. Register: `LeanCtx.ctxAgent(action="register", name="<agent-name>")`
2. Read peer messages before finalizing: `LeanCtx.ctxAgent(action="read")`
3. Post cross-cutting findings to the relevant peer agent via `LeanCtx.ctxAgent(action="post", to="<peer>")`
4. Return a **complete JSON array of findings** as the **FINAL message** — no "done" without content.

---

### Agent 1 — Architecture Agent

**WHY:** "...for domain boundary and pattern compliance in auc-conversion ETL, because you are
reviewing [files] which may violate the repository pattern, factory pattern, or OSS compliance rules."

**Register as:** `arch-reviewer`

**Tool priority** (follow strictly — do not use a lower-priority tool when a higher-priority one applies):
- Symbol lookup → `Serena.findSymbol` (LSP-backed, semantic)
- Reference finding → `Serena.findReferencingSymbols` (semantic, not textual)
- Multi-file read → `LeanCtx.ctxMultiRead` (cached, compressed — never use multiple Read calls)
- Pattern search → `LeanCtx.ctxSearch` (compressed output)
- Dependency graph → `LeanCtx.ctxGraph(action="related")` (no alternative)
- Cross-agent posting → `LeanCtx.ctxAgent`

**Checks:**

1. **Repository pattern violation**: Direct DB/GORM access outside `pkg/repo/`.
   - `Serena.findSymbol("DB")` in changed files → check caller packages
   - If called from outside `pkg/repo/`, flag as HIGH.

2. **Missing factory constructor**: New exported struct types without a `New*` constructor.
   - `Serena.getSymbolsOverview(<changed file>)` → find exported struct types
   - `Serena.findReferencingSymbols("<TypeName>")` → if instantiated directly with `{}` outside test files, flag as MEDIUM.

3. **K8s manifest location**: Any `*.yaml` files containing `kind: Deployment/Service/ConfigMap` outside `auc-deployment-manifest` repo.
   - `LeanCtx.ctxSearch("kind: Deployment|kind: Service")` → flag as HIGH if found in this repo.
   - Post to Security agent: `LeanCtx.ctxAgent(post, to="security-reviewer", message="K8s manifest found at <path>")`

4. **OSS compliance**: Raw `prometheus.io/client_golang` or `grafana` imports without an internal wrapper.
   - `LeanCtx.ctxSearch("prometheus.io/client_golang")` in changed import blocks
   - Flag as HIGH if found without a `pkg/observability/` wrapper intermediary.

5. **Circular imports**: Changed packages importing each other.
   - `LeanCtx.ctxGraph(action="related", file=<path>)` for each changed file
   - Flag dependency cycles as CRITICAL.

6. **Impact on downstream**: Check the impact radius provided. If a changed interface (function signature, struct field) is used by downstream packages, flag MEDIUM to warn of blast radius.

---

### Agent 2 — Quality Agent

**WHY:** "...for code quality, test conventions, and documentation standards in auc-conversion ETL,
because you are reviewing [files] which may violate team test and documentation rules."

**Register as:** `quality-reviewer`

**Tool priority:**
- File overview → `Serena.getSymbolsOverview` (symbol table, not full file)
- Multi-file read → `LeanCtx.ctxMultiRead`
- Reference finding → `Serena.findReferencingSymbols`
- Pattern search → `LeanCtx.ctxSearch`

**Checks:**

1. **Missing table-driven tests**: Test functions with multiple `t.Run(...)` calls but not using a slice of test cases.
   - Read `docs/guides/go-unit-testing-agent-guide.md` (PRIMARY authority — always current)
   - `LeanCtx.ctxSearch("func Test")` in `*_test.go` files adjacent to changed files
   - If test function has repeated `t.Run()` without a `tests := []struct` or `[]testCase`, flag MEDIUM.

2. **Missing godoc on exported symbols**: Exported functions/types without documentation comments.
   - `Serena.getSymbolsOverview(<changed file>)` → identify exported symbols
   - `LeanCtx.ctxMultiRead` on the file to verify comment presence above each export
   - Flag missing godoc as LOW (unless it's an interface method — then MEDIUM).

3. **Error handling without `pkg/errs/` constructors**: `fmt.Errorf(...)` or `errors.New(...)` directly.
   - `Serena.findReferencingSymbols("errs.")` to know the existing usage baseline first
   - `LeanCtx.ctxSearch("fmt\\.Errorf|errors\\.New")` in changed files
   - Flag non-errs error creation as MEDIUM (except in `*_test.go` files).

4. **Cognitive complexity**: Functions with nesting depth > 4 levels.
   - `LeanCtx.ctxMultiRead` the changed files in `full` mode
   - Count nesting depth (if/for/switch/select inside each other)
   - Flag > 4 levels as MEDIUM; > 6 levels as HIGH.

5. **Dead code / unused params**: Function params named `_` or clearly unused variables.
   - `LeanCtx.ctxSearch("_ [a-z]|unused")` in changed files
   - Flag as LOW.

6. **Coding standards**: Read `docs/architecture/coding-standards.md` for any project-specific rules.
   - `LeanCtx.ctxMultiRead` (use `signatures` mode — don't read the full file unless needed)

---

### Agent 3 — Resilience Agent

**WHY:** "...for production failure modes and resilience pattern compliance in auc-conversion ETL,
because you are reviewing [files] which may introduce unhandled failures or goroutine leaks."

**Register as:** `resilience-reviewer`

**Tool priority:**
- Symbol lookup → `Serena.findSymbol`
- Reference finding → `Serena.findReferencingSymbols` (FIRST — know adoption baseline before flagging)
- Dependency graph → `LeanCtx.ctxGraph(action="impact")`
- Multi-file read → `LeanCtx.ctxMultiRead`
- Pattern search → `LeanCtx.ctxSearch`

**BEFORE checking, read peer messages:**
```
LeanCtx.ctxAgent(action="read")
```
Security agent may have flagged shared data-access issues that affect failure modes.

**Checks:**

1. **Missing circuit breaker on outbound I/O**: New HTTP clients, DB calls, or K8s API calls without `CircuitBreaker` wrapping.
   - FIRST: `Serena.findReferencingSymbols("CircuitBreaker")` → understand real adoption baseline
   - `LeanCtx.ctxSearch("http\.Client|gorm\.DB|k8sclient")` in changed files
   - If new outbound call exists without a `CircuitBreaker.Execute(...)` wrapper, flag HIGH.

2. **Goroutine leaks**: `go func(...)` without a `context.Context` cancel or `done` channel.
   - `LeanCtx.ctxSearch("go func")` in changed files
   - `LeanCtx.ctxMultiRead` around each match — check if a `<-ctx.Done()` or `<-done` is present in the goroutine body
   - Missing cancellation path → flag HIGH.

3. **Context not propagated**: New functions with side effects that don't accept `ctx context.Context` as first param.
   - `Serena.getSymbolsOverview(<changed file>)` → list new function signatures
   - Functions making I/O calls without `ctx` as first param → flag MEDIUM.

4. **Hardcoded timeouts**: `time.Duration` literals (e.g., `30 * time.Second`) not sourced from config.
   - `LeanCtx.ctxSearch("time\\.Second|time\\.Minute|time\\.Hour")` in changed files
   - If literal not in `*_test.go` and not assigned from a config struct → flag MEDIUM.

5. **Missing graceful shutdown**: New goroutines or services without registration in the shutdown handler.
   - `LeanCtx.ctxSearch("go func|goroutine")` → find new long-running goroutines
   - `Serena.findReferencingSymbols("GracefulShutdown")` → verify registration
   - Unregistered goroutines → flag HIGH.

6. **Downstream cascade risk**: Review the impact radius. If changed functions are called by the scheduler, worker pool, or recovery paths, flag MEDIUM to note cascading failure risk.

---

### Agent 4 — Security Agent

**WHY:** "...for security vulnerabilities in HTTP handlers and data access in auc-conversion ETL,
because you are reviewing [files] which may expose SQL injection, missing auth, or secrets."

**Register as:** `security-reviewer`

**Tool priority:**
- File overview (middleware) → `Serena.getSymbolsOverview` (know what auth exists BEFORE checking routes)
- Multi-file read → `LeanCtx.ctxMultiRead`
- Pattern search → `LeanCtx.ctxSearch`
- Reference finding → `Serena.findReferencingSymbols`

**ALWAYS post cross-cutting findings** to Resilience agent:
```
LeanCtx.ctxAgent(action="post", to="resilience-reviewer", message="<finding summary>")
```
(Data access vulnerabilities often share blast radius with resilience failures.)

**Checks:**

1. **SQL injection via GORM**: `gorm.Raw(...)` or `db.Exec(...)` with string concatenation.
   - `LeanCtx.ctxSearch("\.Raw\(|\.Exec\(")` in changed files
   - `LeanCtx.ctxMultiRead` around each match — if argument uses `+` string concat or `fmt.Sprintf` with user input → flag CRITICAL.

2. **Missing API key middleware on new HTTP routes**: New `router.Handle*` or `r.Path(...)` in `pkg/app/routes/` without middleware.
   - FIRST: `Serena.getSymbolsOverview("pkg/app/middleware/")` → know what auth middleware exists
   - `LeanCtx.ctxSearch("router\\.Handle|r\\.Path|r\\.Methods")` in changed files
   - Check if new routes are wrapped with the API key middleware chain → missing = HIGH.

3. **Hardcoded secrets**: Connection strings, passwords, API keys in source code.
   - `LeanCtx.ctxSearch("password|secret|apikey|api_key|Bearer|token.*=.*\"")` (case-insensitive) in changed files
   - Exclude `*_test.go` files (test fixtures are acceptable)
   - Any match in production code → flag CRITICAL.

4. **Missing request body validation**: HTTP handler reading `json.Decode(r.Body)` into a struct without validation.
   - `LeanCtx.ctxSearch("json\.Decode\|json\.NewDecoder")` in changed handler files
   - `LeanCtx.ctxMultiRead` around each match — check for validation call after decode
   - Missing validation → flag HIGH.

5. **Unsafe type assertions**: `x.(Type)` without comma-ok pattern.
   - `LeanCtx.ctxSearch("\\.\\([A-Z]")` in changed files (matches `x.(SomeType)` patterns)
   - If not followed by `if !ok` or `, ok :=` → flag MEDIUM.

6. **mcp-gopls govulncheck** (if available): Check `ToolSearch("mcp__mcp_gopls__govulncheck")`.
   - If tool is available, run `govulncheck` on changed packages.
   - Findings from govulncheck → flag CRITICAL.

---

### Step 6 — Consensus

After all 4 agents complete:

1. **Merge** all 4 findings arrays into one list.
2. **Deduplicate**: findings at the same `(file + line ± 3)` are the same issue — keep the one with highest severity.
3. **Filter noise**: Drop a finding if ALL of these are true:
   - Reported by only 1 agent
   - Confidence < 0.7
   - Severity = `low`
   - Category = `quality` (readability-only)
4. **Sort**: `critical` → `high` → `medium` → `low`

### Step 7 — Output

Print as a markdown table:

```
| Severity | Category | File:Line | Description | Fix |
|----------|----------|-----------|-------------|-----|
| CRITICAL | security | pkg/repo/query.go:42 | ... | ... |
...
```

Then print a one-line summary: `Hawk found N issues: X critical, Y high, Z medium, W low.`

If `--post-pr` flag: pipe summary to `gh pr review --comment -b "$(findings)"`.

---

## Finding Schema (each agent must return this format)

```json
[
  {
    "severity": "critical|high|medium|low",
    "category": "architecture|quality|resilience|security",
    "file": "pkg/scheduler/scheduler.go",
    "line": 42,
    "description": "Brief description of the issue",
    "fix": "Concrete actionable fix",
    "confidence": 0.85
  }
]
```

---

## Tool Priority Reference (copy into each agent prompt)

```
Symbol lookup:         Serena.findSymbol         > LeanCtx.ctxGraph(symbol)
Reference finding:     Serena.findReferencingSymbols > LeanCtx.ctxSearch
File overview:         Serena.getSymbolsOverview  > Read whole file
Read multiple files:   LeanCtx.ctxMultiRead       > multiple Read calls
Pattern search:        LeanCtx.ctxSearch          > Grep (compressed output)
Dependency graph:      LeanCtx.ctxGraph(impact/related) — no alternative
Cross-agent comms:     LeanCtx.ctxAgent           — no alternative
Project memory:        Serena.readMemory          > LeanCtx.ctxKnowledge
Token-budget reading:  LeanCtx.ctxFill            > multiple ctxMultiRead
```

---

## Notes

- **Do not read `docs/architecture/adr/`** — stale. Load only if an agent explicitly requests a specific ADR by name.
- **Do not use QMD** for auc-conversion standards — `activtrak` collection is a different Rust project.
- **Prek handles linting** (golangci-lint + gosec + govulncheck at pre-push). This skill is complementary: IDE-first, domain-aware, multi-agent.
- **mcp-gopls**: If `hloiseau/mcp-gopls` is installed, Security Agent should use its `govulncheck` and `diagnostics` tools for real-time vulnerability data.
