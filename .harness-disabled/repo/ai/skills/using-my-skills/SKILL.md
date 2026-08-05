---
name: using-my-skills
description: >
  Skill router and core operating behaviors. Names which skill owns each phase of a task —
  orient, diagnose, plan, implement, review, ship, operate — what precedes and follows it, and
  where its output lands. Injected once per session; consult it when unsure which skill applies.
triggers:
  - which skill should I use
  - what skill handles this
  - skill router
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
---

<!-- GENERATED FILE — DO NOT EDIT.
     Source: ai/skills/manifest.csv
     Regenerate: python3 scripts/generate_router.py
     Any edit here is overwritten on the next regeneration. -->

# Using My Skills

Routing table generated from `ai/skills/manifest.csv`. Work the phases in order; within a phase, pick the row whose output you actually need.

## Orient — Do I understand the code and have the right tool for the lookup?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `chrome-mcp-efficiency` | — | — | browser automation results | `inline` |
| `explore` | — | `investigation-depth` | codebase map or symbol locations | `inline` |
| `kubectl-efficiency` | — | — | cluster query results | `inline` |
| `lean-ctx` | — | `explore` | compressed file/search results | `inline` |
| `model-routing` | — | — | model and effort selection | `inline` |
| `rtk` | — | — | token-compressed shell output | `inline` |
| `tool-routing` | — | `explore` | tool selection decision | `inline` |
| `using-my-skills` | — | `explore` | phase-to-skill routing decision | `inline` |

## Diagnose — Is something broken, and do I know why?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `investigation-depth` | `explore` | `strange` | root-cause findings | `plans/` |
| `strange` | `investigation-depth` | `cap` | reproduced failure and fix hypothesis | `inline` |

## Plan — Is the intended outcome written down where it survives this session?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `goal-authoring` | — | `session-artifacts` | dated goal document | `goals/` |
| `session-artifacts` | `goal-authoring` | `cap` | active-context / decisions / progress | `plans/` |

## Implement — Am I making the change?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `cap` | `session-artifacts` | `lensed-review` | implemented feature with tests | `inline` |
| `db-admin` | `explore` | `lensed-review` | schema and query analysis | `inline` |
| `hook-authoring` | `explore` | `lensed-review` | hook script and settings wiring | `.claude/hooks/` |

## Review — Has the change been checked by something other than the author?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `ai-usage-analyst` | — | — | adoption and usage dashboard | `inline` |
| `coach` | — | — | usage anti-pattern feedback | `inline` |
| `lensed-review` | `cap` | `hyper-atomic-commits-reference` | findings in the shared finding contract | `inline` |
| `pr-review` | `lensed-review` | `stack-ship` | posted review findings | `PR comment` |

## Ship — Is it committed, reviewed, green, and merged?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `auto-ship` | `hyper-atomic-commits-reference` | `stack-clean` | advanced git lifecycle pipeline | `inline` |
| `ci-monitor` | `stack-pr` | `stack-merge` | streamed CI events and failure class | `inline` |
| `ci-status` | `ci-watch` | `stack-merge` | current CI status | `inline` |
| `ci-watch` | `stack-pr` | `ci-status` | background CI verdict | `plans/ci-status.md` |
| `hyper-atomic-commits-reference` | `lensed-review` | `stack-create` | commit-state guidance | `inline` |
| `stack-auto-pr-merge` | `stack-create` | `stack-update` | branch created reviewed and merged | `PR` |
| `stack-clean` | `stack-update` | — | removed branch and worktree | `inline` |
| `stack-create` | `hyper-atomic-commits-reference` | `stack-pr` | new branch and worktree | `.trees/` |
| `stack-doctor` | `stack-status` | `stack-sync` | stack health report | `inline` |
| `stack-merge` | `ci-status` | `stack-update` | completed merge | `PR` |
| `stack-navigate` | `stack-status` | — | branch switch | `inline` |
| `stack-pr` | `stack-create` | `ci-watch` | opened pull request | `PR` |
| `stack-pr-all` | `stack-create` | `ci-watch` | pull requests for the whole stack | `PR` |
| `stack-ship` | `ci-status` | `stack-update` | merged branch and dependents | `PR` |
| `stack-status` | — | `stack-navigate` | stack hierarchy | `inline` |
| `stack-sync` | `stack-doctor` | `stack-pr` | rebased branch | `inline` |
| `stack-update` | `stack-merge` | `stack-clean` | restacked dependents | `inline` |

## Operate — Does this need to keep running after the session ends?

| Skill | After | Before | Output | Lands in |
|---|---|---|---|---|
| `bg-job` | — | — | detached job handle and logs | `~/.local/state/bg-job/` |
| `routines-setup` | — | — | scheduled cloud routine | `inline` |
| `tmux-orchestrator` | — | — | persistent agent sessions | `inline` |

## Core operating behaviors

These six sit above every individual skill and are **non-negotiable**. They apply whether or not
any skill is invoked.

1. **Surface assumptions.** State them before non-trivial work: "correct me now or I proceed."
2. **Manage confusion actively.** On an inconsistency: stop, name it, present the tradeoff, wait.
   Do not resolve it silently by guessing.
3. **Push back when warranted.** Quantify the downside — "adds ~200 ms latency", not "might be
   slower." Sycophancy is a failure mode, not politeness.
4. **Enforce simplicity.** If you build 1000 lines and 100 would suffice, you have failed.
5. **Maintain scope discipline.** Surgical precision, not unsolicited renovation.
6. **Verify, don't assume.** Evidence, never "seems right." Run the check and show its output.

## Verification

- The phase you routed to answers the question actually asked, not an adjacent one.
- The skill you picked appears in the manifest for that phase — you did not invent a route.
- Any skill named in `preceded-by` either already ran or was deliberately skipped, and you said which.
