---
name: azure-devops-cli
description: >
  Azure DevOps CLI (az repos / az devops) command reference for this machine — organization
  flags, PR creation URL format, and the list of ADO projects. Use whenever running az repos
  or az devops commands, or when an ADO command fails with an authentication/repository error.
triggers:
  - az repos
  - az devops
  - azure devops cli
  - ado pr
---

# Azure DevOps CLI Configuration

**IMPORTANT:** When using Azure DevOps CLI commands, you MUST explicitly specify the organization flag even if it's configured in `~/.azure/azuredevops/config`.

## The Problem

The config file stores the default organization but commands like `az repos pr list` do NOT automatically use it and will fail with authentication errors.

## The Solution

Always add `--organization "https://dev.azure.com/bofaz"` to all Azure DevOps commands:

```bash
# WRONG - will fail
az repos pr list --status active --project "Axos-Universal-Core"

# CORRECT - always specify organization
az repos pr list --status active --project "Axos-Universal-Core" --organization "https://dev.azure.com/bofaz"
```

## Quick Reference Commands

```bash
# List projects
az devops project list --organization "https://dev.azure.com/bofaz" --output table

# List active PRs
az repos pr list --status active --project "PROJECT_NAME" --organization "https://dev.azure.com/bofaz" --output json

# Get PR details
az repos pr show --id PR_ID --organization "https://dev.azure.com/bofaz"

# Filter PRs by author
az repos pr list --status active --project "PROJECT_NAME" --organization "https://dev.azure.com/bofaz" --output json | \
  jq -r '.[] | select(.createdBy.displayName | test("AuthorName"; "i")) | "PR #\(.pullRequestId): \(.title)"'
```

## PR Creation Commands

**CRITICAL:** PR creation commands use a DIFFERENT URL format than other commands!

```bash
# Create PR - MUST use visualstudio.com format and --repository parameter
az repos pr create \
  --repository REPO_NAME \
  --source-branch BRANCH_NAME \
  --target-branch TARGET_BRANCH \
  --title "TITLE" \
  --description "DESCRIPTION" \
  --organization "https://bofaz.visualstudio.com" \
  --project "PROJECT_NAME"

# Example for auc-conversion repository
az repos pr create \
  --repository auc-conversion \
  --source-branch feature/my-feature \
  --target-branch main \
  --title "feat(module): add new feature" \
  --description "Description here" \
  --organization "https://bofaz.visualstudio.com" \
  --project "Axos-Universal-Core"
```

**Key Differences for PR Creation:**
1. URL format: `https://bofaz.visualstudio.com` (NOT `https://dev.azure.com/bofaz`)
2. MUST include `--repository` parameter
3. Without these, you'll get "authentication required" or "repository required" errors

## Available Projects

Axos-Universal-Core, Axos Clearing, Axos Core Services, Axos-Crypto-Core, AAS, AAS-Sandbox, AxPay, AxTrader, OCEO Projects, Stock Lending Services, Zenith
