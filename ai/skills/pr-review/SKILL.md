---
name: pr-review
description: >
  PR Review — comprehensive parallel multi-agent pull request investigation.
  For Go: 6 agents (hawk's Architecture/Quality/Resilience/Security + Performance + Tests).
  For non-Go: 4 agents (Security/Performance/Style/Tests).
  Stack-aware (Charcoal), forge-aware (GitHub + Azure DevOps), posts findings to PR.
  Use /pr-review for all reviews, Go and non-Go. (/hawk is a faster Go-only alternative; availability depends on this project's skillOverrides.)
triggers:
  - /pr-review
  - thorough pr review
  - full pr review
  - structured pr review
  - deep pr review
version: 2.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - advisor
  - mcp__serena__find_symbol
  - mcp__serena__find_referencing_symbols
  - mcp__serena__get_symbols_overview
  - mcp__serena__search_for_pattern
---

# PR Review — Comprehensive Parallel Multi-Agent Investigation

Orchestrates the right agent set based on detected language, then synthesizes a severity-ranked
findings table. Forge-aware and stack-aware — works on GitHub and Azure DevOps, single PRs and stacks.

**Note:** `/pr-review` incorporates the same Architecture/Quality/Resilience/Security agent set
that the standalone `/hawk` skill provides for fast Go-only checks. `/hawk`'s enabled/disabled
state is per-project (`skillOverrides` in that project's `.claude/settings.json`) — check it
rather than assuming; where it's off, `/pr-review --no-post` gives an equivalent quick,
non-posting Go review. For non-Go it runs a full 4-agent pass. Always posts to the PR unless
`--no-post` is passed.

## When to Use

- `/pr-review` → review current branch's diff against base, auto-detect forge + language
- `/pr-review <PR#>` → review a specific PR by number
- `/pr-review --stack` → review every PR in the current Charcoal stack independently
- `/pr-review --deep` → use Opus for all agents (security-critical or pre-release reviews)
- `/pr-review --no-post` → print findings only, skip posting to PR

---

## Instructions

### Step 1 — Detect Forge, Stack, Language, and Scope

**Forge detection:**
```bash
REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)
if echo "$REMOTE_URL" | grep -qiE "github\.com"; then FORGE="github"; else FORGE="azure"; fi
```

**Stack detection:**
```bash
GT_INITIALIZED=$(gt branch 2>/dev/null && echo "yes" || echo "no")
if [ "$GT_INITIALIZED" = "yes" ]; then
  STACK_BRANCHES=$(gt log --oneline 2>/dev/null | awk '{print $1}' | head -20)
  STACK_DEPTH=$(echo "$STACK_BRANCHES" | wc -l | tr -d ' ')
else
  STACK_DEPTH=1; STACK_BRANCHES=$(git branch --show-current)
fi
```

If `--stack` or `STACK_DEPTH > 1`: run a separate review per stack layer (`git diff <parent>...<layer>`),
combine all findings into one report sectioned by layer.

**Language detection:**
```bash
CHANGED_FILES=$(git diff --name-only $(git merge-base HEAD origin/main 2>/dev/null || echo "HEAD") 2>/dev/null | head -60)
LANG=$(echo "$CHANGED_FILES" | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
```

- `go` files dominate → `LANG=go` → **6 agents** (Go path, Step 2A)
- Otherwise → `LANG=<detected>` → **4 agents** (non-Go path, Step 2B)
- `--lang <x>` overrides detection; `--deep` sets model=opus for all agents

**PR context:**
```bash
gh pr view <N> --json title,body,baseRefName,files 2>/dev/null   # GitHub
az repos pr show --id <N> --organization "https://dev.azure.com/bofaz" 2>/dev/null  # Azure
```

If no changed files: stop — "No diff found. Pass a PR number or stage changes."

---

### Step 2A — Go Path: Dispatch 6 Parallel Agents

*(Skip to Step 2B if LANG ≠ go)*

Launch all six simultaneously. Each must return a **JSON array of findings**.
Agents 1–4 mirror hawk's canonical definitions — keep in sync if hawk's agents change.

---

**Go Agent 1 — Architecture Agent** *(from hawk)*

```
Review changed Go files for architecture violations.
Changed files: <list> | Impact radius: <2-level reverse deps>

1. Repository pattern violation: direct DB/GORM access outside pkg/repo/ → HIGH
2. Missing factory constructor: exported struct with {} outside tests → MEDIUM
3. K8s manifest in wrong repo: *.yaml with kind: Deployment|Service → HIGH
4. OSS compliance: raw prometheus client without internal wrapper → HIGH
5. Circular imports → CRITICAL
6. Downstream blast radius: changed interface used by downstream packages → MEDIUM

Tools: Serena.findSymbol → Serena.findReferencingSymbols → Serena.getSymbolsOverview → Grep
Return: [{"severity":"...","category":"architecture","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Go Agent 2 — Quality Agent** *(from hawk)*

```
Review changed Go files for quality issues.
Changed files: <list>

1. Missing table-driven tests: repeated t.Run() without slice → MEDIUM
2. Missing godoc on exported symbols → LOW (interface methods → MEDIUM)
3. Error handling without project constructors → MEDIUM
4. Cognitive complexity: nesting >4 → MEDIUM; >6 → HIGH
5. Dead code / unused params → LOW
6. Code Health: `make code-health-json | code-health-score.sh` — score <4.0 → HIGH, <2.0 → CRITICAL
   Hotspot escalation: top file with ≥5 commits/90d → escalate one level

Tools: Serena.getSymbolsOverview → Serena.findReferencingSymbols → Grep
Return: [{"severity":"...","category":"quality","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Go Agent 3 — Resilience Agent** *(from hawk)*

```
Review changed Go files for resilience issues.
Changed files: <list>

1. Missing circuit breaker on HTTP/DB/K8s calls → HIGH
2. Goroutine leaks: go func() without cancellation → HIGH
3. Context not propagated → MEDIUM
4. Hardcoded timeouts → MEDIUM
5. Missing graceful shutdown for new goroutines → HIGH
6. Downstream cascade: changed func in scheduler/worker pool → MEDIUM

Read peer Security agent messages for shared blast radius.
Tools: Serena.findSymbol → Serena.findReferencingSymbols → Grep
Return: [{"severity":"...","category":"resilience","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Go Agent 4 — Security Agent** *(from hawk)*

```
Review changed Go files for security issues.
Changed files: <list>

1. SQL injection: gorm.Raw/db.Exec with string concat or fmt.Sprintf → CRITICAL
2. Missing auth middleware on new HTTP routes → HIGH
3. Hardcoded secrets in non-test source → CRITICAL
4. Missing request validation after json.Decode → HIGH
5. Unsafe type assertion x.(Type) without comma-ok → MEDIUM
6. Govulncheck if available → CRITICAL if found

Post cross-cutting findings to Resilience agent.
Tools: Serena.getSymbolsOverview → Grep → Serena.findReferencingSymbols
Return: [{"severity":"...","category":"security","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Go Agent 5 — Performance Agent** *(pr-review addition)*

```
Review changed Go files for performance issues.
Changed files: <list>

1. N+1 query patterns: loops with per-iteration DB queries; GORM lazy-loading → HIGH
2. Missing indexes on new WHERE/ORDER BY columns for large tables → HIGH
3. Blocking I/O in goroutines that should be async → MEDIUM
4. Unbounded allocations / slice growth in hot paths → MEDIUM
5. O(n²) algorithms where O(n log n) exists → MEDIUM
6. sync.Mutex held across I/O or long computation → HIGH

Tools: Serena.findSymbol → Grep
Return: [{"severity":"...","category":"performance","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Go Agent 6 — Test Coverage Agent** *(pr-review addition)*

```
Review changed Go files for test coverage gaps.
Changed files: <list>

1. New business logic with no *_test.go → HIGH
2. Happy-path-only tests: missing error paths, boundary values, nil/empty → MEDIUM
3. Tests asserting only no-error (no result validation); magic literals; no table-driven → MEDIUM
4. Bug fix with no regression test → HIGH
5. Flaky test risk: time.Sleep, fixed ports, global state, non-seeded random → HIGH
6. External-service calls with only mocks, no integration test → MEDIUM

Optionally run targeted (NOT full suite): go test ./... -run TestXxx -count=1 -short 2>&1 | tail -20
Return: [{"severity":"...","category":"tests","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

---

### Step 2B — Non-Go Path: Dispatch 4 Parallel Agents

*(Skip if LANG = go)*

Launch all four simultaneously. Each must return a **JSON array of findings**.

---

**Non-Go Agent 1 — Security Agent**

```
Review the PR diff for security issues. Language: <detected>.
Changed files: <list>

1. Secrets / credentials hardcoded in tracked source files → CRITICAL
2. Injection risks: SQL string concat, command injection, template injection, path traversal → HIGH
3. Auth/authz gaps: new routes without middleware; missing RBAC checks → HIGH
4. Sensitive data exposure: PII logged, stack traces to clients, verbose error messages → MEDIUM
5. New dependencies — note known CVEs (npm audit, pip-audit if available) → HIGH
6. Cryptography: MD5/SHA1 for security, hardcoded IVs/salts, insecure random → HIGH

Return: [{"severity":"critical|high|medium|low","category":"security","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Non-Go Agent 2 — Performance Agent**

```
Review the PR diff for performance issues. Language: <detected>.
Changed files: <list>

1. N+1 query patterns: loops with per-iteration DB queries; ORM lazy-loading → HIGH
2. Missing indexes on new WHERE/ORDER BY columns → HIGH
3. Blocking sync I/O in async handlers → MEDIUM
4. Large allocations / unbounded growth in hot paths → MEDIUM
5. O(n²) where O(n log n) exists → MEDIUM
6. Bundle size (JS/TS): large imports without tree-shaking → LOW

Return: [{"severity":"high|medium|low","category":"performance","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Non-Go Agent 3 — Style and Conventions Agent**

```
Review the PR diff for style and convention issues. Language: <detected>.
Changed files: <list>

1. PR title format: must follow Conventional Commits (feat/fix/chore/docs/refactor/perf/test/ci/style/revert)
2. Naming: new identifiers follow existing conventions (camelCase vs snake_case, abbreviation style)
3. Documentation: new public functions/types have docstrings; complex logic has inline comments
4. Dead code: commented-out blocks, unused variables, unreachable branches → LOW
5. Magic numbers/strings: literals that should be named constants → LOW
6. PR description: explains WHY, calls out breaking changes, provides test instructions

Return: [{"severity":"medium|low","category":"style","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

**Non-Go Agent 4 — Test Coverage Agent**

```
Review the PR diff for test coverage gaps. Language: <detected>.
Changed files: <list>

1. New business logic with no test file → HIGH
2. Happy-path-only tests: missing error paths, boundary values, nil/empty → MEDIUM
3. Tests asserting only no-error; magic literals; missing arrange/act/assert → MEDIUM
4. Bug fix with no regression test → HIGH
5. Flaky test risk: time.Sleep, fixed ports, global state, non-seeded random → HIGH
6. External-service calls with only mocks, no integration test → MEDIUM

Optionally run targeted tests:
- JS/TS: npx jest --testPathPattern=<changed-test-file> --no-coverage 2>&1 | tail -20
- Python: pytest <changed-test-file> -x -q 2>&1 | tail -20

Return: [{"severity":"high|medium|low","category":"tests","file":"...","line":N,"description":"...","fix":"...","confidence":0.0}]
```

---

### Step 3 — Advisor Gate for CRITICAL/HIGH Security Findings

Call `advisor` before finalizing any CRITICAL or HIGH security findings.
Ask: "Is this finding real? Does surrounding code mitigate it?"
Downgrade if advisor identifies clear mitigation with explicit reasoning.

---

### Step 4 — Aggregate and Report

After all agents complete:

1. **Merge** all arrays
2. **Deduplicate:** findings at `(file + line ±3)` → keep highest severity
3. **Filter noise:** drop if ALL true: single-agent, confidence < 0.65, severity = low, category = style/quality
4. **Sort:** critical → high → medium → low

```
## PR Review — <branch or PR#> — <timestamp>

**Language:** <go | detected-lang>
**Agents:** <6 (arch/quality/resilience/security/perf/tests) | 4 (security/perf/style/tests)>
**Files reviewed:** <N>
**Overall:** ✅ CLEAN | ⚠️ REVIEW NEEDED | ❌ BLOCKING ISSUES

| Severity | Category     | File:Line              | Description | Fix |
|----------|--------------|------------------------|-------------|-----|
| CRITICAL | security     | pkg/repo/query.go:42  | ...         | ... |

**Summary:** N findings (X critical, Y high, Z medium, W low)
```

---

### Step 5 — Post Findings (unless --no-post)

**GitHub:**
```bash
gh pr review <PR#> --comment -b "<findings table>"
```

**Azure DevOps:**
```bash
az repos pr update --id <PR#> --description "<findings table>" \
  --organization "https://dev.azure.com/bofaz" --project "<project>"
```

For stack reviews: post to each layer's PR with that layer's section only.

---

## Skill Map

| Task | Use |
|------|-----|
| Quick Go code review (no posting) | `/pr-review --no-post`, or `/hawk` where this project's `skillOverrides` has it on |
| Thorough Go review + perf/tests + post | `/pr-review` |
| Non-Go PR review | `/pr-review` |
| Stack review (all layers) | `/pr-review --stack` |
| Release readiness (manifest/CHANGELOG/migrations/rollback) | `/release-prep` |
| Test generation for gaps found | `/fury` where this project's `skillOverrides` has it on, otherwise write tests manually |
