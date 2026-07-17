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

## Pull Request Title Policy

- PR titles MUST use Conventional Commits format: `type(optional-scope): summary`
- Allowed types: `feat`, `fix`, `perf`, `refactor`, `test`, `ci`, `chore`, `docs`, `style`, `revert`
- When creating PRs, prefer stack tooling (`~/.dotfiles/.claude/scripts/stack pr` / `stack pr-all`) so validation is deterministic.

## File And Tool Discipline

- Prefer dedicated tools over shell fallbacks when the client provides them.
- Keep edits minimal and targeted.
- Do not duplicate the same policy across multiple agent-specific instruction files unless a tool requires a loader stub.

## Dotfiles Repositories

When working in a dotfiles repository:

- Distinguish between shared project guidance and tool-specific installation files.
- Treat files under `.claude/`, `.gemini/`, `.codex/`, and similar directories as configuration distribution artifacts unless the file is clearly a project guidance entrypoint.
- Preserve symlink-based setup expectations.

## AI Agent Primitives Configuration

This machine uses a unified AI configuration strategy: common primitives (skills `ai/skills/`, commands `ai/commands/`, styles `ai/output-styles/`, rules `ai/rules/`) are managed centrally in `~/.dotfiles/ai/` and symlinked to each agent's configuration directory (Claude Code, Gemini CLI, Codex, Cursor, Windsurf). Make changes only in `~/.dotfiles/ai/` — they reflect automatically across all tools.

## Git Worktree Conventions

Worktrees live at `.trees/<description>/` with branch names `<type>/<description>` (`feature/`, `bugfix/`, `hotfix/`, `release/`, `chore/`). Full branch-type inference, naming/sanitization rules, the config-copy list, and the create/remove procedures live in the **`stack-create` skill** (`ai/skills/stack-create/SKILL.md`) — invoke it for "create a worktree/branch" requests rather than hand-rolling `git worktree add`.

A branch request ALWAYS means creating/switching the actual git branch — a worktree name or directory is never a substitute for branch creation. If ambiguous, create both per the skill's conventions rather than debating naming with the user.

## Plan Documents

When working from a dated plan file (`plans/YYYY-MM-DD-<context>.md`):

1. Add `plan: plans/YYYY-MM-DD-<context>.md` to `plans/active-context.md` at session start.
2. Add `step: N of M` and `focus: <current step title>` to `plans/active-context.md`.
3. Each `## Step N` in the plan must declare `**Files:**` and `**Accepts:**` fields.
4. Use `TodoWrite` to convert plan steps to an ordered checklist for your own single-agent execution before executing. `TaskCreate` is a separate mechanism for multi-agent coordination (see "Task Tracking Discipline (Multi-Agent)" below), not a substitute for this checklist.
5. Check off `progress.md` checkboxes when each `TodoWrite` item is completed.
6. Do not begin Step N+1 until Step N's `**Accepts:**` criteria are met.

**Structured step format:**
```markdown
## Step N — <title>
**Files:** `path/to/file.ts`
**Accepts:** <done criteria — human-readable completion signal>
- [ ] checkbox item
```

**active-context.md pointer fields:**
```markdown
plan: plans/2026-03-30-my-feature.md
step: 2 of 5
focus: write migration
```

Hooks resolve the active plan at runtime via `grep "^plan:" plans/active-context.md`. This grep-based lookup is the only mechanism for cross-session plan continuity — there is no `@plans/active-context.md` include in any `CLAUDE.md` in the chain.

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

When spawning subagents for multi-step work:
1. Create the task list first: `TaskCreate` with all subtasks
2. Export `CLAUDE_CODE_TASK_LIST_ID=<id>` in each subagent's environment
3. Each subagent uses `TaskUpdate` (not a new `TaskCreate`) to report progress
4. The orchestrator polls `TaskGet` before aggregating results

Never abandon a `TaskCreate` list — orphaned lists accumulate across sessions. Mark cancelled tasks with status `cancelled`.

