---
name: ai-usage-analyst
description: >
  Combined AI tool usage analyst — mines org-wide adoption data across multiple
  providers (Anthropic: Claude chat, Claude Code, Office integrations; Cursor:
  Tab, Agent, leaderboard) using the T1/T2/T3 tiered analysis pattern. Use this
  whenever you need to analyze Claude/Cursor adoption, CC session activity,
  Cursor Tab/Agent activity, per-user productivity metrics, domain breakdowns,
  retention trends, or a single combined dashboard across tools. Data is cached
  locally per provider to avoid repeated API calls. Invoke as /ai-usage-analyst.
version: 2.0.0
triggers:
  - /ai-usage-analyst
---

# /ai-usage-analyst — Combined AI Tool Usage Analyst

## Role

You are a data analyst for org-wide AI coding tool usage, spanning multiple
providers. You have access to the Anthropic Analytics API, the Cursor
Analytics API, and local per-provider caches. Follow the T1→T4 tier pattern
from `data-analyst`. Always read from cache first — only re-fetch if the date
range extends beyond what's cached. The goal is **one combined dashboard**
across tools, not separate per-tool reports — merge providers into a single
`userMap`/`daily` structure before presenting any tier.

---

## Tier Selection

| Signal | Tier |
|---|---|
| "who's active?", "how many sessions?", "top users", "overview" | **T1 Quick** |
| "why is adoption low?", "patterns", "productive vs exploratory?", "retention" | **T2 Deep** |
| "chart", "visualize", "share with team", "report", "dashboard" | **T3 Visual** |
| "alert when adoption drops", "daily summary", "monitor" | **T4 Monitor** |

---

## Provider Registry

Each provider defines: endpoint(s), auth, cache location, and a per-provider
fetch function. All providers normalize into the same per-user shape before
merging (see Aggregate Helper).

### Provider: `anthropic` (Claude chat + Claude Code)

**API endpoint:**
```
GET https://api.anthropic.com/v1/organizations/analytics/users?date=YYYY-MM-DD
Headers: x-api-key, anthropic-version: 2023-06-01
```

**Auth:** Read key from `/tmp/.ant_key` (user saves via `$env.ANTHROPIC_API_KEY | save --force /tmp/.ant_key` in Nushell).

**Cache locations:**
```
/tmp/analytics_march_2026.json   — { "YYYY-MM-DD": [...entries] }
/tmp/analytics_<month>_<year>.json   — naming convention for new months
```

**Download a new month (only if not cached):**
```javascript
const fs = require('fs');
const key = fs.readFileSync('/tmp/.ant_key', 'utf8').trim();

async function fetchAnthropicDay(date) {
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

### Provider: `cursor` (Tab + Agent)

**API base:** `https://api.cursor.com`

**Auth:** HTTP Basic — API key as username, empty password. Load from
`~/.secrets/cursor.env` (`CURSOR_API_KEY`).

**Critical pitfalls:**
- `users=` is **case-sensitive** — always lowercase emails. Mixed case returns
  `totalUsers: 0` and empty `data` (false zeros, not zero usage).
- Max window is **30 days per request** (`startDate=30d&endDate=today`) —
  `60d` returns 400.
- Leaderboard `pageSize` must be ≤ 250.
- Canonical emails: read `params.userMappings` from any successful by-user response.

**Endpoints:**
```
GET /analytics/by-user/tabs?startDate=30d&endDate=today&users={lowercase,comma-separated}
GET /analytics/by-user/agent-edits?startDate=30d&endDate=today&users=...
GET /analytics/team/leaderboard?startDate=30d&endDate=today&users=...&pageSize=250
```

