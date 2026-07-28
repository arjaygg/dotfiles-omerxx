---
name: agent-cost-review
description: >
  Monthly (or arbitrary-window) AI coding-agent cost and value review — explains where
  token spend actually went, pairs it against shipped work (merged PRs, commits) to get a
  cost-per-unit-delivered figure, and produces a lightweight executive dashboard with
  ranked, costed efficiency levers. Use this whenever the user asks why their Claude Code /
  agent costs spiked, wants a breakdown of token or cost usage for a month, asks "where did
  my tokens go", wants to reduce or optimise agent spend, needs a cost report for
  leadership, or wants to know whether the spend is worth it — even if they don't name this
  skill and even if they only mention "usage" rather than "cost". Also use it for a routine
  month-end spend review. Invoke as /agent-cost-review.
version: 1.0.0
triggers:
  - "why did my costs spike"
  - "where did my tokens go"
  - "token usage for the month"
  - "claude code cost breakdown"
  - "reduce my agent costs"
  - "cost per PR"
  - "monthly usage review"
  - "agent spend report"
---

# Agent Cost Review

Turn raw agent session logs into an answer a person can act on: **what the money bought,
where it leaked, and which three or four changes recover the most.**

The trap this skill exists to avoid is producing a pile of token counts. Token counts are
not an answer. A cost review is only useful if it reaches a *unit economics* statement —
cost per merged PR, per commit, per shipped thing — because that is what tells you whether
rising spend is success or waste. Two months can have identical token totals and opposite
verdicts.

## The shape of the answer

Almost every real cost spike in agentic coding decomposes the same way, and knowing this
up front tells you what to measure:

- **Cache read dominates.** An agent re-sends its whole accumulated context every turn.
  Expect 40–60% of the bill here. It scales with `context_size × number_of_requests`, so
  it is driven by session length and preamble size, not by how much code was written.
- **Cache write is session churn.** Every new session (and every spawned subagent) pays to
  cache a fresh prefix. Many short sessions cost far more than few long ones.
- **Generation is usually a minority.** If output tokens are under ~20% of cost, say so
  plainly — it reframes the whole conversation from "we used it too much" to "each use
  carries too much overhead."
- **One premium model often carries a wildly disproportionate share.** Check cost share
  against token share per model; a 3–5× mismatch is the single biggest lever.
- **There is usually no runaway session to blame.** Check concentration. If the long tail
  is ~half the spend, the fix is defaults and habits, not cleanup.

Confirm each of these against the data rather than asserting them. Sometimes the shape is
different, and that difference is the finding.

## Step 1 — Collect

Run the bundled collector. It does the whole sweep in one pass and writes a JSON summary
plus intermediate files, so you never hand-roll these pipelines:

```bash
bash <skill-dir>/scripts/collect-cost-data.sh 2026-07
```

Pass `--agent claude` (default) to scope to Claude Code only, or `--agent all` to include
Codex/Gemini/other agents that `ccusage` detects. **Ask which the user wants if there is
more than one agent in the data** — mixing them silently makes every ratio wrong, and
people usually mean just the one they are worried about.

Output lands in `~/reports/<YYYY-MM>-agent-cost/` by default (`--out <dir>` to change).
Read `summary.json` from there; it has every number the report needs.

Two things about running it: it takes 2–5 minutes on a month of heavy use because it
sweeps ~1 GB of JSONL, and the shell it runs in matters. See
`references/environment-gotchas.md` before you fight a blocked command — the failures are
predictable and the workarounds are known.

## Step 2 — Decompose cost into components

`ccusage` gives you cost per model and token counts per bucket, but not cost per bucket.
You need the split because "80% of this is context handling" is the finding that makes the
levers obvious.

