---
name: hawk
description: >
  Hawk — Multi-language code reviewer (Go, Python, TypeScript). Default: single focused agent
  covering Architecture, Quality, Resilience, and Security in one pass. Auto-detects project
  language from root files (go.mod → Go, pyproject.toml → Python, tsconfig.json → TypeScript).
  Use --adversarial for parallel multi-agent cross-checking on security-critical or
  pre-release reviews. Pair with fury for test coverage.
  Triggers: hawk review, /hawk, review my code, review my changes, check my code,
  code review, review changed files, reviewing before a commit, review this locally.
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
version: 3.0.0
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

# Hawk — Code Reviewer (Go / Python / TypeScript)

Single-agent code reviewer covering Architecture, Quality, Resilience, and Security in one
pass. Auto-detects language from project root. Use `--adversarial` for 4-agent parallel depth.

**Linting/quality gates** (not handled here — already in CI pre-push):

| Language | Gates |
|---|---|
| Go | `golangci-lint --fix`, `gosec`, `govulncheck`, `go-test-short` |
| Python | `python -m ruff check .`, `python -m mypy .` |
| TypeScript | `npx tsc --noEmit`, `npx eslint .` |

---

## Persistence Directive

Hawk does **not stop midway**. Once invoked:
- Complete the review before returning results
- Aggregate, filter, and rank all findings before reporting
- Use `TodoWrite` to track progress
- Report progress via `TaskUpdate` if `CLAUDE_CODE_TASK_LIST_ID` is set

---

## Dynamic Context

Changed source files in current diff:
```
!git diff HEAD --name-only 2>/dev/null | grep -E '\.(go|py|ts|tsx)$' || echo "(no changed files — pass explicit path as argument)"
```

---

## Session Start — Register Progress

At session start:

1. Create internal `TodoWrite` checklist:
   ```
   TodoWrite([
     { id: "scope",    content: "Determine scope and load context", status: "pending" },
     { id: "impact",   content: "Run impact analysis on changed files", status: "pending" },
     { id: "review",   content: "Run review agent(s)", status: "pending" },
     { id: "advisor",  content: "Call advisor before finalizing CRITICAL findings", status: "pending" },
     { id: "aggregate",content: "Filter and rank all findings", status: "pending" },
     { id: "report",   content: "Output findings table and summary", status: "pending" },
   ])
   ```

2. If `CLAUDE_CODE_TASK_LIST_ID` is set: `TaskUpdate(status: "in_progress", notes: "Hawk: beginning code review")`

---

## When to Use

- `/hawk` → review all changed `.go` files (single-agent, fast)
- `/hawk pkg/scheduler/` → review a specific package
- `/hawk --adversarial` → spawn 4 parallel agents for cross-checking (security-critical, pre-release)
- `/hawk --deep` → switch to Opus for deeper reasoning
- `/hawk --post-pr` → CRITICAL/HIGH posted as inline review comments; MEDIUM/LOW as block summary
- `/hawk --post-pr=block` → all findings as a single block comment (overrides inline behavior)
- `/hawk --effort low` → pre-commit quick check (high-confidence findings only, ≥ 0.85)
- `/hawk --effort max` → exhaustive pre-release audit (includes uncertain findings flagged `[?]`)

---

## Instructions

### Step 1 — Determine Scope

Mark `scope` in_progress.

- If `$ARGUMENTS` contains a path: filter to that path prefix
- If `$ARGUMENTS` is empty: use the injected diff above
- If `--deep` flag: set `model=opus` for spawned agent(s)
- If `--adversarial` flag: set `ADVERSARIAL=true`
- Detect language from root files: `go.mod` → go, `pyproject.toml`/`requirements.txt` → python, `tsconfig.json`+`package.json` → typescript
- If no changed source files (`.go`, `.py`, `.ts`, `.tsx`) AND no relevant config files: stop with "No changed files found. Pass a path argument or stage some changes."

Parse `--effort <level>` from `$ARGUMENTS` (default: `high`):

