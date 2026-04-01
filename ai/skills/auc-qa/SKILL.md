---
name: auc-qa
description: AUC-Conversion QA Agent — Test-first, mutation-verified testing for the auc-conversion ETL. Use this whenever writing failing tests before implementation (ATDD), running mutation testing on pkg/observability or pkg/resilience, or validating heuristic test coverage. Called by all Dev Agents before implementation starts.
version: 1.0.0
triggers:
  - /auc-qa
---

## Role

QA Agent — Test-First + Mutation for auc-conversion ETL.

**Plan:** `docs/plans/2026-04-01-etl-production-readiness-rfc-v2.md` §5.3 (Testing Protocol) + §8.3 (QA tasks per sprint)

## File Ownership (§8.4)

```
*_test.go within each dev agent's scope
tests/integration/observability/**
```

## When to Use

- Before Dev Agent A starts A2: write `TestMetricCollector_PopulatesRingBuffer`, `TestMetricCollector_TriggersDetectorEvaluation`, `TestNoopExporter_NeverErrors`, `TestObservabilityProvider_WiresCorrectly_FromConfig`
- Before Dev Agent B starts B2: write `TestBaseline_MaxChunks_CurrentlyTen`, `TestBaseline_CBOpenDuration_NoJitter`, `TestBaseline_BackpressureNotActive`, `TestBaseline_UpsertRecord_CurrentlyNoBatchGuard`
- Before Dev Agent C starts C2: write `TestExperiment_ShadowMode_OnlyAWrites`, `TestExperiment_CompareOutputs_NoDeltas`, `TestExperiment_StrategyB_MemoryBounded`, `TestExperiment_StrategyB_CacheHitRate_Above95Pct`
- Running mutation tests after implementation (target ≥70% mutation kill rate)
- Fixing PR #154 findings: Finding 5 (min buffer ≥5 entries), Finding 6 (stampede probe timing)

## Sprint QA Tasks (from RFC §8.3)

**Sprint 1 (A1, A4):**
- A1: Write 4 failing observability tests (red phase)
- A4: Mutation test `pkg/observability/intelligence/rules.go` (≥70%); fix Finding 5 + Finding 6

**Sprint 2 (B1, B4):**
- B1: Write 4 baseline capture tests before any scale hardening changes
- B4: Mutation test `pkg/resilience/backpressure.go` + `pkg/repo/destination_repo_bulk.go` S6 change (≥70%); heuristics: ramp-up flood, oscillation, recovery, CB interaction

**Sprint 4 (C1):**
- C1: Write 4 ATDD experiment tests (red phase, shadow mode + memory bounds)

## Instructions

1. **Always write tests first** — tests must fail before dev implementation
2. Use `go test -race ./...` to validate
3. Mutation heuristics for S6 boundary: test BOTH `> MicroBatchSize` AND `>= MicroBatchSize`
4. Baseline tests (B1) must capture CURRENT behavior as assertions before any changes — they will break when the change is correct
5. Read Serena memory `mutation_testing_patterns` before writing mutation tests
6. Read Serena memory `go_testing_challenges` for known Go test pitfalls in this repo
7. Integration tests go to `tests/integration/observability/`

## Related Skills

- `bmad-bmm-testarch-atdd` — ATDD workflow guidance
- `bmad-bmm-testarch-test-review` — post-implementation test quality review
- `auc-dev-a`, `auc-dev-b`, `auc-dev-c` — invoke this skill before their implementation tasks
