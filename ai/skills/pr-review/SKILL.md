---
name: pr-review
description: >
  PR Review — language-agnostic parallel 4-agent pull request investigation.
  Spawns Security, Performance, Style/Conventions, and Test-Coverage agents concurrently,
  synthesizes a severity-ranked findings report.
  Complement with /hawk for Go-specific deep architectural analysis.
triggers:
  - /pr-review
  - review this PR
  - review PR
  - review pull request
  - PR review
  - check this PR
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - advisor
---

# PR Review — Language-Agnostic 4-Agent Parallel Investigation

Dispatches four parallel subagents to review a pull request across security, performance,
style/conventions, and test coverage dimensions. Returns a severity-ranked findings table.

**For Go codebases:** pair with `/hawk` — hawk handles architecture, resilience, and
Go-specific patterns; this skill handles the process and cross-cutting quality signals.

## When to Use

- `/pr-review` → review the current branch's diff against its base
- `/pr-review <PR#>` → review a specific GitHub PR by number
- `/pr-review --lang go` → hint the language for more precise checks (default: auto-detect)
- `/pr-review --post` → post findings as a GitHub PR comment via `gh pr review --comment`

---

## Instructions

### Step 1 — Determine Scope

Parse `$ARGUMENTS`:
- If a PR number is given: `gh pr view <N> --json files,body,title,baseRefName` to get the diff
- If empty: use `git diff $(git merge-base HEAD origin/main)..HEAD` (or base branch from Charcoal stack)
- If `--lang <lang>` is given: pass the language hint to each agent
- If `--post` is set: post findings as PR comment after synthesis

Auto-detect language if not specified:
```bash
git diff --name-only HEAD origin/main 2>/dev/null | \
  sed 's/.*\.//' | sort | uniq -c | sort -rn | head -5
```

Load changed files list:
```bash
git diff --name-only $(git merge-base HEAD origin/main 2>/dev/null || echo "HEAD") 2>/dev/null | head -60
```

If no changed files: stop with "No diff found. Pass a PR number or stage changes."

---

### Step 2 — Dispatch 4 Parallel Agents

Launch all four simultaneously. Each must return a **JSON array of findings**.

---

**Agent 1 — Security Agent**

```
Review the PR diff for security issues. Language: <auto-detected or user-specified>.

Changed files: <list>

Check:
1. Secrets / credentials: API keys, tokens, passwords, connection strings hardcoded in source
   (not just .env.example — real secrets committed to tracked files)
2. Injection risks: SQL string concatenation, command injection via user input (os.exec, subprocess,
   shell=True), template injection, path traversal
3. Authentication / authorization gaps: new routes/endpoints without auth middleware; privilege
   escalation via missing RBAC checks
4. Sensitive data exposure: PII logged, stack traces returned to clients, verbose error messages
   exposing internals
5. Dependency additions: new packages added to package.json/go.mod/requirements.txt — note any
   known CVEs (check via `npm audit`, `govulncheck`, or `pip-audit` if available)
6. Cryptography: use of MD5/SHA1 for security, hardcoded IVs/salts, insecure random

Return JSON array:
[{
  "severity": "critical|high|medium|low",
  "category": "security",
  "file": "<path>",
  "line": <N or null>,
  "description": "<what the issue is>",
  "fix": "<concrete fix>",
  "confidence": <0.0-1.0>
}]

Return [] if no findings.
```

---

**Agent 2 — Performance Agent**

```
Review the PR diff for performance issues. Language: <auto-detected or user-specified>.

Changed files: <list>

Check:
1. N+1 query patterns: loops that issue DB queries per iteration; ORM lazy-loading in loops
2. Missing indexes: new WHERE/ORDER BY columns on large tables not covered by an index
3. Synchronous blocking in async context: blocking I/O in async functions (await on CPU work,
   sync HTTP calls in async handlers)
4. Memory allocations: large allocations in hot paths, unbounded slice/map growth in loops
5. Inefficient algorithms: O(n²) or worse where O(n log n) exists; redundant re-computation
6. Cache misses: cacheable data fetched on every request; missing memoization for expensive ops
7. Bundle size (JS/TS): large new imports without tree-shaking; importing entire libs for one util

Return JSON array:
[{
  "severity": "high|medium|low",
  "category": "performance",
  "file": "<path>",
  "line": <N or null>,
  "description": "<what the issue is and estimated impact>",
  "fix": "<concrete fix>",
  "confidence": <0.0-1.0>
}]

Return [] if no findings.
```

