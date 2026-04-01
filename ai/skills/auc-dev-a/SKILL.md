---
name: auc-dev-a
description: AUC-Conversion Dev Agent A — Observability Provider track. Use this whenever implementing or debugging pkg/observability/**, wiring MetricCollector, exporter interfaces, or the provider/collector/noop pattern. Owns Sprint 1 (A0-A4) and Sprint 3 (A5-A6) tasks from RFC AUC-RFC-001 v2.
version: 1.0.0
triggers:
  - /auc-dev-a
---

## Role

Dev Agent A — Observability Provider track for auc-conversion ETL.

**Plan:** `docs/plans/2026-04-01-etl-production-readiness-rfc-v2.md` §4 (Unified Observability Architecture) + §8.3 Sprint 1 & 3

## File Ownership (§8.4 — no shared files with other agents)

```
pkg/observability/**
cmd/*/main.go  (wiring only — no logic changes)
```

## When to Use

- Implementing `pkg/observability/exporter.go`, `provider.go`, `collector.go`, `noop/exporter.go`
- Wiring MetricCollector into the worker WaitGroup
- Calling `RegisterDBStats()` on all 3 DB pools
- Wiring circuit breaker metrics (currently nil at main.go:102)
- Sprint 3: moving Splunk HEC + trace exporter into `pkg/observability/splunk/`
- Creating `pkg/observability/stdout/exporter.go` for local dev

## Sprint Tasks (from RFC §8.3)

**Sprint 1 — Observability Foundation (BLOCKING: Task A0 first)**

- A0: Verify/fix `FeatureFlagChunkProcess` default in `config/config.go:153`
- A1: QA Agent writes failing tests first (TestMetricCollector_*, TestObservabilityProvider_*)
- A2: Create `pkg/observability/exporter.go` (<50 lines, interfaces), `noop/exporter.go` (<30 lines), `provider.go` (<80 lines), `collector.go` (<120 lines, 30s ticker)
- A3: Wire provider in `cmd/conversion-worker/main.go` — replace 4 scattered wiring spots
- A4: QA mutation test on `pkg/observability/intelligence/rules.go` (≥70%)

**Gate:** All tests pass with -race; `/debug/vars` shows `auc.db.*` stats; alerts reach Splunk

**Sprint 3 — Observability Exporter Migration**

- A5: Move `util/logging/splunk_hec_handler.go` → `pkg/observability/splunk/log_exporter.go` (split into queue.go, sender.go, handler.go ≤100 lines each)
- A6: Create `pkg/observability/stdout/exporter.go`; wire `OBS_EXPORTER` env var through `config.FeatureFlags`

**Gate:** `OBS_EXPORTER=stdout` works in local dev

## Instructions

1. Always write failing tests (via auc-qa skill) BEFORE implementing
2. Each new file must stay under the line limit specified in the task
3. Use `pctx execute_typescript` for batched Serena reads
4. Check Serena memory `architecture/design_patterns` before adding new patterns
5. Do not modify files owned by Dev Agent B or C

## Related Skills

- `auc-qa` — must run before A2/A3/A5 to write failing tests
- `auc-sm` — sprint gate tracker
- `bmad-bmm-dev-story` — for detailed story execution guidance
