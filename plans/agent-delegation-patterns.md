# Agent Delegation Patterns — Analysis from Serena Enforcement Session

**Date:** 2026-04-03  
**Session:** Deep analysis of tool priority enforcement; 6 tasks completed

---

## Pattern 1: Exploration Phase (Early Research)

**When to delegate:**
- Codebase is unfamiliar or large
- Multiple search angles needed (symbols, files, patterns)
- Results need synthesis before planning

**How we used it:**
- 2x Explore agents in parallel (Phase 1)
  - Agent A: hooks infrastructure + test patterns
  - Agent B: rules/guides + session initialization mechanisms

**Why delegation worked:**
- Agents can search independently without blocking
- Parallel execution (2 agents) saved 50% wall-clock time
- Agent findings became the plan's "context" section
- Results were read-only (no edits) → low risk

**Pattern rule:**
```
IF unfamiliar codebase + multi-angle search needed
  → Launch 2-3 Explore agents in parallel
  → Consolidate findings into one summary
  → Use for planning, not execution
```

---

## Pattern 2: Design Phase (Architecture)

**When to delegate:**
- Multiple approaches possible (tradeoffs unclear)
- Need expert perspective before committing code
- Task spans multiple systems (hooks + tests + docs)

**How we used it:**
- Skipped Plan agents (task was well-scoped)
- User provided explicit plan requirements in `/plan` command
- Wrote plan directly in plan mode

**Why delegation was skipped:**
- User had already given clear direction ("train Claude to improve")
- Scope was bounded (4 streams, 6 files modified)
- Risk was low (all changes were additive, no breaking changes)

**Pattern rule:**
```
IF requirements are crystal clear + scope is bounded
  → Skip Plan agent; write directly
IF requirements are fuzzy + multiple tradeoffs
  → Launch Plan agent to explore alternatives
```

---

## Pattern 3: Parallel Execution (Independent Work)

**When to delegate:**
- Multiple independent code changes (no dependencies)
- Can run in parallel without conflicts
- Each change is self-contained

**How we used it:**
- All 4 streams executed in parallel (A, B, C, D)
- No blocking dependencies (hook edits don't wait for fixtures; rules don't wait for hook edits)
- Batched all edits in single response

**Why delegation would have worked:**
- Could have launched 4 agents (one per stream) instead of parallel edits
- Would have been ~same wall-clock time (parallel execution)
- Agent approach better if: edits were very complex OR needed validation between steps

**Pattern rule:**
```
IF changes are independent + can run in parallel
  → Either batch edits yourself (simple case)
  → OR launch N agents in parallel (complex case)
Threshold: >3 edits or complex validation → use agents
```

---

## Pattern 4: Background/Async Work (Fire-and-Forget)

**When to delegate:**
- Task is long-running (merge, CI, integration)
- You want to continue working immediately
- Result notification is sufficient

**How we used it:**
- `stack-auto-pr-merge` skill with `run_in_background: true`
- Launched agent, got notification 56s later
- Did NOT block waiting for merge

**Why delegation worked:**
- PR creation + merge takes ~3-5 min
- Blocking would waste 3-5 min of your time
- Agent has all tools needed (gh, git)
- Failure modes are safe (PR stays open, branch preserved)

**Pattern rule:**
```
IF task takes >30 seconds + you don't need result immediately
  → run_in_background: true
Result: perceived time = 0; actual time = 3-5 min wall-clock
```

---

## Pattern 5: Data Processing/Analysis (Sandbox Execution)

**When to delegate:**
- Large data to process (logs, JSON, API responses)
- Transformation happens in Deno sandbox (mcp__pctx__execute_typescript)
- Keep raw output out of context

**How we used it:**
- Explored JSONL session logs (262 tool use entries)
- Agent ran jq, grep, counting logic in sandbox
- Only final summary returned to context

**Why delegation worked:**
- JSONL files were large (~400KB)
- Processing in sandbox avoids flooding context
- Agent can use shell tools (jq, grep, awk) without the hook warnings
- Result was concise (tool counts, blocked patterns)