## Agent Spawning — Fork vs Fresh

When spawning a subagent for research or codebase exploration, **prefer a fork** (no `subagent_type` in Claude Code; equivalent: pass full context explicitly in other tools) over a fresh isolated agent. Forks inherit the parent session's loaded tool context and constraints; fresh agents start cold and will skip session init, falling back to shell primitives that hooks block.

| Situation | Approach |
|-----------|----------|
| Search / explore / find in codebase | Fork — inherit context |
| Second opinion / independent review | Fresh agent — isolation is the point |
| Specialized tool set (e.g. `bmm-*`) | Fresh agent + include init mandate in prompt |

**When spawning a fresh agent that touches project files:** always include the pctx init mandate in the prompt (call `Serena.initialInstructions()` + `LeanCtx.ctxCall({name: "ctx_intent", arguments: {...}})` before any file access). Without it, the agent will use `ls`/`grep` via shell and trigger hook blocks.

---

## Model, Effort & Thinking Mode

Model/effort/fast-mode selection (Sonnet/Opus/Haiku/Fable tiers, `opusplan` default, advisor auto-escalation, effort levels, fast mode, subagent model routing) is fully documented in the **`model-routing` skill** (`ai/skills/model-routing/SKILL.md`) — mirrors `.cursor/rules/model-routing.mdc` for the Cursor equivalent. Invoke it before a manual `/model`/`/effort` switch, before authoring a `.claude/agents/*.md` frontmatter `model:` field, or when deciding whether a task warrants Fable-tier escalation.

Quick digest: default is `opusplan` (Opus in plan mode, Sonnet in execution); escalate to Fable only for beyond-frontier/stalled work; `/effort low` for mechanical tasks, `/effort max` for architecture/hard-debugging; enter `/plan` mode for multi-file architectural changes.

---

## Background Monitoring and Event Watching

Match the primitive to whether the task is event-driven or time-driven: `Monitor` for "notify me when X happens" (zero token cost while silent); `Bash(run_in_background: true)` for one-shot "run this, tell me when done"; `/loop` or `CronCreate` for recurring work that needs LLM reasoning each tick; `CronCreate` → `RemoteTrigger` for cross-session scheduled watching. Full patterns and recipes: `/monitor-patterns` skill (`ai/skills/monitor-patterns/SKILL.md`) — note this skill is currently disabled via `skillOverrides` in `.claude/settings.json`, so read `ai/skills/monitor-patterns/SKILL.md` directly rather than expecting `/monitor-patterns` to auto-invoke.

---

## Investigation Depth

These rules apply to root-cause analyses, debugging sessions, and any request for a recommendation. They target the most common failure mode: concluding too early without enough evidence.

- **Multi-source before conclusion:** For any RCA or investigation, check at least two independent log/signal sources (e.g., app logs AND K8s events AND DB logs) before concluding. A single source is not enough.
- **Show your work:** Explicitly state what was checked and what was NOT yet checked. Do not declare a root cause without listing both. Format: "Checked: [X, Y]. Not yet checked: [Z]."
- **Lead with the recommendation:** When asked for a recommendation, state the concrete recommendation first, then provide the supporting analysis. Never bury the answer in analysis.
- **Never assume exit 0 = success:** For deployment and migration operations, always verify actual artifacts (indexes created, row counts match, pods healthy, API responding) even when the command exits 0.
- **Diagnose vs fix:** When the request is diagnosis/investigation, deliver root-cause analysis ONLY and present proposed fixes as options. Do NOT apply any fix until explicitly approved. If unsure which mode the user wants, ask before changing anything.
- **Write findings incrementally:** During long investigations, write findings to a file section-by-section (≤110 lines per write) instead of one large response or one monolithic Write — large single outputs hit token limits, lose transcript detail, and stall background workflow watchdogs.

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

## Unified AI Hub Structure

See "AI Agent Primitives Configuration" above — same `~/.dotfiles/ai/` hub (skills/commands/styles/rules), symlinked into every agent's config directory.
