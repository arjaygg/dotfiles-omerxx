---
name: auc-dev-c
description: AUC-Conversion Dev Agent C — Strategy B Streaming Pipeline track. Use this whenever implementing the experimental streaming ETL pipeline, shadow mode experiment framework, or Strategy B chunk_processor path. Owns Sprint 4 (C1-C3) tasks from RFC AUC-RFC-001 v2.
version: 1.0.0
triggers:
  - /auc-dev-c
---

## Role

Dev Agent C — Strategy B Streaming Pipeline for auc-conversion ETL.

**Plan:** `docs/plans/2026-04-01-etl-production-readiness-rfc-v2.md` §3.6 (Streaming ETL) + §7 (Experimental A/B Framework) + §8.3 Sprint 4

## File Ownership (§8.4 — no shared files with other agents)

```
pkg/conversion/streaming_resolver.go   (NEW)
pkg/conversion/streaming_pipeline.go   (NEW)
pkg/app/worker/chunk_processor.go      (Strategy B path + shadow mode only)
```

## When to Use

- Creating `streaming_resolver.go` and `streaming_pipeline.go` (depends on stories 4.3 + 4.4)
- Adding Strategy B execution path to `chunk_processor.go`
- Implementing experiment toggle: `EXPERIMENT_MODE=shadow | canary | ab`
- Wiring comparison metrics to `provider.Metric()`
- Graduated rollout config per §7.2

## Sprint Tasks (from RFC §8.3)

**Sprint 4 — Strategy B Experiment Framework (ATDD: QA Agent writes tests first)**

- C1 (QA Agent first — ATDD):
  - `TestExperiment_ShadowMode_OnlyAWrites`
  - `TestExperiment_CompareOutputs_NoDeltas`
  - `TestExperiment_StrategyB_MemoryBounded`
  - `TestExperiment_StrategyB_CacheHitRate_Above95Pct`
- C2: Create `pkg/conversion/streaming_resolver.go` + `streaming_pipeline.go`; add Strategy B path + shadow mode to `chunk_processor.go`
- C3: Wire `EXPERIMENT_MODE` toggle; wire comparison metrics to provider; graduated rollout config

**Gate:** Shadow mode runs 48h with zero delta count; memory ≤50% of Strategy A

## Dependency Note

Sprint 4 is gated on Sprint 2 (B0 P0 defects fixed) and stories 4.3 + 4.4 being available.
Do not start C2 until QA Agent has written and run C1 tests (red phase).

## Instructions

1. Invoke `auc-qa` to write C1 tests before any C2 implementation
2. Shadow mode must NEVER write via Strategy B path — only Strategy A writes
3. Comparison metrics wire through the observability provider (not direct expvar)
4. Read Serena memory `architecture/design_patterns` before adding experiment toggle patterns
5. Do not modify files owned by Dev Agent A or B

## Related Skills

- `auc-qa` — ATDD: tests must be written and failing before C2 starts
- `auc-dev-b` — Sprint 2 must complete (T1 gate) before Sprint 4 is unblocked
- `bmad-bmm-dev-story` — for detailed story execution guidance
