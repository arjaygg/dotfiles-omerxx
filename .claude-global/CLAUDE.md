# Global Claude Code Instructions

## AI Agent Primitives

The rules, skills, commands, and output-styles for Claude Code are managed centrally in `~/.dotfiles/ai/` and granularly symlinked into `~/.claude/`.

- **Rules:** `@ai/rules/agent-user-global.md`, `@ai/rules/tool-priority.md`, `@ai/rules/global-developer-guidelines.md`
- **Source:** `/Users/axos-agallentes/.dotfiles/ai/`

## Azure DevOps CLI Configuration

**IMPORTANT:** When using Azure DevOps CLI commands, you MUST explicitly specify the organization flag even if it's configured in `~/.azure/azuredevops/config`.

### The Problem

The config file stores the default organization but commands like `az repos pr list` do NOT automatically use it and will fail with authentication errors.

### The Solution

Always add `--organization "https://dev.azure.com/bofaz"` to all Azure DevOps commands:

```bash
# WRONG - will fail
az repos pr list --status active --project "Axos-Universal-Core"

# CORRECT - always specify organization
az repos pr list --status active --project "Axos-Universal-Core" --organization "https://dev.azure.com/bofaz"
```

### Quick Reference Commands

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

### PR Creation Commands

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

### Available Projects

Axos-Universal-Core, Axos Clearing, Axos Core Services, Axos-Crypto-Core, AAS, AAS-Sandbox, AxPay, AxTrader, OCEO Projects, Stock Lending Services, Zenith

---

## Remote Conventions

**Always run `git remote -v` before any push or PR creation** to confirm the correct remote.

| Repo | Remote | Tool |
|------|--------|------|
| `auc-conversion` | `github.com/axos-financial/auc-conversion` | `gh` CLI |
| `auc-deployment-manifest` | `github.com/axos-financial/auc-deployment-manifest` | `gh` CLI |
| ADO repos | `dev.azure.com/bofaz/...` | `az repos` CLI |

**Never assume the remote** — check first. The `pre-push-remote-check.sh` hook warns on mismatch but does not block; the right habit is to verify before running the push command.

---

## Working Directory Rules

**CRITICAL:** Never use `cd` commands or assume "canonical" locations.

### The Problem

Using `cd` breaks git worktrees and makes assumptions about project structure. Scripts and commands should work from wherever they're invoked (main repo or worktree).

### The Rules

1. **NEVER use `cd`** unless explicitly requested by the user
2. **Use relative paths** from current working directory (e.g., `./scripts/...`)
3. **Use absolute paths** when referring to specific locations
4. **Don't assume canonical locations** - work with what's provided
5. **Scripts should be location-agnostic** - they work from main repo or worktrees

### Examples

```bash
# ❌ WRONG - using cd
cd /path/to/repo && ./scripts/run-tests.sh

# ✅ CORRECT - use absolute path
/path/to/repo/scripts/run-tests.sh

# ✅ CORRECT - use relative path from current directory
./scripts/run-tests.sh

# ❌ WRONG - assuming location
cd /Users/name/git/project && pytest tests

# ✅ CORRECT - work from current directory
pytest ./tests
```

### Why This Matters

- Git worktrees have separate working directories (e.g., `.trees/feature-branch/`)
- Skills and scripts must work regardless of where they're invoked
- Using `cd` violates the principle of working from current context

---

## Plan File Naming Convention

All plan files are saved to `plans/` relative to the project root (configured via `plansDirectory` in `~/.claude/settings.json`).

**Naming format:** `YYYY-MM-DD-<context>.md`

Where `<context>` is a short kebab-case summary of the task being planned.

### Rules

1. Use the current date as prefix
2. Keep `<context>` to 3-5 words max, kebab-cased
3. If multiple plans are created on the same day for different tasks, each gets its own descriptive context
4. Create the `plans/` directory if it doesn't exist

### Examples

```
plans/2026-03-02-refactor-auth-flow.md
plans/2026-03-02-add-redis-caching.md
plans/2026-03-05-migrate-to-grpc.md
```

---

## Model Routing

Select the right model + effort + mode for each task. Default is `opusplan` (Sonnet for execution,
Opus auto-selected in plan mode). Override manually when task signals warrant it.

```
Task arrives
  ├── Trivial lookup / quick Q&A?              → /model haiku
  ├── Standard coding (features, fixes)?       → Sonnet + /effort high  (opusplan default)
  ├── Architecture / hard bugs / deep design?  → /effort max  (opusplan auto-selects Opus in plan mode)
  ├── Rapid iteration / live debugging?        → /fast on + /effort high
  ├── Background / bulk / autonomous?          → /fast off  (speed adds no value)
  └── Privacy / offline / cost-sensitive?      → ollama skill
```

**`primitive-hint.sh`** fires on every prompt and suggests the right primitive when your task
type differs from the default. Follow its advice or ignore — advisory only.

See `ai/rules/agent-user-global.md` § "Model, Effort & Thinking Mode" for full reference.

## Session Artifacts

Maintain these files in `plans/` during active work (create if missing):

- **`active-context.md`**: Update whenever focus shifts, a significant discovery is made, or direction changes. Keep it ≤30 lines. This is read at compaction — keep it current.
- **`decisions.md`**: Append an entry when making an architectural choice or finding a root cause. Use the ADL format:
  ```
  ## YYYY-MM-DD — <Decision title>
  **Decision:** <what was chosen>
  **Why:** <reasoning>
  **Alternatives rejected:** <and why>
  **Assumptions:** <what must hold for this to be correct>
  ```
- **`progress.md`**: Update task state using checkbox format as work progresses.
  ```
  ## In Progress
  - [ ] task being worked on

  ## Done
  - [x] completed task

  ## Blocked
  - [ ] blocked task (reason)
  ```

These are ephemeral per-session artifacts, not permanent documentation. Archive or delete them when starting a new unrelated task.

## CI Monitoring

Never poll CI synchronously. Use `/ci-watch` to spawn background monitoring:

- **Poll at most once per 60 seconds** in interactive mode
- **After 3 consecutive unchanged polls, stop and report status** (no new info to gain)
- **Preferred:** Use `/ci-watch <PR_NUMBER>` — spawns headless agent, returns in <5s, continues main work
- **During active development:** Spawn `/ci-watch` after push, then immediately proceed to next task
- **Zero blocking:** Background monitoring notifies when done/failed; main session stays responsive

This prevents token waste (polling costs ~200 tokens per check) and keeps you productive while CI validates. The skill handles retries and escalation — your job is to implement the next feature.

**Rule:** After pushing a branch, invoke `/ci-watch <PR>` and continue working. Do not enter a polling loop. Do not call `gh run list` in a sleep loop.

---

## PR and Stack Workflow

Use existing skills — do not hand-roll `gh pr merge` sequences:

- **`/stack-ship`** — merge current branch + all dependents atomically with conflict recovery.
- **`/stack-auto-pr-merge`** — background agent: create branch → make changes → PR → approve → merge → cleanup. Runs completely non-blocking in a worktree.
- **`/stack-pr`** / **`/stack-pr-all`** — PR creation only (no merge).
- **`/smart-commit`** — atomic commit with conventional commit message.

**Rule:** When asked to "merge", "ship", or "auto-merge a PR", invoke the appropriate skill above rather than constructing the steps manually. These skills handle remote verification, stale-comment filtering, and branch cleanup.

---

## Kernel File Cache Warning

**Do not edit `CLAUDE.md` or `RTK.md` mid-session** — editing these files invalidates the LLM prompt cache and increases token costs for the remainder of the session.

@RTK.md
