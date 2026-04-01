---
name: auc-dev-b
description: AUC-Conversion Dev Agent B — Scale Hardening track. Use this whenever fixing P0 defects (S6 MERGE overflow, R11 HPA re-registration, R12 FeatureFlag default), implementing BackpressureController, or hardening chunker/circuit-breaker. Owns Sprint 2 (B0-B4) and Sprint 3 (B5) tasks from RFC AUC-RFC-001 v2.
version: 1.0.0
triggers:
  - /auc-dev-b
---

## Role

Dev Agent B — Scale Hardening track for auc-conversion ETL.

**Plan:** `docs/plans/2026-04-01-etl-production-readiness-rfc-v2.md` §3.9 (S1-S6) + §9.1-9.2 + §9.5 + §8.3 Sprint 2 & 3

## File Ownership (§8.4 — no shared files with other agents)

```
pkg/resilience/**
pkg/scheduler/chunker.go
pkg/migration/preflight_checks.go
pkg/repo/destination_repo_bulk.go   (S6 MERGE sub-batch fix)
pkg/app/worker/heartbeat_registry.go  (R11 re-registration fix)
```

## When to Use

- Fixing S6: `UpsertRecord` must sub-batch via `BatchUpsertRecords` before `buildMergeStatement`
- Fixing R12: `FeatureFlagChunkProcess` default in `config/config.go:153`
- Fixing R11: Worker re-registration when heartbeat returns "worker not found or already dead"
- Implementing `BackpressureController` in `pkg/resilience/backpressure.go`
- Scale hardening S1 (MAX_CHUNKS 10→50), S2 (CB jitter), S3 (ETLRowNumber index validation)

## Sprint Tasks (from RFC §8.3)

**Sprint 2 — Scale Hardening (BLOCKING: Task B0 first)**

- B0 (BLOCKING): 
  - S6: Wire `BatchUpsertRecords` into `UpsertRecord` in `pkg/repo/destination_repo_bulk.go` (~line 1490); `CalculateBatchConfig(columnCount int, avgRowWidthOverride int64)` — 2 params
  - R12: Fix `FeatureFlagChunkProcess` default; add pre-run checklist to `run_tier1.sh`
- B1: QA writes baseline tests (TestBaseline_MaxChunks_*, TestBaseline_UpsertRecord_CurrentlyNoBatchGuard)
- B2: `chunker.go:40` MAX_CHUNKS default 10→50 (S1); CB ±5s jitter (S2); ETLRowNumber index validation in `preflight_checks.go` (S3, warn-only)
- B3: `pkg/resilience/backpressure.go` BackpressureController (<100 lines); wire into poll loop; add `auc.queue_depth` to `vars.go`
- B4: QA mutation tests on backpressure.go + S6 change (≥70%); heuristics: ramp-up flood, oscillation, recovery, CB interaction

**Gate:** T1 re-run — AUC_MEMO_MAIN migrates 1,633,286 rows; all 16/16 checks pass

**Sprint 3 — Worker Re-registration (R11)**

- B5: `pkg/app/worker/heartbeat_registry.go:256` — detect "worker not found or already dead" sentinel; idempotent re-registration + exponential backoff; add `TestHeartbeat_ReregistersWhenWorkerFoundDead`

**Gate:** T1.3/T1.7 no longer false-FAIL during HPA scale-down events

## Instructions

1. B0 is an absolute pre-condition — do not start B2/B3 until B0 passes
2. Always have QA Agent write failing baseline tests before ANY changes
3. `CalculateBatchConfig` takes 2 params: `(columnCount int, avgRowWidthOverride int64)`
4. Mutation targets for S6: boundary condition `len(options.Data) > vs >= MicroBatchSize`
5. Do not modify files owned by Dev Agent A or C

## Related Skills

- `auc-qa` — must run before B1 to write failing baseline tests
- `auc-sm` — T1 re-run gate verification
- `bmad-bmm-dev-story` — for detailed story execution guidance
