# Lean Dev Plan Phase Template

Pre-filled configuration for executing one phase of a structured lean development plan
using stacked worktrees and agent roles.

## Orchestration Pattern

A lean dev plan decomposes into phases. Each phase maps to:
- A **stacked worktree** (created via `/stack-create`)
- One or more **agent roles** (QA, Dev, Architect, TL)
- **Parallelizable tasks** within the phase (marked ⊕ in the plan)

The coordinator creates all worktrees first, then invokes autoresearch in each.

## Fields (per phase invocation)

```
Goal: {from plan — e.g., "Write 15 unit tests for Worker.Run() achieving ≥75% coverage"}
Scope: {from plan — e.g., "pkg/app/worker/worker_run_test.go"}
Metric: {from plan — e.g., "Test count passing"}
Direction: {from plan — higher or lower}
Verify: {from plan — e.g., "go test ./pkg/app/worker/... -count=1 | grep -c '--- PASS'"}
Guard: {from plan — e.g., "go build ./..."}
Iterations: {from plan — typically 15-20 for test writing, 10 for implementation}
Base: {parent branch in the stack — e.g., "feat/phase-0-baseline"}
Role: {from plan — QA, Dev, Architect, or TL}
PlanContext: |
  {structured excerpt from the plan with specific items for this phase}
  - TestName1 (file.go:line-range)
  - TestName2 (file.go:line-range)
  ...
```

## Coordinator Workflow

### Step 1 — Create stacked worktrees

```bash
# Each phase gets a stacked branch
/stack-create feat/phase-0-baseline main
/stack-create feat/phase-1-fitness feat/phase-0-baseline
/stack-create feat/story-1.3-shutdown feat/phase-1-fitness
# ...continue for each phase/story
```

### Step 2 — Launch parallel subagents per phase

Within each phase, parallelizable tasks (marked ⊕) launch as concurrent subagents
in the same worktree. Each subagent gets:
- Its own Role (QA, Dev, etc.)
- Its own PlanContext (specific items from the plan)
- Shared Scope (same worktree, different files)

### Step 3 — Sequential phase gates

After all parallel tasks in a phase complete, run the gate:
- QA phase → Dev phase → TL quality gate
- Each gate validates the previous phase's output

### Step 4 — PR stack creation

After all phases complete:
```bash
# Create stacked PRs from worktrees
/stack-pr  # in each worktree, creates PR targeting parent branch
```

## Phase Dependency Rules

- A phase cannot start until its dependencies are complete
- The coordinator checks `[PHASE_COMPLETE]` signals from each worktree
- Parallel phases (marked ⊕) can run simultaneously in separate worktrees
- Sequential phases wait for the dependency chain

## Example — 4-Phase Plan

```
Phase 0: QA writes baseline tests (2 parallel subagents)
  → Phase 0 gate: TL runs mutation + coverage check
Phase 1: QA writes fitness + behavioral tests (2 parallel)
  → Phase 1 gate: Architect reviews
Phase 2: Dev implements stories (sequential, internal parallelism)
  → Each story: QA (Red) → Dev (Green) → TL (Gate)
Phase 3 ⊕ Phase 4: Architect docs + Dev integration tests (parallel)
```
