# Cap v4.0 — Schema Reference

All schemas are defined in `cap-workflow.js` as plain JavaScript objects passed via the
`schema` option to `agent()`. The Workflow tool validates agent output against the schema
before returning — the agent retries automatically on mismatch.

---

## SCOPE_SCHEMA

Returned by the Scope agent (Phase 1).

```json
{
  "feature": "string — feature description as parsed from $ARGUMENTS",
  "deliverable": "string — exact outcome: feature|fix|refactor",
  "criteria": ["string — acceptance criterion 1", "..."],
  "affectedPkgs": ["string — go package path e.g. pkg/scheduler", "..."],
  "boundedContext": "string — DDD bounded context name",
  "mode": "feature|uplift"
}
```

Required: `feature`, `deliverable`, `criteria`, `affectedPkgs`, `boundedContext`, `mode`

---

## HEALTH_SCHEMA

Returned by the Preflight agent (Phase 2). Skipped in uplift mode.

```json
{
  "score": 9.5,
  "passed": true,
  "worstFiles": ["pkg/scheduler/scheduler.go", "..."]
}
```

Required: `score`, `passed`, `worstFiles`

---

## PLAN_SCHEMA

Returned by the Stark (Plan) agent (Phase 3).

```json
{
  "planPath": "plans/active-context.md",
  "components": ["pkg/scheduler/handler.go:Handler", "..."],
  "interfaces": ["pkg/scheduler/port.go:SchedulerPort", "..."],
  "criteriaCount": 5,
  "valid": true,
  "issues": []
}
```

Required: `planPath`, `components`, `interfaces`, `criteriaCount`, `valid`
Optional: `issues` (populated when valid=false)

Validity criteria (agent self-checks before returning `valid: true`):
- `plans/active-context.md` exists with all required sections
- No TBD or ambiguous language
- All files and function signatures explicitly named
- DDD bounded context identified
- Acceptance criteria checkboxes present

---

## TEST_SCHEMA

Returned by the Fury (Tests) agent (Phase 4).

```json
{
  "testFiles": ["pkg/scheduler/handler_test.go", "..."],
  "testCount": 12,
  "allFailing": true,
  "valid": true,
  "issues": []
}
```

Required: `testFiles`, `testCount`, `allFailing`, `valid`
Optional: `issues`

Validity criteria:
- Test files exist for all components in plan
- Tests compile without syntax errors
- All tests fail for the right reason (not panic, not compile error)
- No placeholder TODO assertions
- Edge cases covered

---

## IMPL_SCHEMA

Returned by the Ironman (Implement) agent (Phase 5).

```json
{
  "testsPassed": true,
  "raceClean": true,
  "changedFiles": ["pkg/scheduler/handler.go", "..."],
  "coveragePct": 87.3,
  "valid": true,
  "issues": []
}
```

Required: `testsPassed`, `raceClean`, `changedFiles`, `valid`
Optional: `coveragePct`, `issues`

---

## REVIEW_SCHEMA

Returned by each Hawk dimension agent (Phase 6). One per dimension.

```json
{
  "dimension": "architecture|quality|resilience|security",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "category": "architecture|quality|resilience|security",
      "file": "pkg/scheduler/handler.go",
      "line": 42,
      "description": "Brief description of the issue",
      "fix": "Concrete actionable fix",
      "confidence": 0.85
    }
  ]
}
```

Required: `dimension`, `findings`
Each finding requires: `severity`, `category`, `file`, `line`, `description`, `fix`, `confidence`

---

## VERDICT_SCHEMA

Returned by adversarial verify agents (one per confirmed finding, Phase 6).

```json
{
  "isReal": true,
  "reasoning": "Found SQL parameterization missing at pkg/repo/query.go:42",
  "adjustedSeverity": "HIGH"
}
```

Required: `isReal`, `reasoning`
Optional: `adjustedSeverity` (if severity should differ from original finding)
