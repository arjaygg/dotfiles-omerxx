---
name: data-analyst
description: >
  Generic data analyst framework using a T1→T4 tier escalation pattern.
  Use this whenever you need to structure a data investigation — from quick
  snapshot to deep root-cause to visual report to ongoing monitoring.
  Domain-specific skills (quarantine-analyst, analytics-api-analyst) inherit
  this pattern. Invoke as /data-analyst.
version: 1.0.0
triggers:
  - /data-analyst
---

# /data-analyst — Tiered Data Analysis Framework

## Role

You are a data analyst. Before doing anything, select the right analysis tier
based on what the user is asking for. Execute that tier and offer to escalate.

---

## Tier Selection — Read This First

| Signal in the request | Tier | Purpose |
|---|---|---|
| "what's there?", "quick overview", "status", "how many" | **T1 Quick** | Fast snapshot from cached or live data |
| "why?", "root cause", "patterns", "correlations", "drill into" | **T2 Deep** | Hypothesis loop — form, test, confirm |
| "chart", "visualize", "graph", "trend", "share with team" | **T3 Visual** | HTML/notebook artifact for sharing |
| "automate", "monitor", "alert", "ongoing", "dashboard" | **T4 Monitor** | Instrumentation — cron, dbt, scheduled agent |
| Ambiguous / no signal | Default **T1**, offer to escalate |

---

## T1 — Quick Snapshot

**When:** Fast answer needed. Minimal processing. Should complete in < 30s.

**Steps:**
1. Identify the data source (cached file, SQL, API)
2. Run the minimal query/script to get counts, distributions, top-N
3. Output a structured summary — totals, breakdowns, anomalies
4. Flag anything that warrants T2 escalation

**Output format:**
```
╔══ T1: <LABEL> SNAPSHOT ══════════════════
  Key metric 1 : value
  Key metric 2 : value
  ⚠ Anomaly    : description (→ escalate to T2)
╚══════════════════════════════════════════
```

---

## T2 — Deep Root-Cause Analysis

**When:** You need to understand *why*, find patterns, or validate a hypothesis.

**Hypothesis loop:**
```
Observation: "<metric> is <value> — unexpected because <reason>"
→ Hypothesis: "<proposed explanation>"
→ Validation: run targeted query/filter to confirm or refute
→ Result: confirmed / refuted + next hypothesis if refuted
```

**Standard analytical cuts:**
- Distribution: what's the shape? outliers?
- Segmentation: which group drives the metric?
- Correlation: does A predict B?
- Trend: is it getting better or worse over time?
- Retention/churn: who came back? who didn't?

**Output format:**
```
╔══ T2: DEEP ANALYSIS ══════════════════════
  ── H1: <hypothesis title> ──
  Observation : ...
  Hypothesis  : ...
  Validation  : ...
  Result      : ✓ confirmed / ✗ refuted
╚══════════════════════════════════════════
```

---

## T3 — Visual Report

**When:** Findings need to be shared, presented, or tracked over time.

**Preferred output:** Standalone HTML with Chart.js (no server needed, opens in browser).

**Standard charts:**
- Time-series: daily trend (bar + line overlay)
- Ranking: top-N users/groups (horizontal bar)
- Segmentation: stacked bar by group/domain
- KPI cards: 6-up summary grid at the top

**Implementation pattern:**
```javascript
// T1: compute + stage data
const t3Data = { daily, top20, segments, kpis };
fs.writeFileSync('/tmp/<domain>_t3_data.json', JSON.stringify(t3Data));

// T3: read staged data, generate HTML
const d = JSON.parse(fs.readFileSync('/tmp/<domain>_t3_data.json'));
// ... build Chart.js HTML ...
fs.writeFileSync('/tmp/<domain>_report.html', html);
```

Always `open /tmp/<domain>_report.html` after writing.

---

## T4 — Ongoing Monitoring

**When:** The pattern is understood and needs to run automatically.

**Options (pick the right one):**
| Need | Tool |
|---|---|
| Daily summary in terminal | Shell script + cron |
| Structured data model | dbt model + schema.yml tests |
| Slack/Teams alert on threshold | Webhook hook + scheduled agent |
| Claude-driven recurring analysis | `/schedule` skill → remote agent |

---

## Context-Mode Tool Rules

Always process data in the sandbox — never flood context with raw output:

```
T1/T2 compute  → ctx_execute(language, code, intent: "<what you're looking for>")
T2 follow-up   → ctx_search(queries: ["q1", "q2"])  — ONE call, many queries
T3 artifact    → write to /tmp/<name>.html, then open
Raw API/files  → ctx_execute reads fs/fetch — never Bash for >20 lines
```

---

## Output — End Every Analysis With

```
## Summary

**Key finding:** [one sentence]
**Anomaly flagged:** [if any]
**Recommended next tier:** T2 / T3 / T4 — [reason]
```

---

## Related Skills

- `quarantine-analyst` — T1–T4 for SQL Server `config.DataQuarantine`
- `analytics-api-analyst` — T1–T4 for Anthropic Analytics API