| `--effort` | `CONFIDENCE_THRESHOLD` | `FLAG_UNCERTAIN` |
|---|---|---|
| `low` | 0.85 | false |
| `medium` | 0.75 | false |
| `high` *(default)* | 0.70 | false |
| `max` | 0.55 | true |

Also collect relevant non-source files changed in the same diff:
```
!git diff HEAD --name-only 2>/dev/null | grep -E '\.(sql|yaml|yml|toml|json)$|Dockerfile|dockerfile' || true
```

Load context in parallel:
```
Serena.readMemory("code_review_guide_ai_assisted")
Read("AGENTS.md")
```

Mark `scope` completed.

---

### Step 2 — Impact Analysis

Mark `impact` in_progress. Report: "Hawk: analyzing impact radius"

For each changed file, identify the 2-level reverse dependency list to pass to the review agent(s)
as "impact radius." Flag issues in DOWNSTREAM packages if a changed interface could break them.

Mark `impact` completed.

---

### Step 3 — Run Review

Mark `review` in_progress.

#### Default mode (single-agent)

Spawn one combined review agent with the following prompt:

---

You are a code reviewer. First detect the project language from root files:
- `go.mod` or `*.go` → **Go** | `pyproject.toml`/`requirements.txt` → **Python** | `tsconfig.json`+`package.json` → **TypeScript**

Review all changed files covering Architecture, Quality, Resilience, and Security.
Return a **complete JSON array** of findings — never respond with "done" or a summary without content.

Apply the language-appropriate checks below. For each dimension, pick the checks matching the detected language.

**Architecture checks:**

*Go:* Repository pattern violation (direct GORM outside `pkg/repo/` → HIGH), missing factory constructor → MEDIUM, K8s manifest in wrong repo → HIGH, OSS compliance (raw prometheus without wrapper → HIGH), circular imports → CRITICAL, downstream blast radius → MEDIUM
*Python:* Circular imports → CRITICAL, missing type hints on public API → MEDIUM, layer violations (business logic in routes → HIGH), god module (>500 LOC doing multiple things → MEDIUM), downstream blast radius → MEDIUM
*TypeScript:* Circular dependencies → CRITICAL, barrel file abuse → MEDIUM, module boundary violations (unexported internals re-exported → MEDIUM), mixed concerns (UI with business logic → HIGH), downstream blast radius → MEDIUM

**Quality checks:**

*Go:* Missing table-driven tests → MEDIUM, missing godoc → LOW/MEDIUM, `fmt.Errorf` without project constructors → MEDIUM, cognitive complexity >4 → MEDIUM / >6 → HIGH, dead code → LOW; Code Health: `make code-health-json 2>/dev/null | .github/scripts/code-health-score.sh /dev/stdin 0` — score ≥7.0 → LOW, 4.0–6.9 → MEDIUM, <4.0 → HIGH, <2.0 → CRITICAL (skip if unavailable)
*Python:* Missing `@pytest.mark.parametrize` on repeated test patterns → MEDIUM, missing docstrings on public API → LOW/MEDIUM, bare `except: pass` → HIGH, cognitive complexity >4 → MEDIUM / >6 → HIGH; run `python -m ruff check . && python -m mypy .`
*TypeScript:* Implicit `any` → MEDIUM, `"strict": true` missing in tsconfig → HIGH, missing test coverage for exports → MEDIUM, cognitive complexity >4 → MEDIUM / >6 → HIGH; run `npx tsc --noEmit && npx eslint .`

**Resilience checks:**

*Go:* Missing circuit breaker → HIGH, goroutine leaks (no context cancel/done chan) → HIGH, context not propagated → MEDIUM, hardcoded timeouts → MEDIUM, missing graceful shutdown → HIGH, downstream cascade risk → MEDIUM
*Python:* Missing context manager on resources → HIGH, async exception swallowing → MEDIUM, hardcoded timeouts → MEDIUM, missing retry/backoff on network calls → MEDIUM, unhandled task cancellation → MEDIUM
*TypeScript:* Unhandled Promise rejection (no `.catch()` or `try/catch`) → HIGH, missing null/undefined guards → MEDIUM, missing React error boundaries → MEDIUM, magic timeout literals → LOW, missing loading/error states → MEDIUM

