---
name: code-health
description: >
  Analyzes Go code maintainability using a CodeScene-inspired 1-10 Code Health score.
  Measures cyclomatic complexity (Brain Method CCN≥15, Complex Method CCN≥10), function
  length (Large Method ≥70 LOC), cognitive complexity with nesting weight (Nested Complexity),
  and code duplication (DRY Violations). Mines git history for hotspots — files with both
  high churn and complexity violations that are priority refactor targets.
  Outputs a per-file breakdown, overall project score, score band (Healthy/Warning/Alert),
  and a prioritized refactor queue. Use after implementing a feature, before a PR, or to
  assess technical debt. Works on full project or a specific package path.
triggers:
  - /code-health
  - check code health
  - how healthy is this code
  - code quality score
  - assess maintainability
  - complexity report
  - is this code maintainable
  - how complex is this
  - code health report
  - how clean is this code
  - duplication report
  - cyclomatic complexity check
  - show me code quality metrics
  - assess code complexity
  - maintainability analysis
  - what's the technical debt here
  - done implementing, how does it look
  - just finished coding, quality check
  - health score
  - code score
  - complexity score
  - refactoring priorities
  - technical debt assessment
  - where's the technical debt
  - what should I refactor
  - show me refactor priorities
version: 1.1.0
model: sonnet
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Code Health — CodeScene-Inspired 1-10 Scorer

Produces a 1-10 Code Health score for Go code using free tooling (golangci-lint + git history).
Never stops without a complete scored report.

---

## When to Use

- `/code-health` → score all packages in the current project
- `/code-health pkg/scheduler/` → score a specific package
- `/code-health --hotspots` → include git churn analysis (hotspot identification)
- `/code-health --gate 9.5` → score and exit 1 if overall score < 9.5 (CI/gate use)
- `/code-health pkg/worker/ --gate 9.5` → gate check on a specific package

**Bash-callable gate example (for use in ironman self-correction or cap pre-flight):**
```bash
claude /code-health --gate 9.5 pkg/worker/ || echo "GATE FAILED: health below 9.5"
```
Exit codes: `0` = score ≥ threshold (or no `--gate` set), `1` = score < threshold.

---

## Scoring Model

**Biomarkers and weights:**

| Biomarker | Source | Weight |
|---|---|---|
| Brain Method (CCN≥15) | cyclop linter | −1.5 per finding |
| Complex Method (CCN≥10) | cyclop linter | −0.8 per finding |
| Large Method (≥70 LOC) | funlen linter | −0.6 per finding |
| Nested Complexity | gocognit linter | −0.5 per finding |
| DRY Violation | dupl linter | −0.4 per finding |

Start at 10.0, apply penalties, clamp to [1.0, 10.0].

**Bands** (canonical scheme — defined once in the project's `AGENTS.md` § Code Health & Coverage
Gates, referenced here rather than restated, since that table is what `refactor`/`ironman`
actually gate on):
- ≥ 9.5 → **AI-ready** (green): proceed normally
- 7.0–9.4 → **Warning** (yellow): feature work allowed; expect ironman self-correction loops
- < 7.0 → **Alert** (red): run `/cap --mode uplift` first, then retry

---

## Instructions

### Step 1 — Determine Scope

- If `$ARGUMENTS` contains a path: run against that path only
- If `$ARGUMENTS` is empty or `.`: run against `./...`
- If `$ARGUMENTS` contains `--hotspots`: enable git churn analysis in Step 3
- If `$ARGUMENTS` contains `--gate <N>`: record the threshold value; after Step 4 output, exit 1 if overall score < N, exit 0 otherwise

### Step 2 — Run Code Health Linters

**Preferred (if Makefile target exists):**
```bash
make code-health-json 2>/dev/null
```

**Fallback (if no Makefile or running in a non-standard directory):**
```bash
golangci-lint run --timeout=5m --enable cyclop,funlen,gocognit,dupl \
  --output.json.path /tmp/code-health-out.json <SCOPE> 2>/dev/null || true
cat /tmp/code-health-out.json
```

