---
name: stack-pr
description: Creates a Pull Request in Azure DevOps or GitHub for the current or specified branch. Automatically detects the forge (GitHub vs Azure DevOps) from the git remote. Handles stacked dependencies automatically. USE THIS SKILL when user says "create PR", "create pull request", "open PR", "submit PR", "create a PR for", or wants to create/open a pull request.
triggers:
  - create PR
  - create pull request
  - open PR
  - submit PR
  - make a PR
  - PR for this
  - create a PR for
  - submit for review
  - open pull request
  - push and create PR
  - ready for review
  - send for review
---

# Stack PR

Creates a Pull Request in Azure DevOps or GitHub, automatically detecting the forge from the git remote URL and correctly handling stacked dependencies.

## When to Use

Use this skill when the user wants to:
- Create a PR for their current work
- Submit a feature for review
- Create a draft PR
- Stack a PR on top of another PR

## Instructions

1. Identify parameters:
   - `branch`: Source branch (default: current)
   - `target`: Target branch (default: inferred from Charcoal stack or `main`)
   - `title`: PR title (optional — auto-generated from branch name if omitted)
   - `draft`: Whether to create as draft (optional)

2. **PR title policy (required)**:
   - Titles must be Conventional Commits format:
     `type(optional-scope): summary`
   - Allowed types: `feat|fix|perf|refactor|test|ci|chore|docs|style|revert`
   - If title is omitted, the stack script now generates a deterministic conventional title from the branch name.
   - If title is explicitly provided and invalid, creation is blocked.

3. **Account detection** — determine which GH account to use:
   ```bash
   REMOTE_ORG=$(git remote get-url origin | sed 's|.*github\.com[/:]||;s|/.*||')
   ACTIVE=$(gh api user --jq '.login' 2>/dev/null)
   TARGET_ACCOUNT=$( [ "$REMOTE_ORG" = "arjaygg" ] && echo "arjaygg" || echo "Arjay-Gallentes_axosEnt" )
   [ "$ACTIVE" != "$TARGET_ACCOUNT" ] && gh auth switch --user "$TARGET_ACCOUNT" > /dev/null 2>&1 || true
   ```

4. **Preflight** — ensure credential helper is registered:
   ```bash
   gh auth setup-git
   ```

5. **Push and create PR** by delegating to the stack script (handles account switching, target detection, body generation, and PR title validation):
   ```bash
   BRANCH=$(git branch --show-current)
   $HOME/.dotfiles/.claude/scripts/stack pr "$BRANCH" "" "<title>"
   ```
   For draft: append `--draft`. The script auto-detects the Charcoal parent as target (falls back to main).

6. Return the PR URL to the user.

7. **Auto-start PR lifecycle monitoring:** After the PR is created successfully, invoke `/ci-pr-lifecycle` to start unified CI + review monitoring. This monitors checks, validates review state, and gates merge readiness automatically.

## Examples

User: "Create a PR for this feature"
```bash
gh auth setup-git
git push -u origin $(git branch --show-current)
gh pr create --base main --fill
```

User: "Submit this as a draft"
```bash
gh pr create --base main --fill --draft
```

User: "Create a stacked PR for feature/login-ui on top of feature/api"
```bash
$HOME/.dotfiles/.claude/scripts/stack pr feature/login-ui feature/api
```

User: "Create PRs for all my branches" / "Publish the stack" / "Open all PRs"
```bash
$HOME/.dotfiles/.claude/scripts/stack pr-all
# or for drafts:
$HOME/.dotfiles/.claude/scripts/stack pr-all --draft
```
This creates PRs bottom-up for every branch in the stack that doesn't already have an open PR, correctly targeting each branch's Charcoal parent.