**Security checks:**

*Go:* SQL injection via `gorm.Raw`/`db.Exec` with string concat → CRITICAL, missing auth middleware → HIGH, hardcoded secrets → CRITICAL, missing request validation → HIGH, unsafe type assertions → MEDIUM, govulncheck (if available) → CRITICAL
*Python:* SQL injection via f-string/`format` → CRITICAL, `subprocess shell=True` with user input → CRITICAL, path traversal without sanitization → HIGH, hardcoded secrets → CRITICAL, `pickle.loads` on untrusted data → HIGH, missing Pydantic/marshmallow validation → HIGH
*TypeScript:* `dangerouslySetInnerHTML`/`innerHTML` with user data → CRITICAL, prototype pollution → HIGH, `eval()`/`new Function()` → CRITICAL, hardcoded secrets → CRITICAL, missing CSRF on state mutations → HIGH, `JSON.parse` without schema validation → MEDIUM

**Non-source file checks** (SQL, Dockerfiles, K8s YAML, config files — apply regardless of language):
- SQL: raw queries with string concat → CRITICAL
- Dockerfile: `COPY . .` exposing secrets, root `USER` → HIGH
- K8s YAML: missing `resources.limits`, `privileged: true` → MEDIUM
- Config (`.toml`, `.json`): hardcoded secrets/API keys → CRITICAL

**Confidence calibration:**
- 0.9+: Saw it directly in the code — no ambiguity
- 0.75–0.89: High confidence, minor interpretation needed
- 0.60–0.74: Inferred from structure or pattern — could be wrong
- < 0.60: Speculative — flag with `[?]` in description

**Severity calibration:**
- CRITICAL: causes data loss, security breach, or build failure in production
- HIGH: causes incorrect behavior or panic under reachable conditions
- MEDIUM: risky pattern or convention violation with real consequences
- LOW: advisory — style, documentation, minor convention

**Tool priority:** `Serena.findSymbol` → `Serena.findReferencingSymbols` → `Serena.getSymbolsOverview` → `Grep`

Return findings as a JSON array matching the finding schema.

---

#### Adversarial mode (`--adversarial`)

Report: "Hawk: launching Architecture, Quality, Resilience, Security agents"

Spawn all 4 simultaneously. Each agent MUST:
1. Read all changed files for their domain
2. Return a **complete JSON array of findings** — never "done" without content

Note: When invoked via Cap v4.0, each dimension agent returns REVIEW_SCHEMA findings.
Cap deduplicates findings in JavaScript (by file+line±3 and by category+description prefix),
then runs an adversarial verify agent per unique finding. No inter-agent messaging is used
or needed — Cap aggregates all findings after all pipeline stages complete.

---

### Agent 1 — Architecture Agent (adversarial only)

Detect language first: `go.mod` → Go, `pyproject.toml`/`requirements.txt` → Python, `tsconfig.json`+`package.json` → TypeScript.

**Go checks:** Repository pattern violation (GORM outside `pkg/repo/` → HIGH), missing factory constructor → MEDIUM, K8s manifest in wrong repo → HIGH, OSS compliance (raw prometheus → HIGH), circular imports → CRITICAL, downstream blast radius → MEDIUM
**Python checks:** Circular imports → CRITICAL, missing type hints on public API → MEDIUM, layer violation (business logic in routes → HIGH), god module >500 LOC → MEDIUM, downstream blast radius → MEDIUM
**TypeScript checks:** Circular deps → CRITICAL, barrel file abuse → MEDIUM, module boundary violations → MEDIUM, mixed concerns (UI+business logic → HIGH), downstream blast radius → MEDIUM

**Confidence calibration:**
- 0.9+: Saw it directly in the code — no ambiguity
- 0.75–0.89: High confidence, minor interpretation needed
- 0.60–0.74: Inferred from structure or pattern — could be wrong
- < 0.60: Speculative — flag with `[?]` in description

