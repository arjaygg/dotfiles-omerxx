---
name: model-routing
description: Model/effort/fast-mode selection for Claude Code — when to use Sonnet vs Opus vs Haiku vs Fable 5, the opusplan default, advisor auto-escalation and its known limitations, effort levels (thinking depth), fast mode, subagent model routing in .claude/agents/*.md frontmatter, and plan mode. Mirrors .cursor/rules/model-routing.mdc for the Cursor equivalent. Invoke before a manual /model or /effort switch, before authoring a subagent's model: frontmatter field, or when deciding whether a task warrants Fable-tier escalation.
triggers:
  - which model should I use
  - model routing
  - effort level
  - fast mode
  - fable
  - advisor tool
  - subagent model
---

# Model, Effort & Thinking Mode

Use the right Claude Code primitives for each task. These are configured via `/model`, `/effort`,
and `/fast` commands and apply for the remainder of the session.

## Default configuration

The recommended default is `model: "opusplan"` in `settings.json`. This automatically uses:
- **Opus** (currently Opus 4.8) when in plan mode (complex reasoning, architecture exploration)
- **Sonnet** (currently Sonnet 5) during execution (code generation, file edits, tool use)

No manual `/model` switching needed for the plan→execute flow.

## Model selection

| Signal | Model | Command |
|--------|-------|---------|
| Trivial lookup, quick Q&A, classify | Haiku | `/model haiku` |
| Standard coding (default) | Sonnet | (default via opusplan) |
| Complex reasoning, architecture, hard bugs | Opus | `/model opus` or use plan mode |
| Beyond-frontier: multi-day/long-horizon agentic work, or Opus already stalled on the problem | Fable 5 | `/model fable` |

**Fable 5 is an escalation, not a default.** It's Anthropic's Mythos-class tier — above
Opus, priced well above it, and built for days-long asynchronous work. Reserve `/model
fable` for tasks that genuinely need it; don't leave it selected as your daily driver
(it persists across sessions once chosen, so switch back explicitly when done).

**No `fableplan` hybrid exists.** `opusplan` (Opus in plan mode → Sonnet in execution) is
the only built-in hybrid alias. To get Fable-level planning with cheaper execution, do it
manually: `/model fable` → plan → accept → `/model opus` (or `sonnet`) before execution.

**`best` alias**: resolves to Fable 5 where your account has access, otherwise the latest
Opus. Useful as a settings-file default in orgs with mixed Fable access.

## Auto-escalation via the advisor tool

The advisor tool is the one **real auto-escalation** mechanism: the main model decides,
mid-task, that it's stuck and consults a stronger model for guidance before continuing —
no manual `/model` switch, no fixed phase boundary. It's still experimental (Anthropic
may change behavior/pricing) and requires Claude Code v2.1.170+ for the Fable pairing.

- **Configured here**: `advisorModel: "fable"` in `settings.json` — Sonnet/Opus (the main
  model) auto-consults Fable 5 when it needs a stronger opinion.
- **When it fires**: model-driven, not rule-based. Typically before committing to an
  approach, when an error keeps recurring, or before declaring a task done.
- **Cost**: only the advisor's short reply (~400-700 tokens) is billed at the advisor's
  rate — not the whole task. Cheap even with Fable as the advisor.
- **Steer it**: say so directly in a prompt, e.g. `consult the advisor before you
  continue` or `don't consult the advisor for this`. There's no setting to cap/force calls.
- **Disable**: `/advisor off` for the session, or `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` to
  turn it off entirely.

This is distinct from `opusplan` (fixed plan/execution boundary) and subagent delegation
(explicit, for the whole subtask).

**Known limitation:** the native advisor is known to go silent on long transcripts —
above roughly 100K tokens it can return `advisor_tool_result_error`/`unavailable` with
no fallback firing (see GitHub issues #66784, #66742, #66714, #67609). Do not assume
it will catch a stuck task once a session has run long. `~/.dotfiles/.claude/hooks/
advisor-escalate.py`/`.sh` (a `PostToolUse` hook, ported from the Cursor equivalent)
is a backstop: it tracks recurring identical tool failures and, once a signature
recurs 3+ times, injects a nudge telling the agent to manually spawn a
`model: "fable"` (or `opus`) subagent for a second opinion instead of waiting on the
native advisor. It cannot cover the "before declaring a task complete" trigger —
`Stop` hooks only support `decision: "block"`, not `additionalContext` — so that
trigger remains a prose-rule responsibility in each project's `AGENTS.md`.

## Effort levels (also controls thinking depth)

Effort is the dial for extended thinking — not a separate toggle. Higher effort = more thinking tokens.

| Task type | Effort | Command |
|-----------|--------|---------|
| Mechanical: rename, format, boilerplate | low | `/effort low` |
| Standard coding (default) | high | `/effort high` |
| Architecture, root cause, hard debugging | max | `/effort max` |

- **`/effort low`** — suppresses thinking; fastest output, lowest cost
- **`/effort high`** — adaptive thinking; Claude decides when to reason deeply (default)
- **`/effort max`** — maximum thinking budget; explores edge cases, no cap

## Fast mode

Fast mode uses the same model at 2.5x speed at 6x cost. Quality is identical.

- **Enable** (`/fast on`): rapid iteration loops, live debugging, back-and-forth micro-sessions
- **Disable** (`/fast off`): background/autonomous tasks, bulk operations, one-shot requests

Combining `/fast on` + `/effort low` = maximum throughput for trivial tasks.
Combining `/fast on` + `/effort high` = best interactive experience for standard work.

## Subagent model routing

Subagents declare their own model via the `model:` frontmatter field in
`.claude/agents/*.md` (accepts `opus`, `sonnet`, `haiku`, `inherit`, or an explicit
model ID). Unset means "inherit the orchestrator's current model" — this is correct
for agents whose complexity varies with the task (e.g. `cicd-monitor`, `cicd-review`).

Set an explicit override only when the agent's job is consistently at one end of the
complexity spectrum:

| Signal | Model | Example agents |
|--------|-------|-----------------|
| Deep reasoning, security/correctness stakes, subtle bugs | `opus` | `security-reviewer`, `database-reviewer`, `silent-failure-hunter` |
| Variable complexity, default is fine | unset (`inherit`) | `cicd-monitor`, `cicd-review`, `cicd-audit` |
| Mechanical, narrow, well-defined diagnostic loop | `haiku` | `go-build-resolver`, `cicd-auto-retry` |

Applies when authoring or editing any `.claude/agents/*.md` file. Re-evaluate the tier
if an agent's responsibility changes materially.

## Plan mode

Enter plan mode (`/plan`) for:
- Multi-file architectural changes
- Any task requiring `**Accepts:**` criteria before execution
- Decisions where you want human review before any files are touched

With `opusplan` set, plan mode automatically upgrades to Opus for the planning phase.

## Cursor equivalent

`.cursor/rules/model-routing.mdc` documents the same tiers for Cursor, which has no
`opusplan`-style auto-routing or native advisor tool: model choice there is manual (UI)
or via an explicit `Task` subagent `model` argument, and auto-escalation is
self-triggered (the agent decides to spawn a `Task` at three moments — before an
ambiguous/high-stakes commitment, after 3 identical hook-tracked failures, before
declaring a hard/ambiguous task done) rather than server-side. Keep the two files'
tier tables in sync when either changes.
