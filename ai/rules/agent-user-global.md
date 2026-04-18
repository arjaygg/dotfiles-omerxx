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

This machine uses a unified AI configuration strategy where common primitives are managed centrally in `~/.dotfiles/ai` and symlinked to each agent's configuration directory.

- **Centralized Source:** `~/.dotfiles/ai/`
- **Linked Agents:** Claude Code, Gemini CLI, Codex, Cursor, Windsurf.
- **Maintenance:** Any changes to rules, skills, commands, or styles should be made in `~/.dotfiles/ai/` and will be automatically reflected across all tools.

## Git Worktree Conventions

Worktrees live at `.trees/<description>/` with branch names `<type>/<description>`.

### Supported branch types
- `feature/` or `feat/`, `bugfix/` or `fix/`, `hotfix/`, `release/`, `chore/`

### Determine branch type from intent
- **feature/feat**: add, implement, create, build, new feature
- **bugfix/fix**: bug, fix, resolve, repair, correct
- **hotfix**: urgent, critical, security, emergency
- **release**: release, version, v1.0, v2.0
- **chore**: docs, cleanup, update dependencies

If unclear, default to `feature/`.

### Branch naming rules
- Use lowercase letters, numbers, and hyphens only (dots allowed for release versions)
- No consecutive, leading, or trailing hyphens or dots
- Use hyphens to separate words (e.g., `feature/add-user-login`)

### When asked to "create a worktree"
1. Sanitize the description (lowercase, spaces→hyphens, strip special chars, collapse hyphens, trim).
2. Ensure `.trees/` exists.
3. Create: `git worktree add -b "<type>/<description>" ".trees/<description>" <base-branch>`
4. Copy essential config files (`.env`, `.vscode/`, `.claude/`, `.serena/`, `.mcp.json`, `.cursor/mcp.json`) — update `--project` paths to point to worktree.
5. Print next steps: `cd .trees/<description>`, `git status`, `git branch --show-current`

### When asked to "remove a worktree"
- Verify clean state first (`git -C <path> status --short`).
- Do NOT remove if uncommitted changes unless explicitly told to proceed.
- Remove with `git worktree remove <path>`, optionally delete branch.

## Plan Documents

When working from a dated plan file (`plans/YYYY-MM-DD-<context>.md`):

1. Add `plan: plans/YYYY-MM-DD-<context>.md` to `plans/active-context.md` at session start.
2. Add `step: N of M` and `focus: <current step title>` to `plans/active-context.md`.
3. Each `## Step N` in the plan must declare `**Files:**` and `**Accepts:**` fields.
4. Use `TodoWrite` to convert plan steps to an ordered task list before executing. Do NOT use `TaskCreate` — that spawns background agents, not a checklist.
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

Hooks resolve the active plan at runtime via `grep "^plan:" plans/active-context.md`. The `@plans/active-context.md` include in CLAUDE.md is evaluated once at session start and provides cross-session continuity only.

## TodoWrite Mandate

For any task requiring **3 or more distinct steps**, you MUST:

1. Create a `TodoWrite` list **before** beginning execution
2. Mark each item `in_progress` when starting it, `completed` when done
3. Do NOT stop until ALL items show `status: completed`

This applies whether or not a formal plan file is active.

**Do NOT use `TaskCreate`** for step tracking — it spawns background agents, not a checklist.

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


---

## Model, Effort & Thinking Mode

Use the right Claude Code primitives for each task. These are configured via `/model`, `/effort`,
and `/fast` commands and apply for the remainder of the session.

### Default configuration

The recommended default is `model: "opusplan"` in `settings.json`. This automatically uses:
- **Opus 4.6** when in plan mode (complex reasoning, architecture exploration)
- **Sonnet 4.6** during execution (code generation, file edits, tool use)

No manual `/model` switching needed for the plan→execute flow.

### Model selection

| Signal | Model | Command |
|--------|-------|---------|
| Trivial lookup, quick Q&A, classify | Haiku | `/model haiku` |
| Standard coding (default) | Sonnet | (default via opusplan) |
| Complex reasoning, architecture, hard bugs | Opus | `/model opus` or use plan mode |

### Effort levels (also controls thinking depth)

Effort is the dial for extended thinking — not a separate toggle. Higher effort = more thinking tokens.

| Task type | Effort | Command |
|-----------|--------|---------|
| Mechanical: rename, format, boilerplate | low | `/effort low` |
| Standard coding (default) | high | `/effort high` |
| Architecture, root cause, hard debugging | max | `/effort max` |

- **`/effort low`** — suppresses thinking; fastest output, lowest cost
- **`/effort high`** — adaptive thinking; Claude decides when to reason deeply (default)
- **`/effort max`** — maximum thinking budget; explores edge cases, no cap

### Fast mode

Fast mode uses the same model at 2.5x speed at 6x cost. Quality is identical.

- **Enable** (`/fast on`): rapid iteration loops, live debugging, back-and-forth micro-sessions
- **Disable** (`/fast off`): background/autonomous tasks, bulk operations, one-shot requests

Combining `/fast on` + `/effort low` = maximum throughput for trivial tasks.
Combining `/fast on` + `/effort high` = best interactive experience for standard work.

### Plan mode

Enter plan mode (`/plan`) for:
- Multi-file architectural changes
- Any task requiring `**Accepts:**` criteria before execution
- Decisions where you want human review before any files are touched

With `opusplan` set, plan mode automatically upgrades to Opus for the planning phase.

---

## Background Monitoring and Event Watching

Use the right primitive based on whether the task is event-driven or time-driven:

| Signal | Primitive | Notes |
|--------|-----------|-------|
| "Tell me when X changes/happens" | `Monitor` | Zero tokens when silent; fires only on stdout events |
| "Run this, notify when done" | `Bash(run_in_background: true)` | One-shot; single completion notification |
| "Do X every N minutes regardless" | `/loop` or `CronCreate` | Full prompt cost per tick — use for LLM-required work |
| "Watch across multiple sessions" | `CronCreate` → `RemoteTrigger` | Scheduled remote agent invocation |

**Use Monitor when:** "notify me when CI fails", "tail logs for errors", "watch pods for crashes"
**Use run_in_background when:** "run these tests and tell me when done"
**Use /loop when:** each tick requires LLM reasoning, not just detecting a state change

Patterns and recipes: `ai/rules/monitor-patterns.md`

---

## Unified AI Hub Structure

All AI primitives are managed in the `ai/` directory:
- **Skills**: `ai/skills/`
- **Commands**: `ai/commands/`
- **Styles**: `ai/output-styles/`
- **Rules**: `ai/rules/`
