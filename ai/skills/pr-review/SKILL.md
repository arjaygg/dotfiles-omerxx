---
name: pr-review
description: >
  PR Review — legacy shim. Stack-aware (Charcoal) and forge-aware (GitHub + Azure DevOps)
  pull-request investigation that posts findings to the PR. Superseded by lensed-review; this
  shim forwards there and pins the PR Review report header and posting behaviour.
triggers:
  - /pr-review
  - thorough pr review
  - full pr review
  - deep pr review
version: 3.0.0
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# PR Review (shim → `lensed-review`)

This skill holds **no review logic**. Its agent set is now lenses in
`ai/skills/lensed-review/lenses.toml`. Retirement record: `ai/skills/REMOVALS.md`.

## Forward

1. Detect forge (GitHub vs Azure DevOps) and PR/stack scope as before — that is PR plumbing, not
   review logic, and stays here.
2. For each PR (or each stack layer, reviewed against its own incremental diff), invoke
   `lensed-review` with lenses `correctness`, `security`, `resilience`, `style`, plus `performance`
   when explicitly requested and `doubt` for adversarial depth.
3. Render the returned findings into the legacy contract below and post, unless `--no-post`.

## Legacy output contract (pinned)

Severity is assigned here at triage time; lenses emit no `severity` field.

- Dedupe on `(file + line ± 3)`, keep the highest severity; drop findings that are single-lens,
  low severity, and style/quality; sort CRITICAL → HIGH → MEDIUM → LOW.

```
## PR Review — <branch or PR#> — <timestamp>

**Language:** <detected-lang>
**Lenses:** <comma-separated lens codes that ran>
**Files reviewed:** <N>
**Overall:** ✅ CLEAN | ⚠️ REVIEW NEEDED | ❌ BLOCKING ISSUES

| Severity | Category     | File:Line              | Description | Fix |
|----------|--------------|------------------------|-------------|-----|

**Summary:** N findings (X critical, Y high, Z medium, W low)
```

- GitHub: `gh pr review <PR#> --comment -b "<findings table>"`
- Azure DevOps: `az repos pr update --id <PR#> --description "<findings table>"
  --organization "https://dev.azure.com/bofaz" --project "<project>"`
- Stack reviews: post each layer's own section to that layer's PR.