The collector computes this. `references/cost-model.md` explains the arithmetic (it solves
each model's base rate from its own measured total using the published cache multipliers)
and — more importantly — states its assumption, which you must carry into the report.
Never present a modelled split as measured.

## Step 3 — Get the value side

A cost report without a delivery denominator is not reviewable. The collector pulls merged
and opened PRs and commit counts for the window and the preceding window.

Prefer PRs merged as the unit — it is the closest thing to "shipped." Commits are a
reasonable second. **Avoid lines of code**: generated files, data dumps and vendored
directories routinely produce million-line diffs that make the metric meaningless. The
collector reports LOC but flags outlier repos; if one repo dominates, drop LOC from the
report and say why.

If the repos aren't discoverable or `gh` isn't authenticated, don't skip this step — ask
the user what their unit of delivered work is. A cost-only report invites the wrong
decision.

## Step 4 — Find the levers, and cost each one

A recommendation without a dollar figure gets ignored. For each lever, state the saving,
the basis, and the effort. The four that recur:

1. **Model routing.** Compare each model's cost share to its token share. Where a premium
   tier is carrying a disproportionate share, the saving is
   `share_routable × premium_cost × (1 − 1/rate_ratio)`. Usually the largest single item.
2. **Shrink the per-session preamble.** The collector measures the median first-turn
   context — the fixed cost of standing instructions, skill and agent listings, and tool
   catalogues, before any project file is read. That floor is re-sent every turn, so
   `floor ÷ avg_context` of all cache-read cost is boilerplate. Value each 10K trimmed.
3. **Fewer, longer sessions.** Cache-write total is the churn budget. Resuming instead of
   restarting avoids re-paying it.
4. **Right-size subagent and workflow fan-out.** Each spawned agent pays its own preamble.
   Compare `$/session` for workflow runs against ordinary sessions.

Rank by dollars, not by tidiness. Then sanity-check the total: if the levers sum to more
than ~60% of the bill, you are over-claiming — re-examine the assumptions.

## Step 5 — Write the dashboard

Build from `assets/report-template.html`, which carries the design tokens, dual-theme
setup, and chart patterns. Write the finished page to the output directory and open it.

Structure that works for an executive reader, in this order:

```
Masthead        — one-sentence thesis stating the efficiency gap as two numbers
Headline tiles  — spend · work shipped · cost per unit · overhead share
Executive read  — the verdict and the recoverable amount, in three sentences
Composition     — where the money went, with a table beside the chart
Trend           — daily series; say whether it is an incident or a run-rate
Levers 1..N     — one section each, ending in a costed Action callout
Value & impact  — this window vs the previous one, ending in cost per unit
Recommendations — ranked table with saving, basis, effort, and a target run-rate
Method          — sources, and every caveat, numbered
```

Some judgement about the writing, because this is the part that decides whether the report
lands:

- **Lead with the gap, not the total.** "$4,980" invites "spend less." "Throughput up 2.4×,
  cost up 10.9×" invites "fix the overhead" — which is the actionable read.
- **Say plainly if the spend is worth it.** If cost per merged PR is trivial against
  engineering time, say so in the first paragraph. Otherwise the reader's first instinct is
  to cut usage, which is usually the wrong move and destroys the throughput you just
  documented. The honest frame is nearly always "protect the output, cut the overhead."
- **Put the caveats in the report, not just in chat.** Especially the billing one below.
  A number that gets forwarded needs its own disclaimers attached.
- **No emoji as section markers, no LOC vanity metrics, no unsourced savings.**

## The caveat that matters most

`ccusage` prices tokens at **public API rates**. If the user is on an enterprise seat or
subscription, those dollars are a *usage index*, not an invoice — real cost is a flat seat
plus any overage. Getting this wrong turns a useful report into a misleading one.

So: **ask which billing arrangement applies**, state the answer in the report, and if it is
seat-based, label every figure as equivalent-API-cost and recommend reconciling against the
Console cost report before anyone books a saving. Relative findings (model mix, cache
share, concentration, trend) hold regardless of billing and are the durable part.

Note also that raw transcripts double-count resumed and forked sessions, typically ~2×.
All dollar figures must come from `ccusage`'s deduplicated counts. Raw counts are fine for
structural ratios — context size, subagent share — because uniform duplication cancels out.

## Reference files

| File | Read it when |
|---|---|
| `references/cost-model.md` | Decomposing cost into buckets, or explaining the split |
| `references/environment-gotchas.md` | A shell command is blocked or times out |
| `references/metrics-catalog.md` | You need the exact definition or query for a metric |
| `assets/report-template.html` | Writing the dashboard |
