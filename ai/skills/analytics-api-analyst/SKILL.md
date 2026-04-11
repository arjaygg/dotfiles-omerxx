---
name: analytics-api-analyst
description: >
  Anthropic Analytics API analyst — mines org-wide usage data (Claude chat,
  Claude Code, Office integrations) using the T1/T2/T3 tiered analysis pattern.
  Use this whenever you need to analyze Claude adoption, CC session activity,
  per-user productivity metrics, domain breakdowns, or retention trends.
  Data is cached locally to avoid repeated API calls. Invoke as /analytics-api-analyst.
version: 1.0.0
triggers:
  - /analytics-api-analyst
---

# /analytics-api-analyst — Anthropic Org Analytics Analyst

## Role

You are a data analyst for Anthropic org usage metrics. You have access to the
Anthropic Analytics API and a local cache of per-user daily data. Follow the
T1→T4 tier pattern from `data-analyst`. Always read from cache first — only
re-fetch if the date range extends beyond what's cached.

---

## Tier Selection

| Signal | Tier |
|---|---|
| "who's active?", "how many sessions?", "top users", "overview" | **T1 Quick** |
| "why is adoption low?", "patterns", "productive vs exploratory?", "retention" | **T2 Deep** |
| "chart", "visualize", "share with team", "report" | **T3 Visual** |
| "alert when adoption drops", "daily summary", "monitor" | **T4 Monitor** |

---

## Data Source

**API endpoint:**
```
GET https://api.anthropic.com/v1/organizations/analytics/users?date=YYYY-MM-DD
Headers: x-api-key, anthropic-version: 2023-06-01
```

**Auth:** Read key from `/tmp/.ant_key` (user saves via `$env.ANTHROPIC_API_KEY | save --force /tmp/.ant_key` in Nushell).

**Cache locations:**
```
/tmp/analytics_march_2026.json   — { "YYYY-MM-DD": [...entries] }
/tmp/analytics_april_2026.json
/tmp/analytics_<month>_<year>.json   — naming convention for new months
```

**Download a new month (only if not cached):**
```javascript
const fs = require('fs');
const key = fs.readFileSync('/tmp/.ant_key', 'utf8').trim();

async function fetchDay(date) {
  let all = [], afterId = null;
  while (true) {
    const url = new URL('https://api.anthropic.com/v1/organizations/analytics/users');
    url.searchParams.set('date', date);
    url.searchParams.set('limit', '100');
    if (afterId) url.searchParams.set('after_id', afterId);
    const res = await fetch(url.toString(), {
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01' }
    });
    const json = await res.json();
    if (!json.data) break;
    all.push(...json.data);
    if (!json.has_more) break;
    afterId = json.last_id;
  }
  return all;
}
```

---

## Aggregate Helper (reuse across tiers)

```javascript
function aggregate(filePath) {
  const byDate = JSON.parse(require('fs').readFileSync(filePath, 'utf8'));
  const userMap = {};
  const daily = {};
  for (const [date, entries] of Object.entries(byDate)) {
    daily[date] = { cc_sessions: 0, conversations: 0, active_users: entries.length };
    for (const { user, chat_metrics: c, claude_code_metrics: cc } of entries) {
      const e = user.email_address.toLowerCase();
      if (!userMap[e]) userMap[e] = {
        email: e, domain: e.split('@')[1], active_days: 0,
        conversations: 0, messages: 0, skills_used: 0,
        cc_sessions: 0, commits: 0, prs: 0,
        loc_added: 0, loc_removed: 0,
        edits_accepted: 0, edits_rejected: 0,
      };
      const u = userMap[e];
      u.active_days++;
      u.conversations += c.distinct_conversation_count;
      u.messages      += c.message_count;
      u.skills_used   += c.distinct_skills_used_count;
      u.cc_sessions   += cc.core_metrics.distinct_session_count;
      u.commits       += cc.core_metrics.commit_count;
      u.prs           += cc.core_metrics.pull_request_count;
      u.loc_added     += cc.core_metrics.lines_of_code.added_count;
      u.loc_removed   += cc.core_metrics.lines_of_code.removed_count;
      u.edits_accepted += cc.tool_actions.edit_tool.accepted_count;
      u.edits_rejected += cc.tool_actions.edit_tool.rejected_count;
      daily[date].cc_sessions   += cc.core_metrics.distinct_session_count;
      daily[date].conversations += c.distinct_conversation_count;
    }
  }
  return { users: Object.values(userMap), daily };
}
```

---

## T1 — Quick Snapshot

Key metrics to always surface:
- Unique active users (total / CC users / Chat-only / Both)
- CC Sessions, Commits, PRs
- LOC Added / Removed
- Messages & Conversations

```
╔══ T1: <MONTH YEAR> ORG SUMMARY ══════════════════
  Unique active users  : N  (CC: N | Chat-only: N | Both: N)
  Conversations        : N
  Messages             : N
  CC Sessions          : N
  Commits / PRs        : N / N
  LOC Added / Removed  : N / N
╚══════════════════════════════════════════════════
```

---

## T2 — Deep Analysis Hypotheses

Standard hypotheses to run for this dataset:

| H# | Question | Key metric |
|---|---|---|
| H1 | Are high-session users productive or exploratory? | commits/session ratio |
| H2 | Which domain drives CC vs Chat? | cc_sessions + conversations by domain |
| H3 | Is adoption growing or declining? | daily avg comparison across months |
| H4 | Retention — who came back month-over-month? | set intersection of email lists |
| H5 | LOC outliers — who's writing the most code? | loc_added top-10 |

Always end T2 with a confirmed/refuted verdict per hypothesis.

---

## T3 — Visual Report

**Output:** `/tmp/analytics_report.html` — dark-themed Chart.js dashboard.

**Standard charts:**
1. **Daily trend** (bar + line overlay): CC Sessions + Active Users over time
2. **Top 10 users** (horizontal bar): CC Sessions vs Commits side-by-side
3. **Domain breakdown** (grouped bar): CC Sessions vs Conversations per domain
4. **KPI cards** (6-up grid): key totals at a glance

After writing: `open /tmp/analytics_report.html`

---

## T4 — Monitoring

For daily adoption tracking, schedule a remote agent via `/schedule`:

```
Every weekday at 9am: fetch yesterday's data, append to cache, run T1 snapshot,
post summary to [Slack channel / Teams webhook].
```

---

## Key Findings (as of April 2026)

- `arjay.gallentes@ph.axos.com` — #1 user by CC sessions (1,386 in March, 95 in April partial)
- `ph.axos.com` domain (23 users) drives **65% of all CC sessions** despite being <8% of users
- **60% retention** from March → April (187/314 users returned)
- April daily avg down 24–38% vs March — worth monitoring through mid-April
- Chat-only users vastly outnumber CC users (258 vs 51 in March)

---

## Related Skills

- `data-analyst` — the T1–T4 base framework this skill implements
- `quarantine-analyst` — same tier pattern for SQL Server quarantine data
