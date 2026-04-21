---
name: stack-pr-all
description: Creates GitHub PRs for all unpublished branches in the Charcoal stack bottom-up, skipping branches that already have open PRs. USE THIS SKILL when user says "create PRs for all branches", "publish the stack", "open all PRs", "PR the whole stack", or wants to submit all stacked branches at once.
triggers:
  - create PRs for all branches
  - publish the stack
  - open all PRs
  - PR the whole stack
  - submit all branches
  - create all PRs
  - PR all my branches
  - publish all branches
  - open PRs for stack
---

# Stack PR All

Creates GitHub PRs for every unpublished branch in the Charcoal stack, processing bottom-up so each PR correctly targets its parent.

## When to Use

- After building out a stack of branches and wanting to open all PRs at once
- To publish a full stack for review in one command
- When some PRs already exist and you want to fill in the gaps

## Instructions

1. Run the pr-all script:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack pr-all
   ```

   For draft PRs:
   ```bash
   $HOME/.dotfiles/.claude/scripts/stack pr-all --draft
   ```

   The script will:
   - Walk the Charcoal stack bottom-up (leaf → trunk)
   - Skip trunk and branches with existing open PRs
   - Create a PR for each unpublished branch, targeting its Charcoal parent
   - Generate deterministic Conventional Commit PR titles from branch names when not provided
   - Print a summary with PR URLs

2. Return the summary output to the user, including any created PR URLs.

## Examples

User: "Create PRs for all my branches" / "Publish the stack"
```bash
$HOME/.dotfiles/.claude/scripts/stack pr-all
```

User: "Open all PRs as drafts"
```bash
$HOME/.dotfiles/.claude/scripts/stack pr-all --draft
```

## Related Skills

- **stack-pr**: Create a PR for a single branch
- **stack-clean**: Remove a merged branch and its worktree
- **stack-merge**: Merge a PR and rebase dependents
