---
name: daily-standup-insights
description: Generates team standup reports by running scripts that collect Azure DevOps work items and Git commit data, then correlates them into structured insights. Always use this skill for standup reports, team status updates, team pulse, sprint summaries, or any request about what the team worked on — this skill provides the ADO query and Git scripts required to fetch the data, which Claude cannot access without it. Trigger on casual phrasings too: "what did the team do today?", "any blockers?", "who worked on what?", "give me a team update", "morning standup prep", "show team activity".
---

# Daily Standup Insights

Automates collection and analysis of team activity from Azure DevOps (ADO) and Git, then presents it as a structured standup report.

## Parameters

| Param | Default | Example |
|-------|---------|---------|
| `TEAM_PROJECT` | `Axos-Universal-Core` | `"Axos-Universal-Core"` |
| `AREA_PATH` | `Axos-Universal-Core\AUC Single Account and Sub-Accounting` | `"Axos-Universal-Core\AUC Single Account and Sub-Accounting"` |
| `ORG` | `https://dev.azure.com/bofaz` | `"https://dev.azure.com/bofaz"` |
| `SINCE_DAYS` | `2` | `"2"` |

Config is persisted to `~/.standup_insights.conf` — subsequent runs can omit params.

## Running collection

**From the team's git repo** (full data — ADO work items + local Git log):
```bash
/absolute/path/to/ai/skills/daily-standup-insights/scripts/run_collection.sh "TEAM_PROJECT" "AREA_PATH" "ORG" "SINCE_DAYS"
```
Run this with the team repo as the working directory so `fetch_deltas.sh` can read the local git log.

**From anywhere** (ADO-linked commits/PRs only, no local Git log):
```bash
/absolute/path/to/ai/skills/daily-standup-insights/scripts/fetch_ado_links.sh "TEAM_PROJECT" "AREA_PATH" "ORG" "SINCE_DAYS"
```

`run_collection.sh` always runs `fetch_ado_links.sh` and also runs `fetch_deltas.sh` if the working directory is a git repo. Never skip `fetch_ado_links.sh` — it pulls commit and PR links from ADO work item relations (populated when commits reference `AB#<id>` or are linked in the Boards UI).

Optional: set `MAX_ITEMS=50` (env var) to limit how many work items `fetch_ado_links.sh` checks.

## Workflow

1. **Identify parameters** — confirm Team Project, Area Path, ADO org, and time window with the user (default: last 48 hours / `SINCE_DAYS=2`).

2. **Collect** — run the collection script(s). Prefer running from the team repo working directory for full data.

3. **Synthesize**:
   - **Wins**: work items moved to "Done," "3.4 - QA Approved," or "2.5.1 - Build Complete"
   - **Focus**: items in "In Progress" or "2.2 - In Progress"
   - **Friction**: items in "2.6 - Dev Blocked," or "In Progress" with no linked commits/PRs
   - **Reality Check**: cross-reference ADO IDs found in Git commits (from `fetch_deltas.sh`) or in ADO-linked Git commits (from `fetch_ado_links.sh`). Flag "Ghost Activity" — ADO state changes with no linked commits or PRs.

4. **Report** — use the format below.

## Report Format

### **Team Standup Pulse (ADO + GitHub)**
_Summary for [Current Date]_

#### **1. Completed Recently (The Wins)**
- [ID] [Work Item Type]: [Title] ([Assigned To])

#### **2. Active Focus (The In-Progress)**
- [ID] [Work Item Type]: [Title] ([Assigned To])

#### **3. Friction & Blockers (Talking Points)**
- **Blocked Items**: [ID] [Assigned To] - [Reason/Status]
- **Ghost Activity**: [Observation about mismatch between ADO and Git]
- **Alerts**: [Stale items or unassigned blockers]

#### **4. Goal for Today**
- [Immediate priorities based on ADO priority/state]