---

**Agent 3 — Style and Conventions Agent**

```
Review the PR diff for style, naming, and convention issues. Language: <auto-detected or user-specified>.

Changed files: <list>

Check:
1. PR title format: must follow Conventional Commits (feat/fix/chore/docs/refactor/perf/test/ci/style/revert)
   - Check via: gh pr view --json title if PR number available, else inspect recent commit messages
2. Naming consistency: new identifiers follow existing codebase conventions (camelCase vs snake_case,
   abbreviation style, file naming patterns)
3. Documentation: new exported/public functions and types have docstrings; complex logic has inline comments
4. Dead code: commented-out code blocks, unused variables, unreachable branches
5. Magic numbers/strings: literals that should be named constants
6. Error messages: user-facing error messages follow the project's tone and format conventions
7. File organization: new files placed in the correct directory per project structure; no files in root that
   belong in a subdirectory

Read the PR description (if PR number given) and check:
- Description explains WHY, not just WHAT
- Breaking changes are called out
- Test instructions are provided

Return JSON array:
[{
  "severity": "medium|low",
  "category": "style",
  "file": "<path or 'PR description'>",
  "line": <N or null>,
  "description": "<what the issue is>",
  "fix": "<concrete fix>",
  "confidence": <0.0-1.0>
}]

Return [] if no findings.
```

---

**Agent 4 — Test Coverage Agent**

```
Review the PR diff for test coverage gaps. Language: <auto-detected or user-specified>.

Changed files: <list>

Check:
1. New business logic without tests: functions/methods that process data, validate inputs, or make
   decisions — check if a corresponding test file or test case exists
2. Happy path only: tests exist but only cover the success case; missing error paths, boundary values,
   and nil/empty inputs
3. Test quality: tests that only assert no-error (no result validation); tests with magic literals;
   tests without arrange/act/assert structure
4. Regression coverage: if the PR description mentions fixing a bug, check there is a new test
   that would have caught the original bug
5. Flaky test risk: tests with time.Sleep, fixed ports, global state mutations, or non-deterministic
   data generation without seeding
6. Integration vs unit balance: new external-service calls tested only via unit mocks with no
   integration test at all

If a test runner is available, optionally run:
- Go: `go test ./... -run TestXxx -count=1 -short 2>&1 | tail -20`
- JS/TS: `npx jest --testPathPattern=<changed-test-file> --no-coverage 2>&1 | tail -20`
Do NOT run full test suites — only targeted runs for changed test files.

Return JSON array:
[{
  "severity": "high|medium|low",
  "category": "tests",
  "file": "<path>",
  "line": <N or null>,
  "description": "<what coverage gap exists>",
  "fix": "<what test to add>",
  "confidence": <0.0-1.0>
}]

Return [] if no findings.
```

---

### Step 3 — Advisor Gate for CRITICAL/HIGH Security Findings

Call `advisor` before finalizing any HIGH or CRITICAL security findings.
Ask: "Is this finding real or a false positive? Does the surrounding code mitigate it?"
Downgrade if advisor identifies clear mitigation with reasoning.

---

### Step 4 — Synthesize Findings Report

After all four agents complete:

1. **Merge** all four arrays
2. **Deduplicate:** findings at same file + line ±3 → keep highest severity
3. **Filter noise:** drop if ALL true: single-agent, confidence < 0.65, severity = low, category = style
4. **Sort:** critical → high → medium → low

Print as markdown table:

```
## PR Review — <branch or PR#> — <timestamp>

**Language:** <detected>
**Files reviewed:** <N changed files>
**Overall:** ✅ CLEAN | ⚠️ REVIEW NEEDED | ❌ BLOCKING ISSUES

| Severity | Category | File:Line | Description | Fix |
|----------|----------|-----------|-------------|-----|
| HIGH | security | src/api/auth.go:42 | ... | ... |

**Summary:** N findings (X high, Y medium, Z low)

> For Go-specific architectural and resilience analysis, run `/hawk` on the same diff.
```

If `--post` flag: pipe to `gh pr review --comment -b "<table>"`.

---

## Complementary Skills

| Skill | Covers |
|-------|--------|
| `/hawk` | Go architecture, resilience, goroutine safety, Go-specific security |
| `/release-prep` | Manifest, CHANGELOG, migrations, rollback readiness |
| `/fury` | Test generation and coverage validation |