**Severity calibration:**
- CRITICAL: causes data loss, security breach, or build failure in production
- HIGH: causes incorrect behavior or panic under reachable conditions
- MEDIUM: risky pattern or convention violation with real consequences
- LOW: advisory — style, documentation, minor convention

**Tool priority:** `Serena.findSymbol` → `Serena.findReferencingSymbols` → `Serena.getSymbolsOverview` → `Grep`

---

### Agent 2 — Quality Agent (adversarial only)

Detect language first: `go.mod` → Go, `pyproject.toml`/`requirements.txt` → Python, `tsconfig.json`+`package.json` → TypeScript.

**Go checks:** Missing table-driven tests → MEDIUM, missing godoc → LOW/MEDIUM, `fmt.Errorf` without project constructors → MEDIUM, cognitive complexity >4 → MEDIUM / >6 → HIGH, dead code → LOW; Code Health: `make code-health-json 2>/dev/null | .github/scripts/code-health-score.sh /dev/stdin 0` — ≥7.0 → LOW, 4.0–6.9 → MEDIUM, <4.0 → HIGH, <2.0 → CRITICAL; hotspot escalation (≥5 commits/90d on top finding file → +1 severity); skip if unavailable
**Python checks:** Missing `@pytest.mark.parametrize` → MEDIUM, missing docstrings → LOW/MEDIUM, bare `except: pass` → HIGH, cognitive complexity >4 → MEDIUM / >6 → HIGH; run `python -m ruff check . && python -m mypy .`
**TypeScript checks:** Implicit `any` → MEDIUM, missing `"strict": true` in tsconfig → HIGH, missing tests for exports → MEDIUM, cognitive complexity >4 → MEDIUM / >6 → HIGH; run `npx tsc --noEmit && npx eslint .`

**Confidence calibration:**
- 0.9+: Saw it directly in the code — no ambiguity
- 0.75–0.89: High confidence, minor interpretation needed
- 0.60–0.74: Inferred from structure or pattern — could be wrong
- < 0.60: Speculative — flag with `[?]` in description

**Severity calibration:**
- CRITICAL: causes data loss, security breach, or build failure in production
- HIGH: causes incorrect behavior or panic under reachable conditions
- MEDIUM: risky pattern or convention violation with real consequences
- LOW: advisory — style, documentation, minor convention

**Tool priority:** `Serena.getSymbolsOverview` → `Serena.findReferencingSymbols` → `Grep`

---

### Agent 3 — Resilience Agent (adversarial only)

Detect language first: `go.mod` → Go, `pyproject.toml`/`requirements.txt` → Python, `tsconfig.json`+`package.json` → TypeScript.

**Go checks:** Missing circuit breaker → HIGH, goroutine leaks (no context cancel/done chan) → HIGH, context not propagated → MEDIUM, hardcoded `time.Duration` literals → MEDIUM, missing graceful shutdown → HIGH, downstream cascade risk → MEDIUM
**Python checks:** Missing context manager on resources → HIGH, async exception swallowing → MEDIUM, hardcoded timeout literals → MEDIUM, missing retry/backoff on network calls → MEDIUM, unhandled task cancellation → MEDIUM
**TypeScript checks:** Unhandled Promise rejection (no `.catch()`/`try-catch`) → HIGH, missing null/undefined guards → MEDIUM, missing React error boundaries → MEDIUM, magic `setTimeout` literals → LOW, missing loading/error states → MEDIUM

**Confidence calibration:**
- 0.9+: Saw it directly in the code — no ambiguity
- 0.75–0.89: High confidence, minor interpretation needed
- 0.60–0.74: Inferred from structure or pattern — could be wrong
- < 0.60: Speculative — flag with `[?]` in description

**Severity calibration:**
- CRITICAL: causes data loss, security breach, or build failure in production
- HIGH: causes incorrect behavior or panic under reachable conditions
- MEDIUM: risky pattern or convention violation with real consequences
- LOW: advisory — style, documentation, minor convention