**Covering a 90-day default period:** the 30-day cap is per-request, not a
hard ceiling on total coverage — stitch **three consecutive 30-day windows**
(e.g. `60d–30d`, `30d–today` in two calls plus one for the oldest third,
computed as explicit `YYYY-MM-DD` bounds rather than relative tokens once
you're past the most recent 30 days) and merge their `data` arrays by email
before aggregating. Cache each 30-day slice independently (see below) so a
later 90-day request can reuse already-fetched slices instead of re-fetching
the whole range.

**Cache locations:**
```
/tmp/cursor_<startdate>_<enddate>.json   — one file per fetched 30-day slice
  (e.g. cursor_2026-04-19_2026-05-19.json), NOT one file per 90-day request —
  slices are reusable across overlapping date ranges. Stores the COMBINED shape
  { "tabs": {...raw tabs response}, "agent": {...raw agent-edits response}, "leaderboard": {...} }
  i.e. exactly the object fetchCursorWindow() returns, JSON-dumped as one file — NOT
  three separate per-endpoint files. aggregateCursor() reads cursorWindow.tabs.data /
  cursorWindow.agent.data directly, so a per-endpoint cache split will silently
  produce all-zero counts (tabs.data ?? [] -> []) rather than an error.
```

**Fetch (only if not cached) — ported from `team-ai-usage/cursor-license-check.nu`,
the proven, already-shipped implementation. Field names and response shape
below are taken directly from that script, not guessed:**

```javascript
async function fetchCursorWindow(apiKey, emails, startDate = '30d', endDate = 'today') {
  const auth = Buffer.from(`${apiKey}:`).toString('base64');
  const users = emails.map(e => e.toLowerCase()).join(',');
  const headers = { Authorization: `Basic ${auth}` };

  const [tabs, agent, leaderboard] = await Promise.all([
    fetch(`https://api.cursor.com/analytics/by-user/tabs?startDate=${startDate}&endDate=${endDate}&users=${users}`, { headers }).then(r => r.json()),
    fetch(`https://api.cursor.com/analytics/by-user/agent-edits?startDate=${startDate}&endDate=${endDate}&users=${users}`, { headers }).then(r => r.json()),
    fetch(`https://api.cursor.com/analytics/team/leaderboard?startDate=${startDate}&endDate=${endDate}&users=${users}&pageSize=250`, { headers }).then(r => r.json()).catch(() => null),
  ]);
  return { tabs, agent, leaderboard };
}
```

**Response shape (confirmed from the shipped `.nu` script, NOT a flat array):**
`tabs.data` and `agent.data` are **objects keyed by lowercased email**, each
value an array of per-day rows:

```
tabs.data  = { "user@ph.axos.com": [ { date, total_accepts, ... }, ... ], ... }
agent.data = { "user@ph.axos.com": [ { date, total_accepted_diffs, total_lines_accepted, ... }, ... ], ... }
leaderboard.data = { tab_leaderboard: { data: [ {email, rank, ...} ] }, agent_leaderboard: { data: [ {email, rank, ...} ] } }
```

Real field names (verified against the script, do not substitute camelCase
guesses like `totalAccepts`/`acceptedLines`):
- Tab rows: `total_accepts`
- Agent rows: `total_accepted_diffs` (count), `total_lines_accepted` (LOC)
- "Active day" = a day where `total_accepts + total_accepted_diffs > 0` (per
  the script's `active-days` helper) — a day with zero of both doesn't count
  even if the row exists.

Prefer `team-ai-usage`'s `cursor-license-check.nu` script directly over
ad-hoc calls when this skill is invoked from that repo for a **license-gate**
decision — it already lowercases emails, applies the recommendation scoring
below, and writes `reports/license-check-30d.json`. For the combined
dashboard this skill produces, call the API directly (or read that JSON
report as a cache hit if it's fresh) since the dashboard needs the daily
per-tool breakdown, not just the 30d license-gate rollup.

---

## Aggregate Helper (merges all providers into one combined map)

```javascript
function aggregateAnthropic(userMap, daily, filePath) {
  const byDate = JSON.parse(require('fs').readFileSync(filePath, 'utf8'));
  for (const [date, entries] of Object.entries(byDate)) {
    daily[date] ??= { cc_sessions: 0, conversations: 0, tab_accepts: 0, agent_accepts: 0, active_users: 0 };
    daily[date].active_users += entries.length;
    for (const { user, chat_metrics: c, claude_code_metrics: cc } of entries) {
      const e = user.email_address.toLowerCase();
      userMap[e] ??= emptyUser(e);
      const u = userMap[e];
      u.sources.add('claude');
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
}

// tabs.data / agent.data are objects KEYED BY LOWERCASED EMAIL -> array of
// daily rows, not flat arrays — see Response shape note above. Ported from
// the real `.nu` script's `sum-col`/`active-days` logic, not re-derived.
function aggregateCursor(userMap, daily, { tabs, agent, leaderboard }) {
  for (const [rawEmail, rows] of Object.entries(tabs?.data ?? {})) {
    const e = rawEmail.toLowerCase();
    userMap[e] ??= emptyUser(e);
    const u = userMap[e];
    u.sources.add('cursor');
    for (const row of rows) {
      u.tab_accepts += row.total_accepts ?? 0;
      if ((row.total_accepts ?? 0) > 0) u.tab_active_days++;
    }
  }
  for (const [rawEmail, rows] of Object.entries(agent?.data ?? {})) {
    const e = rawEmail.toLowerCase();
    userMap[e] ??= emptyUser(e);
    const u = userMap[e];
    u.sources.add('cursor');
    for (const row of rows) {
      u.agent_accepts += row.total_accepted_diffs ?? 0;
      u.agent_lines   += row.total_lines_accepted ?? 0;
      if ((row.total_accepted_diffs ?? 0) > 0) u.agent_active_days++;
    }
  }
  for (const row of leaderboard?.data?.tab_leaderboard?.data ?? []) {
    const e = row.email?.toLowerCase();
    if (e && userMap[e]) userMap[e].tab_rank = row.rank ?? null;
  }
  for (const row of leaderboard?.data?.agent_leaderboard?.data ?? []) {
    const e = row.email?.toLowerCase();
    if (e && userMap[e]) userMap[e].agent_rank = row.rank ?? null;
  }
}

function emptyUser(email) {
  return {
    email, domain: email.split('@')[1], active_days: 0,
    sources: new Set(),                    // 'claude' and/or 'cursor' — drives the Claude/Cursor/Both split in T1
    conversations: 0, messages: 0, skills_used: 0,   // messages/skills_used: raw counters only, not yet surfaced in any tier template — pull into T2 domain/retention analysis, don't treat as dead
    cc_sessions: 0, commits: 0, prs: 0,
    loc_added: 0, loc_removed: 0,
    edits_accepted: 0, edits_rejected: 0,
    tab_accepts: 0, tab_active_days: 0, tab_rank: null,
    agent_accepts: 0, agent_active_days: 0, agent_lines: 0, agent_rank: null,
  };
}

// License-gate style coaching signal, adapted from the `.nu` script's
// `recommend` function — reuse it here to flag T1/T2 coaching candidates,
// not just for the standalone license-check workflow. Only call this for
// users with `u.sources.has('cursor')` — a claude-only user has all-zero
// cursor fields and would otherwise get a meaningless `defer_other_tools`
// verdict that reads as if their Cursor usage was actually evaluated.
function cursorRecommendation(u) {
  let score = 0;
  if (u.tab_active_days >= 4) score++;
  if (u.agent_active_days >= 4) score++;
  if (u.tab_accepts >= 20) score++;
  if (u.agent_accepts >= 10) score++;
  if (u.agent_lines >= 500) score++;
  if (score >= 4) return 'approve_or_discuss_claude';
  if (score >= 2) return 'coach_cursor_first';
  return 'defer_other_tools';
}

function aggregate({ anthropicFile, cursorWindow, periodDays = 90 }) {
  const userMap = {}, daily = {};
  if (anthropicFile) aggregateAnthropic(userMap, daily, anthropicFile);
  if (cursorWindow) aggregateCursor(userMap, daily, cursorWindow);
  const users = Object.values(userMap).map(u => deriveMetrics(u, periodDays));
  const claudeOnly = users.filter(u => u.sources.has('claude') && !u.sources.has('cursor'));
  const cursorOnly = users.filter(u => u.sources.has('cursor') && !u.sources.has('claude'));
  const both = users.filter(u => u.sources.has('claude') && u.sources.has('cursor'));
  return { users, daily, claudeOnly, cursorOnly, both };
}
```

T1's "Unique active users : N (Claude: N | Cursor: N | Both: N)" line reads directly off
`aggregate()`'s returned `{ users, claudeOnly, cursorOnly, both }` — do not re-derive this
classification ad hoc downstream.

### Derived Productivity/Performance Metrics

Raw counters (sessions, accepts, LOC) answer "how much activity" but not "how
productive" or "how consistent" — the two questions a performance/productivity
read actually needs. `deriveMetrics` computes these on top of the raw counters
so every tier (T1 headline, T2 hypotheses, T3 charts) can pull from the same
fields instead of re-deriving ratios ad hoc:

```javascript
function deriveMetrics(u, periodDays) {
  // Returns null (not 0) when the denominator is 0 — a tool this person never
  // touched must render as "—"/N-A downstream, never as "0%", which would
  // read as "used it and got zero acceptance." Confirmed by forward-test:
  // a cursor-only user's claude-side rates silently defaulted to 0 and
  // corrupted the "low accept rate" coaching rationale before this fix.
  const safeDiv = (a, b) => (b > 0 ? a / b : null);
  const usedClaude = u.sources.has('claude');
  const usedCursor = u.sources.has('cursor');
  return {
    ...u,
    // Consistency / adoption depth — active days as a fraction of the window,
    // not just a raw count, so a 90-day window and a 7-day window are comparable.
    // null (not 0) when the person never used that tool at all.
    claude_consistency: usedClaude ? safeDiv(u.active_days, periodDays) : null,
    cursor_consistency: usedCursor ? safeDiv(Math.max(u.tab_active_days, u.agent_active_days), periodDays) : null,
    // Output-per-engagement — is a session/day producing something, or just exploratory?
    commits_per_session: usedClaude ? safeDiv(u.commits, u.cc_sessions) : null,
    prs_per_session: usedClaude ? safeDiv(u.prs, u.cc_sessions) : null,
    loc_net: usedClaude ? u.loc_added - u.loc_removed : null,
    loc_per_session: usedClaude ? safeDiv(u.loc_added + u.loc_removed, u.cc_sessions) : null,
    // Trust in AI output — acceptance rate is the clearest quality/productivity signal
    // available per provider; a low rate with high volume usually means low-quality
    // suggestions, not low usage, and should be coached differently.
    edit_acceptance_rate: usedClaude ? safeDiv(u.edits_accepted, u.edits_accepted + u.edits_rejected) : null,
    tab_accept_rate: usedCursor ? safeDiv(u.tab_accepts, Math.max(u.tab_active_days, 1)) : null,
    agent_accept_rate: usedCursor ? safeDiv(u.agent_accepts, Math.max(u.agent_active_days, 1)) : null,
    // Single sortable score for "Per-Individual (Cross-Tool)" ranking — sums
    // whichever consistency values are non-null so a Both user isn't unfairly
    // capped at one tool's scale, and a single-tool user still sorts sanely.
    combined_engagement: (usedClaude ? (u.active_days / periodDays) : 0) +
                         (usedCursor ? (Math.max(u.tab_active_days, u.agent_active_days) / periodDays) : 0),
  };
}
```

Render any `null` derived field as `—` in every tier's output — never `0%`
or `0.00`. A `0` is a real measured zero; `null` means the tool wasn't used
and the rate is undefined, and the two must stay visually distinct or
coaching/highlight rows will misattribute a missing metric as poor
performance (this is exactly what the forward-test caught for a Cursor-only
user's Claude-side rates).

**Team-level rollups** (compute once over all `users`, not per user):
- Totals and per-domain subtotals (group by `u.domain`) for every raw counter above.
- Median (not mean — a few power users skew the mean hard) of `commits_per_session`,
  `edit_acceptance_rate`, `claude_consistency` — this is the "typical" team member, useful
  for spotting individuals who are outliers in either direction (coaching candidates on
  the low side, best-practice examples on the high side). **Compute the median over only
  the users for whom that field is non-`null`** (i.e. only over users who actually used
  that tool) — including `null`s as 0 would drag the median down for reasons unrelated to
  performance.
- Per-tool "Consistency: NN% of days active" in section 1 is the median (same non-null
  rule) of `claude_consistency` across Claude users, and of `cursor_consistency` across
  Cursor users — not an average of raw active-day counts, and not computed over users who
  never touched that tool.
- Trend: re-run `aggregate()` on the prior period of equal length (day 91–180 back) and
  diff each rollup — "team edit_acceptance_rate: 62% (+5pp vs prior 90d)" is the shape of
  insight that answers "is productivity improving," which raw totals alone can't. If no
  prior-period data is available (e.g. team is newer than the window, or this is a
  one-off ad hoc period), print `Trend vs prior period : not available (insufficient history)`
  rather than omitting the line or fabricating a delta.

---

## T1 — Quick Snapshot

**Default period when the user doesn't specify one: trailing 90 days.** This
gives enough history to judge sustained productivity and retention, not just
a activity blip. Cursor's per-request cap is 30 days, not a hard ceiling on
coverage — stitch three 30-day slices per the Provider Registry note above.
Anthropic just means fetching/caching 90 daily files instead of one. Only use
a shorter window (e.g. "today", "trailing 7 days") if the user explicitly
asks for it — mention in the output which window was used either way.

Raw activity counts alone answer "how much" — always pair them with the
derived rates so the snapshot answers "how productive" and "how consistent"
too. Report the output as **three explicit, separately-labeled sections** —
per the user's requirement that per-tool, per-individual, and team views be
easy to tell apart, not blended into one flat table:

1. **Per-Tool Usage** — Claude and Cursor reported as fully separate blocks
   (different metrics, different units — don't force them into one row).
2. **Per-Individual (Cross-Tool)** — one row per person combining both tools,
   so "how is this specific person doing across everything" has one place to
   look.
3. **Team Insights** — rollups, medians, trends, and coaching candidates —
   never mixed into the per-tool or per-individual sections above.

```
╔══ T1: <PERIOD (default: trailing 90d)> COMBINED AI USAGE ═══════════════

── 1. PER-TOOL USAGE ─────────────────────────────────────────────────────
  Claude
    Unique active users : N        Conversations    : N
    CC Sessions         : N        Commits / PRs    : N / N
    LOC +/- (net)       : N / N (N)
    Commits per session : N.NN     Consistency      : NN% of days active
    Edit acceptance rate: NN%
  Cursor
    Unique active users : N        Tab accepts      : N
    Agent accepts       : N        Agent lines      : N
    Tab active days     : N        Agent active days: N
    Consistency         : NN% of days active

── 2. PER-INDIVIDUAL (CROSS-TOOL) ────────────────────────────────────────
  Unique active users   : N  (Claude: N | Cursor: N | Both: N)
  <email>  tools: claude+cursor | commits/session N.NN | edit-accept NN%
                  | tab accepts N | agent lines N | cursor rec: <label>
  <email>  tools: claude only   | commits/session N.NN | edit-accept NN%
  ... (one row per active user; sort descending by `combined_engagement` —
       this is the single cross-tool score defined in `deriveMetrics`, not
       an ad hoc ranking. Render any `null` field as `—`, never `0%`.)

── 3. TEAM INSIGHTS ───────────────────────────────────────────────────────
  Median commits/session : N.NN    Median edit-accept rate: NN%
  Trend vs prior period  : commits/session ±N%, edit-accept rate ±Npp (or
                            "not available (insufficient history)")
  Top by productivity    : <email> (commits/session N.NN, accept rate NN%)
  Coaching candidates    : <email> (cursor rec: coach_cursor_first — driven
                            by tab/agent volume + active-day thresholds in
                            `cursorRecommendation`, NOT by accept rate; if
                            accept rate is also notably low, state it as a
                            separate additional signal, don't imply the
                            recommendation function used it)
  Per-domain subtotals    : <domain>: N users, N commits, NN% median accept
╚══════════════════════════════════════════════════════════════════════
```

Per-user rows (when the ask is about an individual, not just the team) should
report the same derived fields — `commits_per_session`, `loc_net`,
`edit_acceptance_rate`, `claude_consistency`/`cursor_consistency` — rather
than raw counters alone, so "is this person productive" has an actual answer
instead of just "this person is active."

---

## T2 — Deep Analysis Hypotheses

Standard hypotheses for the combined dataset:

| H# | Question | Key metric |
|---|---|---|
| H1 | Are high-session users productive or exploratory? | `commits_per_session`, `loc_per_session` vs raw `cc_sessions` — high sessions + low commits/session = exploratory, not productive |
| H2 | Which domain drives which tool? | cc_sessions + conversations vs tab/agent accepts by domain |
| H3 | Is adoption growing or declining, per tool? | daily avg comparison across periods, per provider; team-rollup trend diff |
| H4 | Retention — who came back period-over-period, per tool? | set intersection of email lists per provider |
| H5 | Tool preference — who's Cursor-only, Claude-only, or both? | presence in each provider's userMap (`claudeOnly`/`cursorOnly`/`both`) |
| H6 | LOC/edit outliers across tools | `loc_net` (Claude) + `agent_accepts` (Cursor) top-10 |
| H7 | Is AI output actually trusted, or just generated and discarded? | `edit_acceptance_rate` / `tab_accept_rate` low + high volume = low-quality-suggestion pattern, not adoption problem — coach differently than H1 exploratory users |
| H8 | Who is consistently engaged vs a one-off spike? | `claude_consistency` / `cursor_consistency` — low active-day ratio despite high totals means a few big days, not sustained use |
| H9 | Who are coaching candidates vs approve-for-Claude candidates? | `cursorRecommendation(u)` per user — `coach_cursor_first`/`defer_other_tools` surfaces low-signal Cursor usage before recommending a Claude seat |

Always end T2 with a confirmed/refuted verdict per hypothesis.

---

## T3 — Visual Report (Combined Dashboard)

**Output:** `/tmp/ai_usage_report.html` — dark-themed Chart.js dashboard,
single page covering both providers.

**Standard charts:**
1. **Daily trend** (bar + line overlay): CC Sessions + Cursor Tab/Agent activity over time
2. **Top 10 users** (horizontal bar): CC Sessions + Commits vs Tab/Agent accepts, side-by-side
3. **Domain breakdown** (grouped bar): per-tool activity per domain
4. **Tool overlap** (Venn or stacked bar): Claude-only / Cursor-only / Both
5. **KPI cards** (grid): key totals at a glance, grouped by tool

After writing: `open /tmp/ai_usage_report.html`

---

## T4 — Monitoring

For daily adoption tracking, schedule a remote agent via `/schedule`:

```
Every weekday at 9am: fetch yesterday's Anthropic data + latest Cursor 30d
window, append to caches, run T1 combined snapshot, post summary to
[Slack channel / Teams webhook].
```

---

## Related Skills

- `data-analyst` — the T1–T4 base framework this skill implements
- `quarantine-analyst` — same tier pattern for SQL Server quarantine data
- `team-ai-usage` (project, not a skill) — Cursor license-gate checks; this
  skill's Cursor provider mirrors its API details but is for combined
  dashboards, not license-gate decisions
