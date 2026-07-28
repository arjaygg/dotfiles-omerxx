---
name: silent-failure-hunter
description: Review code for silent failures, swallowed errors, bad fallbacks, and missing error propagation. Use when debugging mysterious behavior or reviewing error handling.
tools: Read, Grep, Glob
model: opus
---

# Silent Failure Hunter (shim → `lensed-review`)

This agent holds **no review logic**. Swallowed errors, bad fallbacks, and missing error
propagation are covered by the `resilience` lens in `ai/skills/lensed-review/lenses.toml`.
Retirement record: `ai/skills/REMOVALS.md`.

## Forward

Load `ai/skills/lensed-review/SKILL.md` and run the `resilience` lens against the requested
scope, narrowed to error-handling paths. Add the `doubt` lens when the caller wants each
suspected silent failure adversarially re-checked before it is reported.

## Legacy output contract (pinned)

One block per finding; `Severity` is assigned at this rendering step, not by the lens.

- **Location**: `location` (file:line)
- **Severity**: HIGH / MEDIUM / LOW
- **Issue**: `trigger_condition` — what the silent failure is
- **Impact**: `potential_consequence` — what observable behaviour results, or won't be observable
- **Fix**: `guard_snippet` — the concrete change that surfaces the error
