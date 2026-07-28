# Cost model — turning token counts into a cost decomposition

## Why this is needed

`ccusage` reports cost **per model** and token counts **per bucket** (input, output, cache
write, cache read), but not cost per bucket. The single most useful sentence in an agent
cost review — "80% of this was context handling, 17% was generation" — requires the
cross-tabulation. Hence a small model.

## The arithmetic

Anthropic prices the buckets as fixed multiples of a model's input rate:

| Bucket | Multiple of input rate |
|---|---|
| Input | 1× |
| Output | 5× |
| Cache write (5-minute TTL) | 1.25× |
| Cache read | 0.10× |

So for a model with input rate `r` (per token) and measured token counts:

```
cost = r · (input + 5·output + 1.25·cache_write + 0.10·cache_read)
     = r · weight
```

`cost` is measured by `ccusage`, and `weight` is computed from measured token counts, so
solve for the rate rather than looking it up:

```
r = cost / weight
```

Then each bucket's dollar contribution falls out, and they sum exactly to the measured
total by construction:

```
cost_input       = r · input
cost_output      = r · 5 · output
cost_cache_write = r · 1.25 · cache_write
cost_cache_read  = r · 0.10 · cache_read
```

Do this **per model, not in aggregate.** Models differ by 4–5× in base rate, so a single
blended rate assigns cost to the wrong buckets. The collector script does it per model and
then sums.

## Why solve for the rate instead of using a price list

Three reasons, in order of importance:

1. **It always reconciles.** Component costs sum to the figure `ccusage` reported, so the
   report has no unexplained residual to apologise for.
2. **It survives price changes and new models.** A hardcoded table goes stale silently; the
   solved rate cannot.
3. **It works when the model is unknown to you.** A model released after your knowledge
   cutoff still gets a correct split.

The derived `base_rate_per_mtok` is also directly useful: comparing it across models is
what identifies an over-used premium tier. Report the **ratio** between models rather than
the absolute derived rate — the ratio is robust, while the absolute value inherits any
error in the multiplier assumptions.

## What to say in the report

Label the split as modelled, in the report itself, not just in chat:

> The cost-component split applies the standard cache multipliers — output 5× input, cache
> write 1.25×, cache read 0.10× — and solves each model's base rate from its own measured
> total. Model-level, daily and token figures are measured, not modelled.

Two things weaken the model, both worth a sentence if they apply:

- **1-hour cache TTL** is priced at 2× input rather than 1.25×. If the workload uses
  extended caching, cache-write cost is understated. It does not change the conclusion —
  it makes the context share *larger* — so the finding is directionally safe.
- **Long-context tiers** (above ~200K tokens) carry higher rates on some models. Where
  average context runs high, the solved rate is a blend across tiers. Again this does not
  flip any conclusion.

## Sanity checks before you publish a number

- Component costs sum to the measured total (they will, by construction — verify anyway;
  a mismatch means the token counts and cost came from different scopes).
- Cache read is the largest or second-largest component. If generation dominates, that is
  unusual and interesting — investigate rather than assume an error. It generally means
  very short sessions or very long outputs.
- The derived rate ordering matches the known tier ordering (cheap tier lowest, premium
  highest). If not, the model names are being mis-grouped.
- Read-to-write ratio on cache: `cache_read / cache_write` around 10–20× means caching is
  working. Below ~5× means prefixes are being invalidated constantly, which is its own
  finding — usually mid-session config edits or churning session starts.
