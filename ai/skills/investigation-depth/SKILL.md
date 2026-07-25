---
name: investigation-depth
description: >
  Root-cause analysis and debugging rigor — multi-source verification before
  concluding, a show-your-work checklist, diagnose-vs-fix mode separation, and
  incremental findings writes. Use for any RCA, debugging session, or request
  for a recommendation.
triggers:
  - root cause
  - RCA
  - investigation
  - debugging
  - recommendation
  - why is this failing
---

# Investigation Depth

These rules target the most common failure mode in RCAs and debugging sessions:
concluding too early without enough evidence.

## Multi-source before conclusion

For any RCA or investigation, check at least two independent log/signal sources
(e.g., app logs AND K8s events AND DB logs) before concluding. A single source
is not enough.

## Show your work

Explicitly state what was checked and what was NOT yet checked. Do not declare
a root cause without listing both. Format:

```
Checked: [X, Y]. Not yet checked: [Z].
```

## Lead with the recommendation

When asked for a recommendation, state the concrete recommendation first, then
provide the supporting analysis. Never bury the answer in analysis.

## Never assume exit 0 = success

For deployment and migration operations, always verify actual artifacts
(indexes created, row counts match, pods healthy, API responding) even when
the command exits 0.

## Diagnose vs fix

When the request is diagnosis/investigation, deliver root-cause analysis ONLY
and present proposed fixes as options. Do NOT apply any fix until explicitly
approved. If unsure which mode the user wants, ask before changing anything.

## Write findings incrementally

During long investigations, write findings to a file section-by-section
(≤110 lines per write) instead of one large response or one monolithic Write
— large single outputs hit token limits, lose transcript detail, and stall
background workflow watchdogs.
