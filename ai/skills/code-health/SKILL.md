---
name: code-health
description: >
  Code Health — legacy shim. CodeScene-inspired 1-10 Go maintainability score from cyclop,
  funlen, gocognit, and dupl biomarkers plus git-churn hotspots. Superseded by lensed-review's
  style lens; this shim forwards there and pins the score report, gate check, and refactor queue.
triggers:
  - /code-health
  - code health report
  - health score
version: 2.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Code Health (shim → `lensed-review`)

This skill holds **no analysis logic**. Complexity, length, nesting, and duplication checks are
the `style` lens in `ai/skills/lensed-review/lenses.toml`. Retirement record:
`ai/skills/REMOVALS.md`.

## Forward

Invoke `lensed-review` with the `style` lens only, scoped to the requested path (default: whole
project). `--hotspots` and `--gate <threshold>` are handled by this shim, not by the lens.

## Legacy output contract (pinned)

Bucket the returned findings by biomarker and apply the unchanged scoring formula:

```
score = 10.0
      − (brain_methods     × 1.5)   # cyclop CCN ≥ 15
      − (complex_methods   × 0.8)   # remaining cyclop
      − (large_methods     × 0.6)   # funlen
      − (nested_complexity × 0.5)   # gocognit
      − (dry_violations    × 0.4)   # dupl
score = max(1.0, min(10.0, score))
```

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
Top Hotspots (high churn × complexity):
Refactor Queue (priority order):
```

- `--gate <threshold>`: append `GATE RESULT: FAIL — score X.X < threshold Y.Y` and exit 1, or
  `GATE RESULT: PASS — score X.X >= threshold Y.Y` and exit 0. On failure, emit no
  recommendations — the caller decides.
- Always append a short interpretation: dominant biomarker and the top 1–2 concrete refactors.