If a `.github/scripts/code-health-score.sh` exists in the project, pipe the JSON output through it for an automatic scored report:
```bash
make code-health-json 2>/dev/null | .github/scripts/code-health-score.sh /dev/stdin 0
```

### Step 3 — Hotspot Analysis (if `--hotspots` or high-severity findings)

For each file with 3+ findings, check git churn (commits in last 90 days):
```bash
git log --since="90 days ago" --format="%H" -- <file> 2>/dev/null | wc -l
```

A file is a **hotspot** if: churn ≥ 5 commits AND ≥ 3 code health findings.
Hotspots are the highest-priority refactor targets — they change often AND are hard to read.

### Step 4 — Score and Report

Parse the golangci-lint JSON output. Count findings per biomarker. Apply the scoring formula.

**If the scorer script ran automatically (Step 2 piped to score.sh):** Display its output directly.

**Otherwise compute manually:**

```
brain_methods    = count of cyclop findings with CCN≥15
complex_methods  = total cyclop findings − brain_methods
large_methods    = count of funlen findings
nested_complexity = count of gocognit findings
dry_violations   = count of dupl findings

score = 10.0
      − (brain_methods    × 1.5)
      − (complex_methods  × 0.8)
      − (large_methods    × 0.6)
      − (nested_complexity × 0.5)
      − (dry_violations   × 0.4)
score = max(1.0, min(10.0, score))
```

**Output format:**

```
Code Health Report — <date>
Overall Score: X.X / 10  (<Band>)

Biomarker Breakdown:
  Brain Method (CCN≥15):    N findings  × -1.5
  Complex Method (CCN≥10):  N findings  × -0.8
  Large Method (funlen):    N findings  × -0.6
  Nested Complexity:        N findings  × -0.5
  DRY Violation (dupl):     N findings  × -0.4

Worst Files (by finding count):
  N issues  <file>  [<linters>]
  ...

Top Hotspots (high churn × complexity):
  <file> — N commits/90d, M findings → Priority refactor target
  ...                          (only if --hotspots or if hotspots found)

Refactor Queue (priority order):
  1. <file> — <worst biomarker> — <why it matters>
  2. ...
```

### Step 4b — Gate Check (when `--gate` is set)

After outputting the report:

1. Compare the computed `score` against the `--gate` threshold
2. If `score < threshold`: append to output:
   ```
   GATE RESULT: FAIL — score X.X < threshold Y.Y
   ```
   Then signal exit code 1 (failure).
3. If `score >= threshold`: append:
   ```
   GATE RESULT: PASS — score X.X >= threshold Y.Y
   ```
   Exit code 0.

When the gate fails, do NOT provide a list of recommendations or start refactoring — the caller decides what to do with the exit code.

### Step 5 — Interpretation

Always append a brief interpretation:
- Which biomarker dominates (largest penalty contributor)
- Whether the score is likely to trigger CI gate failures (if threshold is known)
- Top 1-2 concrete refactor actions (specific functions, not vague "reduce complexity")

**Example interpretation:**
> "Score is dominated by Nested Complexity (76 findings × -0.5 = -38 pts). The top refactor target is `pkg/repo/destination_repo_bulk.go` — 12 findings from both cyclop and gocognit suggest deeply nested transaction logic that could be extracted into smaller helpers. Splitting the bulk insert logic into a 3-step pipeline would likely improve the score by 3-4 points."

---

## Success Criteria

- [ ] golangci-lint ran successfully (exit 0 or finding-count > 0)
- [ ] Score computed from actual findings (not estimated)
- [ ] Per-file breakdown shown for top 10 worst files
- [ ] Hotspots identified if `--hotspots` flag or if any file has ≥5 commits + ≥3 findings
- [ ] Refactor queue prioritized with actionable (not generic) suggestions
