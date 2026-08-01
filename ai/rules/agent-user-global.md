# Agent User-Global Defaults

These rules are the user-global baseline for AI coding agents on this machine.

## Scope

- This file is for machine-wide defaults that should apply across repositories.
- Project-specific policy belongs in each repository's `AGENTS.md`, `CLAUDE.md`, or equivalent project docs.
- Tool-specific enforcement belongs in tool settings, hooks, wrappers, and MCP configuration.

## Working Style

- Prefer concise, direct communication.
- Make decisions explicit when tradeoffs matter.
- Prefer concrete verification over assumption when local inspection can answer the question.
- Treat tracked policy documents as higher priority than agent-generated memory.

## Git And Change Safety

- Do not use destructive git commands unless explicitly requested.
- Do not revert unrelated user changes.
- Prefer non-interactive git commands.
- For non-trivial changes, prefer isolated branches and worktrees.

## Autonomy Tiers (A0-A4)

Where a repo opts into the git pipeline, how much a leg may do without asking is an **A0-A4 tier**,
not a boolean. Never read `.claude-atomic.yaml`'s `pipeline:` values directly to decide whether to
act — the declared value is only a ceiling. Resolve the tier actually in force:

```bash
scripts/ai/autonomy-tier.sh --stage auto_ship --json
```

- **A non-zero exit means A0, never "unrestricted."** The resolver fails loudly on a config error
  (legacy boolean, unparseable tier, an irreversible leg declared above its cap) because the hook it
  supports runs under `trap 'exit 0' ERR` — fail-open is right for session availability and wrong
  for authorization.
- **Irreversible legs (`auto_ship`, `auto_clean`) never exceed A2**, whatever evidence accumulates.
  Blast radius caps the tier.
- **Promotion needs a committed green eval run**, not a judgement call. A risk-acceptance override
  is reported separately from evidence and is refused for irreversible legs.
- **Never edit `.claude-atomic.yaml`, `hook-config.yaml`, or `.claude/hooks/*` to raise your own
  tier.** Only a human may. Demotion markers under the shared git dir are written by the gate and
  cleared by a human after committing evidence.

Full ladder, evidence requirements per tier, and the current signed re-acceptance:
`plans/2026-07-27-native-agent-orchestration.md` Part VIII.

## Pull Request Title Policy

PR titles use Conventional Commits (`type(scope): summary`); prefer stack tooling (`stack pr`/`stack pr-all`)
so validation is deterministic. Full allowed-types list and validation flow: **`stack-pr` skill**.

## GitHub Personal Account Billing Gate

- Until the user explicitly says the billing issue is resolved, do not create pull requests for GitHub repositories owned by the personal account `arjaygg`.
- Stop at a local commit/branch by default. While this gate remains active, creating a personal-account PR requires a new explicit override that acknowledges the billing issue.
- GitHub work and enterprise accounts are unaffected.

## File And Tool Discipline

- Prefer dedicated tools over shell fallbacks when the client provides them.
- Keep edits minimal and targeted.
- Do not duplicate the same policy across multiple agent-specific instruction files unless a tool requires a loader stub.

## Git Worktree Conventions

Worktrees live at `.trees/<description>/` with branch names `<type>/<description>` (`feature/`, `bugfix/`, `hotfix/`, `release/`, `chore/`). Full branch-type inference, naming/sanitization rules, the config-copy list, and the create/remove procedures live in the **`stack-create` skill** (`ai/skills/stack-create/SKILL.md`) — invoke it for "create a worktree/branch" requests rather than hand-rolling `git worktree add`.

A branch request ALWAYS means creating/switching the actual git branch — a worktree name or directory is never a substitute for branch creation. If ambiguous, create both per the skill's conventions rather than debating naming with the user.

## Plan Documents

Name plan files `plans/YYYY-MM-DD-<context>.md`. Full naming/format rules, the per-step
`**Files:**`/`**Accepts:**` ritual, and `active-context.md` pointer fields live in the
**`session-artifacts` skill** (`ai/skills/session-artifacts/SKILL.md`) — invoke it when
creating or updating a plan file. Core rule that stays in force everywhere: do not begin
Step N+1 until Step N's `**Accepts:**` criteria are met.

## TodoWrite Mandate

For any task requiring **3 or more distinct steps**, you MUST:

1. Create a `TodoWrite` list **before** beginning execution
2. Mark each item `in_progress` when starting it, `completed` when done
3. Do NOT stop until ALL items show `status: completed`

This applies whether or not a formal plan file is active.

**Use `TodoWrite` for your own step tracking, not `TaskCreate`.** `TaskCreate`/`TaskGet`/`TaskUpdate`/`TaskList` manage a shared task-list entry system for coordinating *multiple* agents (see "Task Tracking Discipline (Multi-Agent)" below) — they do not spawn agents themselves. When you are the only agent working the checklist, `TodoWrite` is the right tool; reach for `TaskCreate` only when the work is being split across subagents that need to share task state.

Heuristics for "3+ step tasks":
- Editing more than one file
- Any request phrased as "do X, then Y" or "X and also Y"
- Any implementation task (feature, fix, refactor, migration)

## Task Tracking Discipline (Multi-Agent)

When spawning subagents for multi-step work, use `TaskCreate`/`TaskUpdate`/`TaskGet` to
share progress across agents (not `TodoWrite`, which is per-agent only). Full protocol —
list creation, `CLAUDE_CODE_TASK_LIST_ID` export, polling, and orphaned-list hygiene — is
in the **`tool-routing` skill** (`ai/skills/tool-routing/SKILL.md`).

## Agent Spawning — Fresh by Default, Fork by Exception

