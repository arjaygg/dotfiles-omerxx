---
name: hawk
description: >
  Hawk — adversarial multi-agent code reviewer for Go codebases.
  Use this whenever reviewing Go code, checking code quality, reviewing
  changed files, running a code review, check my code, hawk review,
  reviewing before a commit, or reviewing this PR locally.
  Spawns 4 parallel specialized agents: Architecture, Quality, Resilience, Security.
  Never stops until all agents complete and findings are aggregated.
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
version: 2.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - advisor
  - TaskUpdate
  - TaskGet
  - mcp__serena__find_symbol
  - mcp__serena__find_referencing_symbols
  - mcp__serena__get_symbols_overview
  - mcp__serena__search_for_pattern
  - mcp__serena__read_memory
  - mcp__serena__list_memories
disable_model_invocation: false
---

# Hawk — Adversarial Multi-Agent Code Reviewer

Adversarial, multi-agent code reviewer. Spawns 4 parallel Explore subagents (Architecture, Quality,
Resilience, Security), coordinates cross-cutting findings, and produces a severity-ranked findings table.

**Linting/quality gates** (not handled here — already in CI pre-push):
`golangci-lint --fix`, `gosec`, `govulncheck`, `go-test-short`.

---

## Persistence Directive

Hawk does **not stop midway**. Once invoked:
- Launch all 4 agents and wait for all to complete — do not report partial results
- Aggregate, deduplicate, and rank all findings before returning
- Use `TodoWrite` to track progress
- Report progress via `TaskUpdate` if `CLAUDE_CODE_TASK_LIST_ID` is set

---

## Dynamic Context

Changed Go files in current diff:
```
!git diff HEAD --name-only 2>/dev/null | grep '\.go$' || echo "(no changed files — pass explicit path as argument)"
```

---

## Session Start — Register Progress

At session start:

1. Create internal `TodoWrite` checklist:
   ```
   TodoWrite([
     { id: "scope",    content: "Determine scope and load context", status: "pending" },
     { id: "impact",   content: "Run impact analysis on changed files", status: "pending" },
     { id: "agents",   content: "Launch 4 parallel review agents", status: "pending" },
     { id: "advisor",  content: "Call advisor before finalizing CRITICAL findings", status: "pending" },
     { id: "aggregate",content: "Aggregate, deduplicate, and rank all findings", status: "pending" },
     { id: "report",   content: "Output findings table and summary", status: "pending" },
   ])
   ```

2. If `CLAUDE_CODE_TASK_LIST_ID` is set: `TaskUpdate(status: "in_progress", notes: "Hawk: beginning code review")`

---

## When to Use

- `/hawk` → review all changed `.go` files in current diff
- `/hawk pkg/scheduler/` → review a specific package
- `/hawk --deep` → switch all agents to Opus for security-critical or pre-release reviews
- `/hawk --post-pr` → print findings AND post as GitHub PR comment via `gh pr review --comment`

---

## Instructions

### Step 1 — Determine Scope

Mark `scope` in_progress.

- If `$ARGUMENTS` contains a path: filter to that path prefix
- If `$ARGUMENTS` is empty: use the injected diff above
- If `--deep` flag: set `model=opus` for all spawned agents
- If no changed `.go` files: stop with "No changed Go files found. Pass a path argument or stage some changes."

Load context in parallel:
```
Serena.readMemory("code_review_guide_ai_assisted")
Read("AGENTS.md")
```

Mark `scope` completed.

---

### Step 2 — Impact Analysis

Mark `impact` in_progress. Report: "Hawk: analyzing impact radius"

For each changed file, identify the 2-level reverse dependency list to pass to agents as "impact radius."
Agents must flag issues in DOWNSTREAM packages if a changed interface could break them.

Mark `impact` completed.

---

### Step 3 — Launch 4 Parallel Agents

Mark `agents` in_progress. Report: "Hawk: launching Architecture, Quality, Resilience, Security agents"

Spawn all 4 simultaneously. Each agent MUST:
1. Read all changed files for their domain
2. Check cross-cutting findings from peer agents
3. Return a **complete JSON array of findings** — never "done" without content

---

### Agent 1 — Architecture Agent

**Checks:**
1. **Repository pattern violation:** Direct DB/GORM access outside `pkg/repo/` → HIGH
2. **Missing factory constructor:** Exported struct instantiated with `{}` outside tests → MEDIUM
3. **K8s manifest in wrong repo:** `*.yaml` with `kind: Deployment|Service` → HIGH
4. **OSS compliance:** Raw `prometheus.io/client_golang` without internal wrapper → HIGH
5. **Circular imports:** Packages importing each other → CRITICAL
6. **Downstream blast radius:** Changed interface used by downstream packages → MEDIUM warning