**Tool priority:** `Serena.findSymbol` → `Serena.findReferencingSymbols` → `Grep`

---

### Agent 4 — Security Agent (adversarial only)

Detect language first: `go.mod` → Go, `pyproject.toml`/`requirements.txt` → Python, `tsconfig.json`+`package.json` → TypeScript.

**Go checks:** SQL injection via `gorm.Raw`/`db.Exec` with string concat → CRITICAL, missing auth middleware → HIGH, hardcoded secrets → CRITICAL, missing `json.Decode` post-validation → HIGH, unsafe `x.(Type)` → MEDIUM, govulncheck (if available) → CRITICAL
**Python checks:** SQL injection via f-string/`format` → CRITICAL, `subprocess shell=True` with user input → CRITICAL, path traversal without sanitization → HIGH, hardcoded secrets → CRITICAL, `pickle.loads` on untrusted data → HIGH, missing Pydantic/marshmallow validation → HIGH
**TypeScript checks:** `dangerouslySetInnerHTML`/`innerHTML` with user data → CRITICAL, prototype pollution → HIGH, `eval()`/`new Function()` → CRITICAL, hardcoded secrets → CRITICAL, missing CSRF on state mutations → HIGH, `JSON.parse` without schema validation → MEDIUM


**Confidence calibration:**
- 0.9+: Saw it directly in the code — no ambiguity
- 0.75–0.89: High confidence, minor interpretation needed
- 0.60–0.74: Inferred from structure or pattern — could be wrong
- < 0.60: Speculative — flag with `[?]` in description

**Severity calibration:**
- CRITICAL: causes data loss, security breach, or build failure in production
- HIGH: causes incorrect behavior or panic under reachable conditions
- MEDIUM: risky pattern or convention violation with real consequences
- LOW: advisory — style, documentation, minor convention

**Tool priority:** `Serena.getSymbolsOverview` → `Grep` → `Serena.findReferencingSymbols`

---

### Step 4 — Advisor Gate (Batch Calibration)

Mark `advisor` in_progress.

If there are **no CRITICAL or HIGH findings**, skip this step entirely — mark `advisor` completed and proceed.

Otherwise, collect all CRITICAL and HIGH findings into a single list and call `advisor` **once** with
the complete list. Per-finding calls are forbidden — one batch call gives the advisor cross-finding
context and ensures consistent calibration.

Advisor prompt:
> "Review these N findings (X critical, Y high). For each finding:
> 1. Is it real or a false positive? (e.g., is SQL parameterization already present in a non-obvious form?)
> 2. Is the severity correct — should any HIGH be promoted to CRITICAL, or any CRITICAL downgraded?
> 3. Are there patterns across findings that suggest a systemic problem rather than isolated bugs?
> Apply the same calibration standard across all findings."

Incorporate advisor feedback:
- Downgrade CRITICAL → HIGH for confirmed false positives (requires explicit advisor reasoning)
- Promote HIGH → CRITICAL when advisor identifies under-reported severity
- If advisor notes a systemic pattern, carry that note into the executive summary (Step 6)

Mark `advisor` completed.

---

### Step 5 — Aggregate and Report

Mark `aggregate` in_progress.

1. **Merge** all agent findings into one array
2. **Deduplicate** (adversarial mode only): a finding is a duplicate if it matches on EITHER
   `(file + line ± 3)` OR `(file + category + first 20 chars of description normalized to lowercase)`.
   Keep the highest severity instance. The second criterion catches semantic duplicates where two agents
   flag the same issue at slightly different lines.
3. **Filter noise:** Drop findings below `CONFIDENCE_THRESHOLD`. If `FLAG_UNCERTAIN=true` (effort=max), include findings at confidence ≥ 0.55 but append `[?]` to descriptions of any finding below 0.70 confidence.
4. **Sort:** CRITICAL → HIGH → MEDIUM → LOW