**Pattern rule:**
```
IF raw output would be >200 lines + transformation is needed
  → Use mcp__pctx__execute_typescript (data processing)
  → Filter/map inside the script
  → Return only final results
```

---

## Pattern 6: Read-Only Exploration (No Risk)

**When to delegate:**
- Task is pure exploration (no writes)
- Safe to parallelize (independent searches)
- Results inform next step

**How we used it:**
- Explore agents found hook configurations, rules, fixtures
- 0 edits during exploration
- Zero risk of conflicts or overwrites

**Why delegation was ideal:**
- Can parallelize without git conflicts
- Agents won't break existing code
- Results are informational (used for planning)
- Easy to retry if search is incomplete

**Pattern rule:**
```
IF read-only + informational
  → Safe to delegate and parallelize
  → Use Explore subagent (has search tools)
Parallelization: 1 agent for narrow search; 2-3 for broad exploration
```

---

## Pattern 7: Implementation (Write/Edit Phase)

**When to delegate:**
- Complex multi-file refactor (10+ files changed)
- Changes have dependencies (B depends on A)
- Need iterative testing

**When NOT to delegate:**
- Edits are simple (<5 files)
- No dependencies between changes
- You're in "flow state" (productive locally)

**How we used it:**
- Did NOT delegate implementation
- Executed all edits locally in plan mode
- Faster than spawning agents + waiting

**Why NOT delegating worked:**
- All edits were straightforward (add guards, add fixtures)
- No cyclic dependencies
- Needed tight feedback loop (edit → test → fix)
- Local execution was faster

**Pattern rule:**
```
IF edits are simple + you can do them faster than agent overhead
  → Edit locally
  → Overhead of agent spawn (~5-10s) + context setup (~10-20s) = 15-30s
  → If work takes <30s, do it yourself

IF edits are complex or require deep context
  → Delegate to agent with full codebase context
  → Agent explores, plans, executes in isolation
  → You continue working
```

---

## Summary Matrix

| Phase | Agent Type | Parallelism | Delegation? | Why |
|-------|-----------|-------------|------------|-----|
| **Exploration** | Explore | 2-3 parallel | ✅ YES | Safe, informational, fast |
| **Planning** | Plan | 1-3 parallel | ❓ OPTIONAL | Skip if requirements are clear |
| **Implementation** | General | Sequential | ❌ NO | Faster to edit locally |
| **Testing/Validation** | General | Parallel | ✅ YES | Independent test runs |
| **Background merge** | General | Parallel | ✅ YES | Long-running, non-blocking |
| **Data processing** | Any + mcp__pctx__execute_typescript | N/A | ✅ YES | Keep sandbox, not context |

---

## Decision Tree

```
START: "Should I delegate this?"
  |
  +-- Is it read-only exploration?
  |    YES → Delegate to Explore agent
  |    NO  ↓
  +-- Does it take >30 seconds AND you don't need result immediately?
  |    YES → Delegate with run_in_background: true
  |    NO  ↓
  +-- Are 3+ independent changes needed in parallel?
  |    YES → Delegate 3 agents OR batch edits yourself (whichever is simpler)
  |    NO  ↓
  +-- Is it a complex multi-file refactor?
  |    YES → Delegate to general-purpose agent
  |    NO  ↓
  +-- Is it data processing or transformation?
  |    YES → Use mcp__pctx__execute_typescript (sandbox, not agent)
  |    NO  ↓
  → Do it yourself (edit locally)
```

---

## Overhead Analysis

| Operation | Setup | Execution | Overhead |
|-----------|-------|-----------|----------|
| Agent spawn | 5-10s | 30s+ | 15% of work |
| Parallel edit | 0s | 10-30s | 0% |
| Background agent | 5-10s | 3-5 min (async) | 0% perceived |
| mcp__pctx__execute | 2-3s | 5-20s | 10% |

**Rule of thumb:** If work takes <30s, do it yourself. If >30s or background, delegate.