**Fresh is the default, and omitting `subagent_type` already gives you a fresh agent**
(`general-purpose`). Only the literal value `"fork"` forks. A fork inherits the parent's entire
conversation, so it *starts* at the parent's current context size and grows from there — treat that
inheritance as a cost to justify, never as a convenience.

Choose in this order:

1. **`Explore`** — read-only repo research answerable cold. First choice; rule it out before
   authoring anything custom.
2. **Fresh** — `general-purpose` or a named agent type. Everything else. Pack what it needs into the
   prompt; a fresh agent inherits nothing, so context-packing is mandatory, not optional.
3. **Fork** — `subagent_type: "fork"`, only when **all three** hold:
   - the answer depends on state that exists only in this conversation (a decision just made, a tool
     result not yet written to disk, a diff mid-iteration) and is not re-derivable from the repo;
   - restating that state in a prompt would be longer or lossier than inheriting it;
   - the work is one self-contained question — a fork cannot re-delegate.

**Never fork** for: an independent review or second opinion (isolation is the point); work needing a
non-parent model (a fork ignores `model`) or a specialised tool set; work that may spawn its own
workers; or when the parent context is already large.

**Every fresh agent that touches project files must open its prompt with the pctx init mandate** —
`Serena.initialInstructions()` + `LeanCtx.ctxCall({name: "ctx_intent", arguments: {...}})` before any
file access. Without it the agent reaches for `ls`/`grep` and is hard-denied by
`pre-tool-gate-v2.sh`. Normative statement and the reusable `pctxInit()` block:
`plans/2026-07-27-native-agent-orchestration.md` §5.

---

## Model, Effort & Thinking Mode

Model/effort/fast-mode selection (Sonnet/Opus/Haiku/Fable tiers, `opusplan` default, advisor auto-escalation, effort levels, fast mode, subagent model routing) is fully documented in the **`model-routing` skill** (`ai/skills/model-routing/SKILL.md`) — mirrors `.cursor/rules/model-routing.mdc` for the Cursor equivalent. Invoke it before a manual `/model`/`/effort` switch, before authoring a `.claude/agents/*.md` frontmatter `model:` field, or when deciding whether a task warrants Fable-tier escalation.

Quick digest: default `opusplan` (Sonnet for execution, Opus auto-selected in plan mode); escalate to Fable only for beyond-frontier/stalled work; `/effort low`/`max` for mechanical vs. architecture work; `/plan` for multi-file architectural changes. Override the default manually when task signals warrant it.

`primitive-hint.sh` fires on every prompt and suggests the right primitive when the task type
differs from the default — **advisory only**, follow or ignore.

---

## Background Monitoring and Event Watching

Match the primitive to whether the task is event-driven or time-driven: `Monitor` for "notify me when X happens" (zero token cost while silent); `Bash(run_in_background: true)` for one-shot "run this, tell me when done"; `/loop` or `CronCreate` for recurring work that needs LLM reasoning each tick; `CronCreate` → `RemoteTrigger` for cross-session scheduled watching. Full patterns and recipes: `/monitor-patterns` skill (`ai/skills/monitor-patterns/SKILL.md`) — note this skill is currently disabled via `skillOverrides` in `.claude/settings.json`, so read `ai/skills/monitor-patterns/SKILL.md` directly rather than expecting `/monitor-patterns` to auto-invoke.

---

## Investigation Depth

Root-cause analysis and debugging rigor — multi-source verification before concluding, a
show-your-work checklist, diagnose-vs-fix mode separation, and incremental findings writes.
Full rules: **`investigation-depth` skill** (`ai/skills/investigation-depth/SKILL.md`).

## Skill Tool Semantics

The Skill tool only loads instructions into the current context — it does NOT execute
anything and is NOT a background process.

- Never report a skill as "running in the background" after invoking the Skill tool.
- Background work exists only when spawned via `Bash(run_in_background: true)`,
  `Agent`, or `Monitor` — report its real task/agent id as evidence.
- After loading a skill, execute its steps directly and report actual status.

## Communication

When a request uses ambiguous shorthand (e.g. an abbreviation, acronym, or numbered label like "P0" that could mean either a priority tier or a plan phase), ask a single targeted clarifying question before starting implementation. Do not guess and proceed — a wrong guess on scope wastes more turns than one clarifying question.

## Compound Request Echo-Back

For any request containing 2+ distinct actions joined by AND/THEN/ALSO/PLUS, before taking any action:
1. Print a one-line interpretation: "I understand: (1) X, (2) Y, (3) Z"
2. Proceed immediately — do NOT wait for confirmation unless actions are destructive

## Scope Declaration

Before editing >3 files: list the files and why each is in scope. Stop if any are not obviously connected to the request.

## Orchestrator-Worker Paradigm

When executing complex tasks, follow the Orchestrator-Worker paradigm to maximize efficiency and token savings:

- **Role Boundaries:** The main session acts as the Coordinator (highest frontier model), focusing exclusively on architecture, planning, and code review. It delegates hands-on, multi-file code implementation tasks to Executor sub-agents (smaller worker models).
- **Frozen Spec Pattern:** Before spinning up any worker agent, the Coordinator must generate a per-worker frozen specification file at `plans/specs/<label>.md` (template: `plans/specs/TEMPLATE.md`) to provide unambiguous instructions to the Executor. `<label>` matches the worker's branch/task label so concurrent workers never collide on one file. This is the only spec-path convention — do not use a single shared `plans/spec.md`, and do not use `plans/active-context.md` as a spec handoff location.
- **Anti-Nesting Rule:** CRITICAL: Executor sub-agents must perform implementation themselves and are strictly forbidden from spawning nested sub-agents.
