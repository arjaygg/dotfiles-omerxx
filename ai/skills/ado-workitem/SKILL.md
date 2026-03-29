---
name: ado-workitem
description: >
  Create, update, and link Azure DevOps work items (PBIs, Tasks, Bugs) with all required fields
  auto-populated from parent context. USE THIS SKILL when the user mentions creating ADO tickets,
  PBIs, work items, tasks, bugs, or linking PRs to ADO. Also trigger when the user says
  "create a ticket", "make a PBI", "link this to ADO", "add a work item", or mentions
  Azure Boards work items in any context. Works across all ADO projects on dev.azure.com/bofaz.
---

# ADO Work Item Manager

Create Azure DevOps work items with institutional knowledge baked in — the right fields,
the right hierarchy, the right links — so you never hit "field required" errors.

## Why this skill exists

Creating ADO work items via CLI is error-prone: each project has custom required fields,
iteration paths change every sprint, and the relationship between parent/child items has
specific rules. This skill encodes the tribal knowledge so every work item is created
correctly the first time.

## Core workflow

### Step 1 — Gather intent

Ask the user (or infer from conversation context):

1. **What type?** PBI, Task, or Bug
   - PBI for self-contained deliverables or feature slices
   - Task for small sub-units of work under a PBI (requires Activity + Original Estimate)
   - Bug for defects
2. **Title** — concise description of the work
3. **Parent work item** — ID of the parent PBI/Feature/Epic (if any)
4. **Assigned to** — person's display name
5. **Description** — what the work involves (can be inferred from conversation)

If the conversation already contains this context (e.g., the user just completed work and
wants a ticket for it), extract the answers rather than re-asking.

### Step 2 — Resolve parent context

When a parent ID is provided, fetch its fields to inherit iteration and area path:

```bash
az boards work-item show --id <PARENT_ID> \
  --organization "https://dev.azure.com/bofaz" \
  --output json
```

Extract and reuse:
- `System.IterationPath` — current sprint
- `System.AreaPath` — team area
- `Custom.ProjectNumber` — project number (critical for some projects)

This avoids the most common failure: mismatched or missing iteration/area paths.

### Step 3 — Create the work item

**For PBIs:**
```bash
az boards work-item create \
  --type "Product Backlog Item" \
  --title "<title>" \
  --description "<description>" \
  --assigned-to "<display name>" \
  --iteration "<inherited iteration path>" \
  --area "<inherited area path>" \
  --fields "Custom.ProjectNumber=<inherited>" \
  --organization "https://dev.azure.com/bofaz" \
  --project "<project name>" \
  --output json
```

**For Tasks** (additional required fields):
```bash
az boards work-item create \
  --type "Task" \
  --title "<title>" \
  --description "<description>" \
  --assigned-to "<display name>" \
  --iteration "<inherited iteration path>" \
  --area "<inherited area path>" \
  --fields "Microsoft.VSTS.Common.Activity=<activity>" "Custom.ProjectNumber=<inherited>" "Microsoft.VSTS.Scheduling.OriginalEstimate=<hours>" \
  --organization "https://dev.azure.com/bofaz" \
  --project "<project name>" \
  --output json
```

Activity values: Development, Testing, Design, Documentation, Requirements, Deployment

**For Bugs:**
```bash
az boards work-item create \
  --type "Bug" \
  --title "<title>" \
  --description "<repro steps and expected/actual>" \
  --assigned-to "<display name>" \
  --iteration "<inherited iteration path>" \
  --area "<inherited area path>" \
  --fields "Custom.ProjectNumber=<inherited>" "Microsoft.VSTS.TCM.ReproSteps=<steps>" \
  --organization "https://dev.azure.com/bofaz" \
  --project "<project name>" \
  --output json
```

### Step 4 — Link to parent

If a parent ID was provided, create the parent-child relationship:

```bash
az boards work-item relation add \
  --id <NEW_ITEM_ID> \
  --relation-type "parent" \
  --target-id <PARENT_ID> \
  --organization "https://dev.azure.com/bofaz"
```

### Step 5 — Link to PR (if applicable)

If the work item should be linked to a GitHub PR, include `AB#<ITEM_ID>` in the PR
description. The Azure Boards ↔ GitHub integration picks this up automatically.

`AB#` is a fixed prefix (stands for "Azure Boards") — it works for all projects regardless
of project name or code.

### Step 6 — Report back

Show the user:
- Work item ID and URL
- Parent link confirmation
- How to reference in PRs: `AB#<ID>`

Format:
```
ADO Work Item Created:
  Type:     <PBI|Task|Bug>
  ID:       #<ID>
  Title:    <title>
  Parent:   #<parent_id> (if linked)
  Sprint:   <iteration path>
  URL:      https://dev.azure.com/bofaz/<project>/_workitems/edit/<ID>
  PR link:  AB#<ID>
```

## Known projects and their custom fields

| Project | ProjectNumber | Notes |
|---------|--------------|-------|
| Axos-Universal-Core | 920 | AUC conversion, clearing |

When working with a project not in this table, check the parent work item for
`Custom.ProjectNumber` and other custom fields.

## Common pitfalls

1. **Organization URL is always required** — even if `~/.azure/azuredevops/config` has a
   default, `az boards` commands silently fail without `--organization`.

2. **Iteration paths contain backslashes** — escape them in bash:
   `--iteration "Project\\Sprint 7 (03.23.2026 - 04.03.2026)"`

3. **Tasks have more required fields than PBIs** — Activity and OriginalEstimate are
   required for Tasks but not PBIs. When in doubt, create a PBI.

4. **PR creation uses a different URL format** — `az repos pr create` needs
   `https://bofaz.visualstudio.com` (not `dev.azure.com/bofaz`). This skill only handles
   work items, not PR creation.

## Updating work items

To update state (e.g., mark as Active when PR is created):

```bash
az boards work-item update \
  --id <ID> \
  --state "Active" \
  --organization "https://dev.azure.com/bofaz"
```

Common states: New → Active → Resolved → Closed
