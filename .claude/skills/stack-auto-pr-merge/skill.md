---
name: stack-auto-pr-merge
description: Fully automated stack branch creation, PR, approval, and merge with optional stack update
---

# Stack Auto PR Merge

Fully automates the entire stack workflow: create branch → make changes → create PR → approve → merge → update dependent branches.

**This skill ALWAYS runs in the background** - you continue working immediately and get notified when done (~3-5 min).

## When to Use

Use this skill when you want to:
- Make quick changes without leaving your current work
- Handle multiple independent changes in parallel
- Automate repetitive PR workflows
- Skip interactive approval steps (pre-authorized changes only)

**IMPORTANT**: Only use this for changes you're confident about. All pre-commit hooks still run, but there's no manual review before merge.

## Instructions

### Primary Workflow (ALWAYS Use This)

1. **Parse the user's request** to identify:
   - `base-branch`: Branch to base on (e.g., "main")
   - `branch-name`: New branch name (following conventions: feat/*, fix/*, chore/*, docs/*)
   - `changes-description`: What changes to make (human-readable and detailed)
   - `current-branch`: Optional - branch to update after merge (detect from git status if user says "update my branch")

2. **Immediately launch background Task**:

```python
Task(
    subagent_type="general-purpose",
    run_in_background=True,
    description="Auto-merge {branch_name} to {base_branch}",
    prompt=f"""Execute the stack auto-merge workflow:

## Your Task
Create a PR with these changes and auto-merge it to {base_branch}:
{changes_description}

## Workflow Steps

1. Create isolated worktree:
   cd $(git rev-parse --show-toplevel)
   ~/.dotfiles/.claude/scripts/stack create {branch_name} {base_branch} --worktree

2. Change to worktree directory:
   cd .trees/{branch_name_without_prefix}/

3. Make the changes described above using Edit/Write tools

4. Commit changes:
   git add .
   git commit -m "{commit_message}"

5. Push to remote:
   git push origin {branch_name}

6. Create PR using stack pr command:
   ~/.dotfiles/.claude/scripts/stack pr

7. Auto-approve the PR:
   az repos pr set-vote --id <pr-id> --vote approve --organization "https://dev.azure.com/bofaz"

8. Complete the merge:
   az repos pr update --id <pr-id> --status completed --organization "https://dev.azure.com/bofaz"

9. Return to original directory and update current branch (if requested):
   cd $(git rev-parse --show-toplevel)
   git checkout {current_branch}
   git pull origin {base_branch}

10. Clean up worktree:
    git worktree remove .trees/{branch_name_without_prefix}/

## Expected Outcome
- PR created and merged to {base_branch}
- Current branch updated (if requested)
- Worktree cleaned up
- Report PR URL and merge status
"""
)
```

3. **Notify user immediately**:
   - "✅ Started background auto-merge: {branch_name} → {base_branch}"
   - "You'll be notified when the PR is merged (~3-5 min)"
   - "You can continue working - this runs in the background"

## Architecture

This skill uses **isolated worktrees** for complete non-blocking operation:
- ✅ Changes made in separate `.trees/<branch>/` directory
- ✅ Your current workspace never touched
- ✅ Multiple auto-merges can run in parallel
- ✅ Automatic cleanup after merge
- ✅ Uses existing `stack create --worktree` and `stack pr` commands
- ✅ Runs in background via Task tool with `run_in_background=True`

## Safety Features

- ✅ Pre-commit hooks must pass
- ✅ All changes validated before commit
- ✅ PR creation verified
- ✅ Merge completion verified
- ✅ Rollback on failure (branch remains, PR stays open)
- ✅ Non-blocking execution - you continue working immediately

## Examples

### Example 1: Quick Fix
```
User: "Fix the typo in README section 3, auto-merge to main"

Claude: ✅ Started background auto-merge: docs/readme-typo → main
        You'll be notified when the PR is merged (~3-5 min)

You: [Continue working immediately]

[5 min later] Notification: "✅ PR #12345 merged to main"

Result: PR merged, zero interruption to your work
```

### Example 2: Configuration Change
```
User: "Update the plansDirectory setting in .claude/settings.json, auto-merge to main"

Claude: ✅ Started background auto-merge: chore/claude-settings → main

You: [Continue working immediately]

[3 min later] Notification: "✅ PR #12346 merged to main"

Result: Configuration updated, automatic merge
```

### Example 3: Multiple Changes in Parallel
```
User: "I need to make 3 quick fixes:
       1. Update dependencies in package.json
       2. Fix lint errors in utils.go
       3. Update API docs

       Auto-merge them all"

Claude: Launches 3 background Tasks in parallel
  ✅ Started: feat/update-deps → main
  ✅ Started: fix/lint-utils → main
  ✅ Started: docs/api-update → main

You: [Continue working - all 3 run simultaneously]

[5 min later] 3 notifications:
  ✅ PR #12345 merged to main
  ✅ PR #12346 merged to main
  ✅ PR #12347 merged to main

Result: 3 PRs merged in parallel, zero interruption
```

### Example 4: Update Current Branch After Merge
```
User: "Fix the import path in config.go, merge to main, and update my current branch"

Claude: ✅ Started background auto-merge: fix/import-path → main
        Will update performance-baseline after merge

You: [Continue working immediately]

[5 min later] Notification:
  ✅ PR #12348 merged to main
  ✅ performance-baseline updated

Result: PR merged, your branch updated, work preserved
```

## Error Handling

All errors are reported via notification - you're never blocked:

### Pre-commit Hook Failure
```
Notification:
  ❌ Auto-merge failed: pre-commit hooks failed
  - Branch created: fix/my-fix
  - Changes committed (not pushed)
  - Error details: [hook output]
  - Branch preserved for manual fixing
```

### Merge Conflict
```
Notification:
  ❌ Auto-merge failed: merge conflict detected
  - PR created: #12345
  - Conflict details: [files with conflicts]
  - PR remains open for manual resolution
```

### Policy Violation (e.g., requires 2 reviewers)
```
Notification:
  ⚠️ Auto-merge partially completed
  - PR created and approved: #12345
  - Additional reviewers required by policy
  - PR remains open for manual approval
```

## Monitoring Background Tasks

- Check status: `/tasks`
- View output: Use TaskOutput tool with task ID
- All output logged to file for review

## Related Skills

- **stack-create**: Create branch only (no PR)
- **stack-pr**: Create PR only (no auto-merge)
- **stack-update**: Update dependent branches after merge
- **stack-status**: View stack hierarchy

## Workflow Comparison

### Traditional (Manual)
```
1. /stack-create
2. Make changes
3. Commit
4. /stack-pr
5. Approve
6. Merge
7. /stack-update
Time: 10+ minutes, full attention required
```

### With This Skill (Background - Always)
```
1. /stack-auto-pr-merge
Time: 0 perceived time (runs in background while you work)
Actual: 3-5 minutes wall clock time
```