Mark `aggregate` completed. Report via TaskUpdate: "Hawk: N findings (X critical, Y high, Z medium, W low)"

---

### Step 6 — Output

Mark `report` in_progress.

#### 6a — Generate Executive Summary

Before printing any findings, compose a 3-sentence executive summary:

1. **What changed:** Infer from changed file paths and finding categories (e.g., "This diff adds a new HTTP handler in `pkg/api/` and updates the scheduler").
2. **Primary concern:** Describe the dominant finding theme, or "No significant issues found" if clean.
3. **Verdict:** Derive deterministically from the ranked findings:

| Condition | Verdict |
|-----------|---------|
| Any CRITICAL finding | **Request changes** — critical issues found |
| HIGH ≥ 2 | **Request changes** |
| HIGH = 1 | **Needs work** before merge |
| MEDIUM only (no HIGH/CRITICAL) | **Approve** with minor suggestions |
| LOW only | **Approve** with minor notes |
| No findings | **LGTM** — no issues found |

Print the summary as a blockquote before the findings table:

```
> **Hawk review** · X critical · Y high · Z medium · W low
>
> [Sentence 1: what changed]. [Sentence 2: primary concern]. **Verdict: [VERDICT]**
```

#### 6b — Print Findings Table

If there are **no findings** after filtering, skip the table entirely. The executive summary
blockquote from 6a is the complete output — do not print an empty table.

Otherwise, print the findings table:
```
| Severity | Category | File:Line | Description | Fix |
|----------|----------|-----------|-------------|-----|
| CRITICAL | security | pkg/repo/query.go:42 | ... | ... |
```

#### 6c — Post to PR (if `--post-pr`)

- Detect PR number: `gh pr view --json number --jq '.number' 2>/dev/null`
- Detect repo: `gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null`
- Get head SHA: `gh pr view <N> --json headRefOid --jq '.headRefOid'`

If `--post-pr=block`: post summary + full findings table as one block comment:
  `gh pr review <N> --comment -b "<summary blockquote>\n\n<full findings table>"`

Otherwise (default `--post-pr`):
  Post the summary as a standalone block comment first:
  `gh pr review <N> --comment -b "<summary blockquote>"`

  **Validate line anchors against the diff before posting inline.** GitHub rejects
  (HTTP 422) review comments whose `line` is not part of the PR's diff hunks. Fetch
  the changed line ranges first:
  ```bash
  # Map of changed (RIGHT-side) line ranges per file
  gh pr diff <N> | awk '
    /^\+\+\+ b\//   { file = substr($2, 3) }
    /^@@/           { split($3, a, ","); start = substr(a[1], 2);
                      len = (a[2] == "" ? 1 : a[2]); print file ":" start "-" start+len-1 }'
  ```

  Then for each CRITICAL or HIGH finding **whose `file:line` falls inside a hunk range**,
  post an inline review comment:
  ```bash
  gh api repos/<owner>/<repo>/pulls/<N>/comments \
    --method POST \
    --field body="**[hawk] SEVERITY — CATEGORY**\n\nDESCRIPTION\n\n**Fix:** FIX" \
    --field commit_id="<head SHA>" \
    --field path="FILE" \
    --field line=LINE \
    --field side="RIGHT"
  ```

  CRITICAL/HIGH findings **outside** any hunk are never dropped and never posted inline —
  include them in the block comment table below with their `file:line` references.

  Then post MEDIUM/LOW findings plus any out-of-hunk CRITICAL/HIGH findings as one block comment:
  `gh pr review <N> --comment -b "<table of remaining findings>"`
  If there are none, skip the block comment entirely.

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

- [ ] Review agent(s) completed (no partial results)
- [ ] CRITICAL findings verified by advisor
- [ ] Findings filtered by confidence threshold and ranked
- [ ] Executive summary with verdict printed before findings table
- [ ] Markdown table output with actionable fixes
- [ ] TaskUpdate reported completion to shared task list
- [ ] Summary + CRITICAL/HIGH as inline comments; MEDIUM/LOW as block summary (when --post-pr)
