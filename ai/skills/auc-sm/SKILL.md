---
name: auc-sm
description: AUC-Conversion Scrum Master Agent — Sprint delivery tracking for auc-conversion ETL. Use this to check sprint gate status, verify T1 run results, update plans/progress.md, or get the next priority task across all dev agent tracks (A/B/C).
version: 1.0.0
triggers:
  - /auc-sm
---

## Role

SM Agent — Delivery Tracking for auc-conversion ETL.

**Plan:** `docs/plans/2026-04-01-etl-production-readiness-rfc-v2.md` §8.3 (Sprint Map) + §10 (Success Measurements)

## When to Use

- Checking which sprint gate is currently blocking
- Reporting overall RFC completion status (currently ~63%)
- Updating `plans/progress.md` when a sprint gate is cleared
- Identifying the next unblocked task across all agent tracks
- Verifying T1 run checklist before re-running `run_tier1.sh`

## Sprint Gate Summary

| Sprint | Gate Condition | Status |
|---|---|---|
| Sprint 1 | All tests pass -race; `/debug/vars` shows `auc.db.*`; alerts → Splunk | Pending |
| Sprint 2 | T1 re-run: AUC_MEMO_MAIN migrates 1,633,286 rows; 16/16 checks pass | **BLOCKING (P0)** |
| Sprint 3 | `OBS_EXPORTER=stdout` works locally; T1.3/T1.7 no false-FAILs | Pending Sprint 2 |
| Sprint 4 | Shadow 48h zero-delta; memory ≤50% Strategy A | Pending Sprints 2+3 |

## Blocking P0 Defects (must fix before T1 re-run)

1. **S6** — `UpsertRecord` MERGE overflow: `pkg/repo/destination_repo_bulk.go` ~line 1490 (→ auc-dev-b)
2. **R12** — `FeatureFlagChunkProcess=false` default: `config/config.go:153` (→ auc-dev-b)

## Unblocked Open Items (from session handoff)

- Finding 5: Anomaly detection cold start — min buffer threshold (→ auc-qa Sprint 1 A4)
- Finding 6: Stampede test probe timing (→ auc-qa Sprint 1 A4)
- Verify `feat/supervisor-deployment-dev` ConfigMap alignment in auc-deployment-manifest
- ConversionMetric DB migration must run in DEV before merge

## Instructions

1. Read `plans/progress.md` for current session state
2. Read `plans/active-context.md` to understand current focus
3. Sprint 2 (B0) is the absolute critical path — all other work is secondary
4. Report status using the RFC's capability table format (§1 Executive Summary)
5. Update `plans/progress.md` when reporting gate clearance

## Related Skills

- `auc-dev-b` — owns all Sprint 2 P0 fixes
- `bmad-bmm-sprint-status` — sprint status summary with risk surface
- `bmad-bmm-sprint-planning` — for planning next sprint
