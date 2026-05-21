# claude-auto Pipeline — Setup Guide

Autonomous PR pipeline: label a GitHub issue `claude-auto` → Claude implements it,
runs tests, reviews the code, opens a PR, waits for CI, and admin-merges.

## Architecture

```
Issue labeled 'claude-auto'
  └── arjaygg/.dotfiles/.github/workflows/claude-auto.yml  (reusable)
        └── claude -p <ai/skills/claude-auto/SKILL.md>     (orchestrator)
              ├── Phase 1: Create branch
              ├── Phase 2: Implement + test loop (max 5)
              ├── Phase 3: 3 parallel agents (security, performance, style)
              ├── Phase 4: Diff size self-check
              ├── Phase 5: Commit + push + create PR
              ├── Phase 6: CI watch + bugbot fix
              ├── Phase 7: Admin merge
              ├── Phase 8: Branch cleanup
              └── Phase 9: Issue summary comment + close

  └── arjaygg/.dotfiles/.github/workflows/claude-auto-gates.yml  (required checks)
        ├── claude-auto-coverage-gate   (fails if test coverage drops)
        └── claude-auto-diff-size-gate  (fails if diff > N lines without label)
```

## Prerequisites

### 1. Secrets (required)

| Secret | Where to set | Value |
|--------|-------------|-------|
| `CLAUDE_API_KEY` | Target repo Settings → Secrets → Actions | Anthropic API key |
| `ADMIN_GITHUB_TOKEN` | Target repo Settings → Secrets → Actions | PAT — see below |

**Creating the PAT:**
1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Name: `claude-auto-bot`
3. Repository access: select target repos
4. Permissions:
   - Contents: Read and write
   - Pull requests: Read and write
   - Issues: Read and write
   - Workflows: Read and write
   - Administration: Read (needed for admin merge)
5. Copy token → add as `ADMIN_GITHUB_TOKEN` secret

### 2. Branch protection on `main` (required for gates)

In target repo → Settings → Branches → Add rule for `main`:

- [x] Require status checks to pass before merging
  - Add required check: `claude-auto-coverage-gate`
  - Add required check: `claude-auto-diff-size-gate`
- [x] Require branches to be up to date before merging
- [x] Include administrators — **uncheck this** so admin merge works

### 3. Repository variable (optional)

To override the default 500-line diff limit for a specific repo:

Settings → Variables → Actions → New repository variable:
- Name: `DIFF_SIZE_MAX`
- Value: e.g. `1000`

## Installing in a target repo

Create `.github/workflows/claude-auto.yml` in the target repo:

```yaml
name: claude-auto

on:
  issues:
    types: [labeled]

jobs:
  claude-auto:
    if: github.event.label.name == 'claude-auto'
    uses: arjaygg/.dotfiles/.github/workflows/claude-auto.yml@main
    with:
      issue_number: ${{ github.event.issue.number }}
      # Optional overrides:
      # diff_size_max: 1000
      # max_test_iterations: 3
    secrets:
      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
      ADMIN_GITHUB_TOKEN: ${{ secrets.ADMIN_GITHUB_TOKEN }}
```

Also install the gates workflow — create `.github/workflows/claude-auto-gates.yml`:

```yaml
name: claude-auto-gates

on:
  pull_request:
    branches: [main]

jobs:
  claude-auto-coverage-gate:
    uses: arjaygg/.dotfiles/.github/workflows/claude-auto-gates.yml@main
    # or copy the full gates workflow directly
```

Or copy the full `claude-auto-gates.yml` from dotfiles directly into the target repo.

## Using the pipeline

1. Open (or find) a GitHub issue in a target repo
2. Add the `claude-auto` label
3. Pipeline triggers automatically → watch Actions tab
4. When complete: PR is merged, issue is closed with a summary comment

### Writing good issues for claude-auto

The orchestrator reads your issue title and body verbatim. Better descriptions = better code.

**Template:**

```markdown
## What

<1-2 sentences: what should change>

## Why

<context: why is this needed>

## Acceptance criteria

- [ ] criterion 1
- [ ] criterion 2

## Constraints

- Language: Go / Python / TypeScript / etc.
- Must follow: <pattern/convention>
- Do not: <anti-pattern to avoid>
```

**Minimal example (still works):**
```
Add a health check endpoint at GET /health that returns {"status":"ok"} with HTTP 200.
```

### Overriding gates

**Coverage dropped:**
- Add more tests that cover the new code, OR
- If coverage drop is intentional (e.g. dead code removal): add `large-diff-ok` label
  (this label suppresses the diff gate; coverage gate cannot be bypassed by label)

**Diff too large:**
- Add the `large-diff-ok` label to the issue before triggering (or to the PR before CI re-runs)
- Or narrow the scope of the issue

## Monitoring

- **Active run:** Actions tab → `claude-auto` workflow
- **CI gates:** Actions tab → `claude-auto-gates` workflow  
- **Logs:** full claude session output in the "Run autonomous pipeline" step

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Workflow doesn't trigger | Label name mismatch | Must be exactly `claude-auto` |
| "Resource not accessible by integration" | Wrong token used | Verify `ADMIN_GITHUB_TOKEN` is the PAT, not `GITHUB_TOKEN` |
| Admin merge fails | Branch protection includes admins | Uncheck "Include administrators" in branch protection |
| Coverage gate always fails | No test runner detected | Project needs `go.mod`, `package.json`, `pyproject.toml`, or `Gemfile` |
| Tests timeout | Test suite takes > 6 hours | Reduce scope or set `max_test_iterations: 1` |
| Claude errors with "API key invalid" | Wrong secret | Verify `CLAUDE_API_KEY` is the Anthropic API key |

## Files in this feature

```
.github/workflows/
  claude-auto.yml           ← reusable trigger + orchestration workflow
  claude-auto-gates.yml     ← coverage + diff-size required checks

ai/skills/claude-auto/
  SKILL.md                  ← orchestrator skill (6 phases)

docs/
  claude-auto-pipeline.md   ← this file
```
