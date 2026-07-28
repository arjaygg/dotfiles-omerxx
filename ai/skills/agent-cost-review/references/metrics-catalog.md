# Metrics catalogue

Every metric the report uses, with its definition and where it comes from. The collector
writes all of these into `summary.json`; this file exists so you can explain a number when
someone asks, and so a future change to the report does not have to re-derive them.

## Cost and tokens

| Metric | JSON path | Definition |
|---|---|---|
| Window cost | `totals.cost` | Sum of `ccusage` per-model cost over the window. Measured. |
| Previous-window cost | `totals.cost_previous` | Same for the preceding calendar month. |
| Growth | `totals.cost_growth` | `cost / cost_previous`, as a multiple. |
| Annualised | `totals.annualised` | `cost × 12`. A run-rate, not a forecast — label it as such. |
| Component costs | `components.*` | Modelled split. See `cost-model.md`. |
| Context share | `components.context_share` | `(input + cache_write + cache_read) / total`. The headline overhead number. |
| Generation share | `components.generation_share` | `output_cost / total`. Usually the surprise. |

## Model mix

| Metric | JSON path | Definition |
|---|---|---|
| Cost share | `by_model[].cost_share` | Model's cost ÷ window cost. |
| Token share | `by_model[].token_share` | Model's total tokens ÷ window tokens. |
| Derived base rate | `by_model[].base_rate_per_mtok` | Solved input rate. Compare as ratios, not absolutes. |
| Rate ratios | `rate_ratio_vs_cheapest_major[]` | Each material model's rate ÷ the cheapest material model's. Restricted to models above 5% of cost so a barely-used tier can't set the baseline. |

**The finding to look for:** cost share meaningfully above token share. A model at 8% of
tokens and 32% of cost is the largest single lever in most reviews. State both numbers
together — either alone is unconvincing.

## Session shape

| Metric | JSON path | Definition |
|---|---|---|
| Session count | `sessions.count` | Distinct sessions `ccusage` attributes to the window. |
| Cost per session | `sessions.cost_per_session` | Window cost ÷ session count. |
| Top-10 / top-50 share | `sessions.top10_share`, `top50_share` | Concentration. |
| Tail share | `sessions.tail_share` | Everything below the top 50. |

**Why concentration decides the recommendation:** if the tail is ~half the spend, fixing
individual expensive sessions cannot recover much, so the levers must be defaults and
habits. If instead the top 10 hold most of it, name those sessions and look at what they
did. Check before recommending.

## Context structure

All from the raw transcript sweep — structural ratios only, never dollars.

| Metric | JSON path | Definition |
|---|---|---|
| Raw requests | `structure.requests_raw` | Assistant turns with usage records. ~2× the deduplicated count. |
| Average context | `structure.avg_context_tokens` | `(cache_read + cache_write) / requests`. What each request carries. |
| Context floor | `structure.floor_median` | Median first-turn context: system prompt, standing instructions, skill and agent listings, MCP tool catalogues — everything paid before a project file is read. Sampled over up to 400 sessions. |
| Floor share | `structure.floor_share_of_context` | `floor_median / avg_context_tokens`. The fraction of every request that is boilerplate. |
| Subagent shares | `structure.subagent_*` | Subagent portion of requests, cache reads, and output. |

**Valuing the floor** — this is the arithmetic behind lever 2:

```
floor_cost ≈ cache_read_cost × floor_share_of_context
per_10k    ≈ floor_cost × (10,000 / floor_median)
```

The first line assumes the floor is present in every cached read, which it is — it sits at
the head of the prefix. Quote `per_10k` in the report; "every 10K trimmed is worth $X/month"
is the sentence that makes people actually go and trim.

## Delivered work

| Metric | JSON path | Definition |
|---|---|---|
| PRs merged | `delivered.pull_requests.merged` | `gh search prs --author=@me --merged-at=<window>`. |
| PRs opened | `delivered.pull_requests.opened` | Same with `--created`. |
| Commits | `delivered.commits.total_commits` | `git log --since --until` across the resolved repos. |
| LOC trustworthy | `delivered.commits.loc_trustworthy` | `false` when one repo holds >60% of insertions — generated data or a vendored import. |

When `loc_trustworthy` is `false`, leave LOC out of the report and say why in the caveats.
A million-line diff from a data dump discredits every other number on the page.

## Unit economics — the point of the whole exercise

| Metric | JSON path | Definition |
|---|---|---|
| Cost per merged PR | `unit_economics.cost_per_merged_pr` | Window cost ÷ PRs merged. |
| Previous | `unit_economics.cost_per_merged_pr_prev` | Same for the prior window. |
| Throughput growth | `unit_economics.throughput_growth` | PRs merged ÷ prior PRs merged. |
| Unit cost regression | `unit_economics.unit_cost_regression` | Cost per PR ÷ prior cost per PR. |

The thesis sentence writes itself from two of these: **throughput growth** against **cost
growth**. Their ratio *is* `unit_cost_regression`, and it is the number that tells the
reader whether rising spend was earned.

Read the absolute alongside the ratio. A 4× regression on a figure that is still $28 per
merged PR is a tuning problem worth a few hours; the same regression at $500 per PR is a
different conversation. Say which one it is.
