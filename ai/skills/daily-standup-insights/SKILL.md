---
name: daily-standup-insights
description: Analyzes and generates daily standup insights by correlating Azure DevOps work items with Git commit activity. Use when the user requests a team status, standup report, or team pulse.
---

# Daily Standup Insights

Use this skill to automate the collection and analysis of team activity from both Azure DevOps and Git.

## Workflow

1.  **Preparation**: Identify the Team Project, Area Path, ADO Organization, and relevant time window (default 48 hours).
2.  **Collection**: Run the `scripts/fetch_deltas.sh` script with positional parameters:
    *   `TEAM_PROJECT`: e.g., "Axos-Universal-Core"
    *   `AREA_PATH`: e.g., "Axos-Universal-Core\AUC Single Account and Sub-Accounting"
    *   `ORG`: e.g., "https://dev.azure.com/bofaz"
    *   `SINCE_DAYS`: e.g., "2" (optional, defaults to 2 days)
    *   **Usage**: `./scripts/fetch_deltas.sh "Project" "AreaPath" "OrgUrl" "Days"`
    *   **Note**: The script caches your parameters to `~/.standup_insights.conf`. If you run it without parameters next time, it will automatically use your previously saved values.
3.  **Synthesis**:
    *   **The Wins**: Identify work items that moved to "Done," "3.4 - QA Approved," or "2.5.1 - Build Complete."
    *   **The Focus**: List items in "In Progress" or "2.2 - In Progress."
    *   **The Friction**: Highlight items in "2.6 - Dev Blocked" or items stagnant in "In Progress" with no commits.
    *   **Reality Check**: Compare ADO IDs found in Git commits against the active ADO items list. Note any "Ghost Activity" (ADO changes without commits).
4.  **Reporting**: Present the findings in the structured "Standup Pulse" format.

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