**Tool priority:** `Serena.findSymbol` → `Serena.findReferencingSymbols` → `Serena.getSymbolsOverview` → `Grep`

---

### Agent 2 — Quality Agent

**Checks:**
1. **Missing table-driven tests:** Repeated `t.Run()` without a slice of test cases → MEDIUM
2. **Missing godoc:** Exported symbols without documentation comments → LOW (interface methods → MEDIUM)
3. **Error handling:** `fmt.Errorf` / `errors.New` without project error constructors → MEDIUM
4. **Cognitive complexity:** Nesting depth > 4 levels → MEDIUM; > 6 levels → HIGH
5. **Dead code / unused params:** `_ param` or clearly unused variables → LOW
6. **Coding standards:** Cross-reference `docs/architecture/coding-standards.md`

**Tool priority:** `Serena.getSymbolsOverview` → `Serena.findReferencingSymbols` → `Grep`

---

### Agent 3 — Resilience Agent

**Checks:**
1. **Missing circuit breaker:** New HTTP/DB/K8s calls without circuit breaker wrapping → HIGH
2. **Goroutine leaks:** `go func(...)` without context cancellation or done channel → HIGH
3. **Context not propagated:** Side-effect functions without `ctx context.Context` first param → MEDIUM
4. **Hardcoded timeouts:** `time.Duration` literals not sourced from config → MEDIUM
5. **Missing graceful shutdown:** New long-running goroutines not registered in shutdown handler → HIGH
6. **Downstream cascade risk:** Changed functions called by scheduler/worker pool → MEDIUM warning

**Before checking, read peer messages** — Security agent may have flagged shared data-access issues.

**Tool priority:** `Serena.findSymbol` → `Serena.findReferencingSymbols` → `Grep`

---

### Agent 4 — Security Agent

**Checks:**
1. **SQL injection:** `gorm.Raw` / `db.Exec` with string concatenation or `fmt.Sprintf` with user input → CRITICAL
2. **Missing auth middleware:** New HTTP routes without middleware → HIGH
3. **Hardcoded secrets:** Connection strings, passwords, API keys in non-test source → CRITICAL
4. **Missing request validation:** `json.Decode(r.Body)` without post-decode validation → HIGH
5. **Unsafe type assertions:** `x.(Type)` without comma-ok pattern → MEDIUM
6. **Govulncheck:** If `mcp__mcp_gopls__govulncheck` is available, run it → CRITICAL if found

**Always post cross-cutting findings** to Resilience agent — data access vulnerabilities share blast radius.

**Tool priority:** `Serena.getSymbolsOverview` → `Grep` → `Serena.findReferencingSymbols`

---

### Step 4 — Advisor Gate for CRITICAL Findings

Mark `advisor` in_progress.

**Call `advisor` before finalizing any CRITICAL findings.**
Ask the advisor to verify: Is the finding real? Could it be a false positive (e.g., SQL parameterization
is present but in a non-obvious form)? The CRITICAL label raises team alarm — it should be correct.

Incorporate advisor feedback. Downgrade to HIGH if advisor identifies a false positive with clear reasoning.

Mark `advisor` completed.

---

### Step 5 — Aggregate and Report

Mark `aggregate` in_progress.

1. **Merge** all 4 agent finding arrays
2. **Deduplicate:** findings at `(file + line ± 3)` are the same — keep the highest severity
3. **Filter noise:** Drop if ALL true: reported by 1 agent, confidence < 0.7, severity = LOW, category = quality
4. **Sort:** CRITICAL → HIGH → MEDIUM → LOW

Mark `aggregate` completed. Report via TaskUpdate: "Hawk: N findings (X critical, Y high, Z medium, W low)"

---

### Step 6 — Output

Mark `report` in_progress.

Print as markdown table:

```
| Severity | Category | File:Line | Description | Fix |
|----------|----------|-----------|-------------|-----|
| CRITICAL | security | pkg/repo/query.go:42 | ... | ... |
```

Then: `Hawk found N issues: X critical, Y high, Z medium, W low.`

If `--post-pr`: pipe to `gh pr review --comment -b "$(findings)"`.

Mark `report` completed. Report via TaskUpdate: "Hawk: review complete. N issues found."

---

## Finding Schema

```json
{
  "severity": "critical|high|medium|low",
  "category": "architecture|quality|resilience|security",
  "file": "pkg/scheduler/scheduler.go",
  "line": 42,
  "description": "Brief description of the issue",
  "fix": "Concrete actionable fix",
  "confidence": 0.85
}
```

---

## Success Criteria

- [ ] All 4 agents completed (no partial results)
- [ ] CRITICAL findings verified by advisor
- [ ] Findings deduplicated and ranked
- [ ] Markdown table output with actionable fixes
- [ ] TaskUpdate reported completion to shared task list
