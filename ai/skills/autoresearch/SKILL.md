---
name: autoresearch
description: >
  Axos adapter for the autoresearch plugin (uditgoenka/autoresearch v1.8.2).
  Adds worktree isolation, GitHub Enterprise integration, agent roles (QA/Dev/Architect/TL),
  plan-driven orchestration, bounded defaults (10 iterations), sensitive-file deny-list,
  and domain templates on top of the upstream autonomous loop. Use this skill whenever
  the user wants to iteratively improve something with a measurable metric — test coverage,
  build time, failing tests, security findings, latency, prompt eval pass rates. Invoke
  proactively when the user says "fix all failing tests", "optimize until X", "run overnight",
  "keep improving", "make all tests pass", "reduce build time", "increase coverage",
  "run experiments", "autoresearch", or whenever a bounded modify→verify→keep/discard loop
  would help. Also triggers for multi-agent plan execution, stacked worktree orchestration,
  and role-based development workflows (QA writes tests, Dev implements, TL gates).
version: adapter-1.0.0
upstream: uditgoenka/autoresearch@1.8.2
---

# Autoresearch — Axos Adapter

Wraps the upstream [autoresearch plugin](https://github.com/uditgoenka/autoresearch) with
safety, isolation, and workflow layers. The core loop logic lives in the plugin's reference
files — this adapter adds what the plugin lacks.

**What the plugin provides**: 9-step autonomous loop, crash recovery, guard system, bounded
iteration, results logging, 9 subcommands.

**What this adapter adds**: Worktree isolation, GitHub integration, agent roles, plan context
injection, bounded defaults, sensitive-file deny-list, domain templates, orchestration support.

---

## Subcommands

| Subcommand | Purpose | Load |
|---|---|---|
| `/autoresearch` | Autonomous metric optimization | `references/autonomous-loop-protocol.md` |
| `/autoresearch:plan` | Goal → verified config wizard | `references/plan-workflow.md` |
| `/autoresearch:fix` | Drive failing count to zero | `references/fix-workflow.md` |
| `/autoresearch:debug` | Scientific bug-hunting loop | `references/debug-workflow.md` |
| `/autoresearch:security` | STRIDE + OWASP audit | `references/security-workflow.md` |
| `/autoresearch:ship` | Universal shipping workflow | `references/ship-workflow.md` |
| `/autoresearch:scenario` | Edge case discovery | `references/scenario-workflow.md` |
| `/autoresearch:predict` | Multi-persona swarm analysis | `references/predict-workflow.md` |
| `/autoresearch:learn` | Documentation generation | `references/learn-workflow.md` |

For every invocation, also load `references/core-principles.md` and `references/results-logging.md`.

---

## Enhanced Setup Fields

These fields extend the plugin's standard setup gate. The plugin collects Goal, Scope, Metric,
Direction, Verify, Guard, and Iterations. This adapter adds:

| Field | Default | Description |
|---|---|---|
| `Base` | main | Branch to create worktree from. Supports stacked branches (e.g., `feat/phase-0-baseline`). |
| `Role` | — | Agent role: QA, Dev, Architect, TL. Injects role-specific scope and metric constraints. |
| `PlanContext` | — | Structured plan excerpt (test names, file paths, acceptance criteria) that constrains hypotheses. |
| `Worktree` | true | Run in `.trees/<goal-slug>/`. Set `false` to use current branch. |
| `Template` | auto | Domain template name, or `auto` for keyword detection from Goal. |

If the user omits `Iterations`, inject `Iterations: 10`. Unbounded loops require explicit
`Iterations: unlimited` — this prevents accidental multi-hour token burn.

---

## Safety Overlay

These rules apply to ALL modes, ALL subcommands, without exception.

### Sensitive File Deny-List

Refuse any hypothesis that touches these patterns — check BEFORE making tool calls:

`.env`, `*.secret`, `*credential*`, `*password*`, `*.pem`, `*.key`, `*.pfx`, `*.p12`,
`appsettings.Production.*`, `appsettings.Staging.*`

The `pre-tool-gate.sh` hook enforces this at the tool level as defense-in-depth, but the
skill should catch these earlier to avoid wasted iterations.

### Scope Contract

- Only modify files matching the declared `Scope` pattern.
- If a hypothesis requires out-of-scope files, surface this to the user — never expand silently.
- Never modify Verify or Guard commands/scripts. The eval harness is the trust anchor; if it
  changes, iterations become incomparable.

### Commit Before Verify

Always commit changes before running verification. This is what makes `git reset --hard HEAD~1`
a clean undo. Without the commit, a failed verify leaves dirty state.

---

## Pre-Loop Wrapper

Execute these steps BEFORE delegating to the plugin's autonomous loop:

### 1. Worktree Isolation

If `Worktree: true` (default):

```bash
$HOME/.dotfiles/.claude/scripts/stack create feat/autoresearch-<goal-slug> <Base>
```

- `<goal-slug>` = kebab-case of the Goal (max 5 words, lowercase, hyphens)
- `<Base>` = the Base field (defaults to `main`, supports any branch for stacking)
- All subsequent loop iterations happen inside `.trees/<goal-slug>/`
- On `Ctrl+C` interrupt: the worktree is safe to inspect, resume, or remove

### 2. Template Loading

If `Template` is specified or `auto` matches Goal keywords (see lookup table below),
load pre-filled field values from `templates/<name>.md`. Show the pre-filled config to
the user and let them override any field before proceeding.

### 3. Baseline Validation

Run the Verify command once to establish the baseline metric. If it fails (non-zero exit
or unparseable output), stop and help the user fix the command before starting the loop.

### 4. Results File

Create `autoresearch-results.tsv` in the worktree root:

```
# metric_direction: <higher_is_better|lower_is_better>
iteration	status	metric_before	metric_after	delta	description	commit_sha	timestamp
0	baseline	—	<baseline_value>	—	initial measurement	<sha>	<ISO8601>
```

---

## Agent Role System

When `Role:` is specified, these constraints layer on top of the standard loop behavior.
Roles encode the Red-Green-Refactor discipline from test-first development.

### QA (Red Phase)

Write failing tests. The goal is test existence and compilation, not passing.

- **Scope**: Test files only. Never modify source code.
- **Metric**: Test count (compiling test signatures) or coverage %.
- **Verify**: Test compilation check (tests exist, even if they fail).
- **PlanContext**: Specific test names and signatures to implement.
- **Behavior**: Each iteration adds one test. The test SHOULD fail (it tests unimplemented behavior).

### Dev (Green Phase)

Make failing tests pass. The goal is zero failures.

- **Scope**: Source code only. Never modify test files.
- **Metric**: Failing test count. Direction: lower. Target: 0.
- **Verify**: Test runner counting failures.
- **Guard**: Build compiles successfully.
- **PlanContext**: Which specific tests must pass.
- **Behavior**: Each iteration fixes one failing test. Stop when all pass.

### Architect

Structural analysis, fitness functions, documentation.

- **Typical subcommands**: `/autoresearch:learn`, `/autoresearch:security`, `/autoresearch:predict`
- **Scope**: Broad (whole module or package). Read-heavy, write-light.
- **PlanContext**: Architectural constraints, dependency rules, fitness function definitions.

### TL — Tech Lead (Quality Gate)

Mutation testing, coverage thresholds, quality verification.

- **Verify**: Quality gate script output (mutation kill rate %, coverage %).
- **Guard**: All existing tests pass.
- **Behavior**: Runs after Dev phase. Validates that tests are meaningful, not just passing.

---

## Plan Context Injection

When `PlanContext:` is provided, it constrains the hypothesis space in Step 2 (Ideate)
of the autonomous loop. The agent implements what the plan specifies rather than freestyling.

**How it works**:
- The plan context is injected as read-only reference material during ideation
- Each iteration should implement the next unfinished item from the plan
- The agent tracks which plan items are done via the results TSV
- Never modify the plan itself

**Format** — structured markdown:
```markdown
PlanContext:
  - TestRun_PrioritizesChunksOverNewProcessLogs (worker.go:128-140)
  - TestRun_AtCapacity_ReturnsEarlyWithNoWork (worker.go:168-172)
  - TestRun_StartsAndStopsHeartbeat (worker.go:185-194)
```

Each item becomes one iteration's hypothesis. This turns a plan into a mechanical execution.

---

## Core Loop Delegation

After the pre-loop wrapper completes, delegate to the plugin's reference files.
The adapter does NOT reimplement the loop — it wraps it.

Load the appropriate reference file based on the subcommand:

- `/autoresearch` → Read `references/autonomous-loop-protocol.md`, follow its 8-phase protocol
- `/autoresearch:<cmd>` → Read `references/<cmd>-workflow.md`, follow its protocol

**pctx/Serena integration** — In Step 1 (READ STATE), batch scope understanding:

```typescript
// Via mcp__pctx__execute_typescript — ONE call, not sequential
const [scopeFiles, overview] = await Promise.all([
  Serena.searchForPattern({ substring_pattern: ".", relative_path: "<scope-dir>" }),
  Serena.getSymbolsOverview({ relative_path: "<scope-dir>" }),
]);
return { scopeFiles, overview };
```

**Context window management** — For loops beyond 5 iterations, avoid dumping full verify
output into context. Summarize results, or route verbose output through context-mode sandbox.
Query results.tsv with grep, not full file reads.

---

## Post-Loop Wrapper

After the loop ends (iterations exhausted, goal met, or user interrupt):

### 1. Results Summary

Print a summary table from `autoresearch-results.tsv`:
- Total: X kept, Y discarded, Z crashes
- Net improvement: `<baseline>` → `<final>` (`<direction>`)
- Best iteration: #N with delta of `<value>`

### 2. GitHub Integration

Detect forge from `git remote get-url origin`. If GitHub:

- **Existing PR**: Offer to post results as a PR comment:
  ```bash
  gh pr comment <PR_ID> --body "## Autoresearch Results\n<summary>"
  ```
- **New PR from worktree**: Offer to create via `gh pr create` or `/stack-pr`
- **Never auto-execute** — always show the command and wait for user approval

### 3. Worktree Guidance

- Remind: all kept changes are committed in `.trees/<goal-slug>/`
- Offer: create PR, merge to parent branch, or continue iterating with more iterations

### 4. Phase Completion Signal

For orchestrated multi-agent scenarios, output:
```
[PHASE_COMPLETE] goal=<goal> metric_start=<baseline> metric_end=<final> status=<success|partial|failed> worktree=<path>
```

This allows a coordinator to parse completion and trigger the next phase.

---

## Orchestration Support

For multi-agent lean dev plan execution (stacked worktrees, parallel subagents, agent roles):

- Each autoresearch invocation is one phase/task — the coordinator manages sequencing
- Results go to worktree-local `autoresearch-results.tsv` (no shared state between worktrees)
- Multiple instances can run concurrently in different worktrees without conflict
- The coordinator creates stacked worktrees via `/stack-create`, then invokes autoresearch
  in each with the appropriate `Role:`, `Base:`, and `PlanContext:`
- Phase dependencies are enforced by the coordinator, not by this skill

**Example — Coordinator creates a stacked PR pipeline**:
```bash
# Phase 0: baseline tests (targets main)
/stack-create feat/phase-0-baseline main
# Phase 1: fitness functions (stacked on Phase 0)
/stack-create feat/phase-1-fitness feat/phase-0-baseline
# Phase 2 stories as individual stack entries
/stack-create feat/story-1.3-shutdown feat/phase-1-fitness
```

Then for each worktree, invoke autoresearch with the matching Role and PlanContext.

---

## Domain Template Lookup

When `Template:` is set, or `auto` matches Goal keywords, load from `templates/`:

| Template | Trigger Keywords | File |
|---|---|---|
| coverage | "test coverage", "increase coverage" | `templates/coverage.md` |
| test-fix | "fix tests", "make tests pass" | `templates/test-fix.md` |
| security-audit | "security audit", "vulnerability" | `templates/security-audit.md` |
| performance | "latency", "throughput", "performance" | `templates/performance.md` |
| build-optimization | "build time", "compilation" | `templates/build-optimization.md` |
| lean-dev-phase | "phase", "plan execution", "lean dev" | `templates/lean-dev-phase.md` |
| mutation-gate | "mutation testing", "quality gate" | `templates/mutation-gate.md` |

On match: load the template, show pre-filled values, let user confirm or override.
On no match: proceed with standard interactive setup from the plugin.
