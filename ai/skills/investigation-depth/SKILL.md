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

## Common Rationalizations

| Excuse | Rebuttal |
|---|---|
| "The log line clearly shows the error, no need to check anything else" | One source shows *a* symptom, not the cause — a second independent source (K8s events, DB logs, metrics) is what rules out coincidence. |
| "I already know this codebase, I can skip the second source" | Familiarity biases toward the last bug you saw, not this one — the checklist exists precisely to counter that. |
| "The user is in a hurry, just give the fix" | A fix applied without diagnosis risks masking the real cause and creates a second incident — lead with the recommendation, don't skip the analysis behind it. |
| "The command exited 0, so it worked" | Exit code is a process-return-value check, not an artifact check — always verify the actual thing the command claimed to do. |
| "I'll just note findings at the end in one big write" | A single large write risks hitting token limits mid-investigation and losing everything gathered so far — write incrementally. |

## Red Flags

- Root cause stated with only one log/signal source cited as evidence — *checkable*: does the response name two or more independent sources before concluding?
- A fix is applied before the user approved it, when the request was diagnostic in nature.
- "Not yet checked" is absent from a stated conclusion — the show-your-work format was skipped.
- Success is claimed solely from a command's exit code, with no named artifact verification.

## Verification

- [ ] At least two independent sources are named in the final conclusion (evidence: the `Checked: [...]` line lists 2+ sources).
- [ ] A "Not yet checked" line is present alongside every "Checked" line (evidence: both lines appear together in the response).
- [ ] For deploy/migration tasks, an artifact check is named beyond the exit code (evidence: named artifact — index, row count, pod health, API response).
- [ ] Diagnosis-only requests produced no unapproved fix (evidence: fixes are listed as options, not applied, until the user approves).</replace>

