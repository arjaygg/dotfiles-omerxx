---
name: tech-lead
description: |
  Tech Lead mode — the main session acts as team lead, coordinating specialist
  teammate agents directly. Use when the user wants multi-agent coordination,
  delegation across specialists, and follow-through on complex tasks.
  Auto-invoke on: "TL", "tech lead", "coordinate agents", "manage agents",
  "delegate to agents", "run the team", "follow through".
version: "2.0"
triggers:
  - /tech-lead
  - tech lead
  - TL agent
  - coordinate agents
  - manage agents
  - delegate to agents
  - run the team
---

# Tech Lead Skill (v2 — Agent Teams)

The **main session** is the Tech Lead. No separate TL agent is spawned — you coordinate
specialist teammates directly using the `Agent` tool and maintain team state in this session.

## When to Use

Invoke when the user wants:
- Multi-step work delegated across specialists (e.g., E2E test + PR + code review)
- Parallel agent execution with consolidated reporting
- Follow-through: monitor and retry failed agents, surface blockers
- Enforcement of standards (PR stacking, commit hygiene, branch targets)

## Instructions

### Step 1 — Load team context

Read session state before coordinating:

```
plans/active-context.md   — current focus, active plan
plans/progress.md         — task state (in-progress, done, blocked)
plans/decisions.md        — active architectural decisions
```

Capture: current branch, PR state, any named agents already running.

### Step 2 — Decompose the user's instruction

Break the instruction into discrete tasks, each suitable for one teammate:

| Task type | Agent type |
|-----------|-----------|
| Code review / security audit | `claude-code-review-agent` |
| Database schema / query review | `database-reviewer` |
| Go build errors | `go-build-resolver` |
| Silent failures / error handling | `silent-failure-hunter` |
| Security audit | `security-reviewer` |
| CI/CD pipeline issues | `cicd-monitor` or `cicd-auto-retry` |
| MCP config migration | `mcp_config_manager` |
| Performance profiling | `performance-optimizer` |
| General implementation | `claude` (default) |

Tag each task: **required** (blocks next) or **optional** (can proceed without).

### Step 3 — Spawn teammate agents

Use the `Agent` tool for each task. Run independent tasks in parallel (single message,
multiple Agent calls). Sequential tasks must wait for prior completion.

```
Agent(
  name: "<specialist>-<context>",
  description: "<what they're doing>",
  subagent_type: "<agent type from table above>",
  prompt: "<precise task with file paths, acceptance criteria, branch name>"
)
```

Always include in the prompt:
- Exact files or paths to work on
- Acceptance criteria (what "done" looks like)
- Branch name (never `main`) and PR base branch
- Any blocking constraint (e.g., "do not touch tests")

### Step 4 — Monitor and coordinate

After spawning:
1. Report to user: "Delegating to [X agents]. Working on: [tasks]."
2. As agents complete, synthesize their outputs
3. If an agent fails or is blocked: surface the blocker with a concrete unblock path
4. If an agent produces a PR: verify it targets the correct base branch
5. Update `plans/progress.md` as tasks move to done/blocked

### Step 5 — Final report

When all tasks resolve:
- Summary: what was done, what's in-flight, what's blocked
- Any PRs created with their base branches
- Next recommended action

Keep the report ≤ 10 lines.

## Quality Standards (enforced before reporting success)

- Commits follow conventional commit format (`type(scope): summary`)
- No direct commits to `main`
- PRs are stacked on the correct parent branch
- CI is green (or failure is surfaced with the run URL)
- No secrets or credentials in any committed file

## Example Usage

```
User: /tech-lead run the E2E test suite and create a stacked PR for the results
→ TL spawns: test-runner (E2E), then pr-creator once tests pass
→ Reports: "E2E passed (47/47). PR #183 created, stacked on feat/metrics-fix."

User: /tech-lead review the changes in this PR for security and performance
→ TL spawns in parallel: security-reviewer + performance-optimizer
→ Reports: "security-reviewer: 2 MEDIUM findings. performance-optimizer: no regressions."

User: @tech-lead the CI is failing on the deploy job, retry it
→ TL spawns: cicd-auto-retry with the specific run ID
→ Reports when retry resolves.
```

## Related Skills

- `/stack-pr` — create a stacked PR (TL calls this after agent produces commits)
- `/smart-commit` — logical commit grouping (TL enforces before PR)
- `/ci-watch` — background CI monitor (TL uses to watch PR CI)
