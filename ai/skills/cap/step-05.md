# Cap Step 5 — Report to User

If a step says read fully and follow step-XX, you read and follow step-XX. No exceptions.

```
Cap v4.1 — Done
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Feature:   <feature>
Language:  <language>
Tests:     <testsCount> passing
Coverage:  <coveragePct>%
Findings:  <findingsResolved> resolved, 0 critical/high remaining
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Resume ID: <runId>  (use /cap --resume <runId> to replay)
Script:    <scriptPath>
```

For portable runtime, use:

```
Resume ID: n/a (portable runtime)
Script:    n/a (Workflow unavailable)
```

If the run returned `blocked: true`, report the blocking reason and recommended action
(e.g. "Code health gate failed — run /cap --mode uplift first").

## Principles Enforced

All 6 principles are enforced via Workflow schema gates when Workflow is available, or via the
portable runtime's phase contracts when it is not:

1. **Test-First (TDD):** Fury writes failing tests before Ironman touches source
2. **Lean-Agile:** Minimum changes — only what's needed to pass tests
3. **DDD:** Scope agent identifies bounded context; all prompts reference it
4. **SOLID:** Stark and Ironman prompts enforce single-responsibility and interface-injection
5. **Evolutionary Architecture:** Extend patterns, no unnecessary abstractions
6. **Continuous Feedback:** Schema validation at every phase — invalid output retries, never proceeds

## Verification

- [ ] The reported `Findings` line shows 0 critical/high remaining, or the run is reported as `blocked` with a reason (evidence: quoted `result.criticalHighRemaining` / `result.blocked` value).
- [ ] Tests are reported as passing before the report is finalized (evidence: `testsCount` sourced from the actual test run, not assumed).
- [ ] Resume ID and Script are populated for Workflow runtime runs, or explicitly `n/a` for portable runtime (evidence: which runtime was used is stated).
- [ ] All 6 principles were enforced by schema gates (Workflow) or phase contracts (portable) — not skipped for expediency (evidence: fix loop iteration count or "no findings" statement).
