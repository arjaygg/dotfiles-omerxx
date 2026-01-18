---
name: stack-doctor
description: Checks PR stack health and finds issues. USE THIS SKILL when user says "check stack", "stack health", "diagnose stack", "fix stack", "stack doctor", "stack issues", or wants to verify stack integrity or fix problems.
triggers:
  - check stack
  - stack health
  - diagnose stack
  - fix stack
  - stack doctor
  - stack issues
  - verify stack
  - stack integrity
  - troubleshoot stack
  - what's wrong with stack
  - stack problems
  - repair stack
---

# Stack Doctor

Diagnoses and reports on PR stack health, finding issues like orphan branches, sync problems, and metadata mismatches.

## When to Use

**TRIGGER IMMEDIATELY** when the user's request contains any of these patterns:
- "check [my] stack"
- "stack health" or "stack doctor"
- "diagnose [my] stack"
- "what's wrong with [my] stack"
- "fix [my] stack" or "repair stack"
- "stack issues" or "stack problems"
- "verify stack [integrity]"
- Any mention of stack troubleshooting or diagnostics

Use this skill when the user wants to:
- Check if their PR stack is healthy
- Find issues with branches, worktrees, or metadata
- Diagnose sync problems between Charcoal and native metadata
- Identify orphan worktrees or missing branches
- Check if PRs are targeting the correct base branches
- Verify branches are pushed to remote

## Instructions

1. Run the doctor command:
   ```bash
   .claude/scripts/stack doctor
   ```

2. This will check:
   - ✓ Charcoal branch references (branches tracked but don't exist)
   - ✓ Native metadata consistency
   - ✓ PR target alignment with Charcoal parents
   - ✓ Orphan worktrees (worktree exists but branch deleted)
   - ✓ Branch sync status (behind parent, potential conflicts)
   - ✓ Remote branches (not pushed)
   - ✓ Metadata synchronization between systems
   - ✓ PR freshness (local differs from remote)

3. Interpret results:
   - **Errors** (✗): Critical issues that need fixing
   - **Warnings** (⚠): Non-critical issues that may cause problems
   - Suggested fixes are provided for each issue

4. Report to user:
   - Summary of issues found
   - Recommended actions
   - If user wants to fix, provide the suggested commands

## Output Example

```
╔════════════════════════════════════════════════════════════╗
║                    STACK DOCTOR                            ║
╚════════════════════════════════════════════════════════════╝

Running stack integrity checks...

  Checking Charcoal branch references... done
  Checking native metadata consistency... done
  Checking PR target alignment... done
  Checking for orphan worktrees... done
  Checking branch sync status... done
  Checking remote branches... done
  Checking metadata synchronization... done
  Checking PR freshness... done

════════════════════════════════════════════════════════════

Errors (1):
  ✗ Branch 'feature/old' tracked in Charcoal but doesn't exist in git

Warnings (2):
  ⚠ Branch 'feature/api' is 3 commit(s) behind parent 'main' - may have merge conflicts
  ⚠ Branch 'feature/ui' exists locally but not pushed to origin

Suggested fixes:
  gt branch untrack feature/old
  git checkout feature/api && git rebase main
  git push -u origin feature/ui

Summary: 1 error(s), 2 warning(s)
```

## Examples

User: "Check my stack health"
Action: `.claude/scripts/stack doctor`
Result: Shows all checks and any issues found

User: "What's wrong with my stack?"
Action: `.claude/scripts/stack doctor`
Result: Diagnoses issues and provides fixes

User: "My stack seems broken, can you help?"
Action: `.claude/scripts/stack doctor`
Result: Run diagnostics, report findings, suggest fixes

## Related Skills

- **stack-status**: View stack hierarchy
- **stack-update**: Update/restack branches
- **stack-navigate**: Move between branches
