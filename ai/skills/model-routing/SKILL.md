---
name: model-routing
description: Model/effort/fast-mode selection across Claude Code, Codex, and Cursor — when to use Sonnet vs Opus vs Haiku vs Fable 5, the Codex Sol/Terra/Luna/5.4-mini tiers, the opusplan default, advisor auto-escalation and its known limitations, effort levels (thinking depth), fast mode, subagent model routing in .claude/agents/*.md frontmatter, and plan mode. Mirrors .cursor/rules/model-routing.mdc for the Cursor equivalent. Invoke before a manual /model or /effort switch, before authoring a subagent's model: frontmatter field, before choosing a Codex subagent tier, or when deciding whether a task warrants Fable-tier escalation.
triggers:
  - which model should I use
  - model routing
  - effort level
  - fast mode
  - fable
  - advisor tool
  - subagent model
  - codex model tier
  - sol terra luna
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
`.claude/agents/*.md` (accepts `opus`, `sonnet`, `haiku`, `fable`, or `inherit` —
aliases only, never a dated model ID; `.claude/hooks/config-integrity.sh` hard-fails
the tree on any other value). Unset means "inherit the orchestrator's current model" —
this is correct for agents whose complexity varies with the task (e.g. `cicd-monitor`,
`cicd-review`).

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

## Enforcement

This policy is prose guidance, not automatically self-enforcing. Each clause below maps
to whatever actually holds it in place today — several clauses have no hook and rely on
this document plus habit.

| Policy clause | Mechanism | Enforcement level |
|----------------|-----------|--------------------|
| Main-loop model tier (Sonnet/Opus/Fable via `/model`, `opusplan`) | None — **advisory-only, structurally.** Claude Code exposes no hook that can call `/model` or otherwise switch the main session's model; hooks only see/gate tool calls, they cannot mutate session-level model state. There is no mechanism to add here — this is a permanent platform boundary, not a gap to close. | None (by design of the platform) |
| `.claude/settings.json` default (`model: "opusplan"`) tracked correctly | Human/agent discipline + `plans/decisions.md` ADL-020 recording the fix; `settings-symlink-guard.sh` can silently copy a drifted runtime value back into the tracked file (see ADL-020's "Why") | None — drift-prone, no hook currently blocks a bad value from landing in the tracked file |
| Subagent `model:` frontmatter is a supported alias (`haiku`/`sonnet`/`opus`/`fable`/`inherit`, no dated IDs) | `.claude/hooks/config-integrity.sh`'s `check_agent_models()` | **Hard-enforced** — `exit 1` on violation (ADL-021) |
| Workflow fan-out stays ≤ 3 concurrent agents | `.claude/hooks/pre-tool-gate-v2.sh` Section 8 (`Workflow` matcher, regex-counts `agent(` call sites, flags undecidable `.map()`/variable fan-out) | **Warn-only** (ADL-022) — regex cannot reliably parse arbitrary JS array sizes, so a hard count would be unreliable; promotion to deny is an explicit future decision, not part of this policy |
| Agent tier matches task difficulty (no Haiku on deep-reasoning work, no frontier tier on trivial work) | `.claude/hooks/pre-tool-gate-v2.sh` Section 7b (`Agent` matcher, keyword/length heuristic against an explicit `model:` override only) | **Warn-only** (ADL-022) — keyword matching is a heuristic, not a difficulty classifier; only fires on explicit overrides since the hook cannot see a resolved "inherit" tier |
| Subagent delegation contains context (fork vs fresh choice) | None — prose rule in `ai/rules/agent-user-global.md` § Agent Spawning | None |
| Effort level / fast mode match task type | None — prose rule + `primitive-hint.sh` (advisory suggestion, not a gate) | None |
| Advisor auto-escalation fires before declaring a task done | None — `Stop` hooks only support `decision: "block"`, not `additionalContext`, so this trigger cannot be hook-injected; see "Known limitation" above | None |

### Codex rows

Same hard/warn/unenforceable split, applied to `.codex/hooks/pre-agent-gate.sh` (PreToolUse,
matching the subagent tool). All checks **fail open** — a malformed payload, missing `jq`, or a
Codex version whose subagent payload shape differs must never strand a session.

| Policy clause | Mechanism | Enforcement level |
|---|---|---|
| Coordinator tier is `gpt-5.6-sol` | `config.toml` `model =` | **Pinned**, but manual — same structural gap as the Claude row above; no hook can switch a main-loop model |
| Subagent `model` is a supported slug | `pre-agent-gate.sh` check 1 — fixed enum of 6 slugs | **Hard deny** (`exit 2`) — deterministic, mirrors `check_agent_models()` |
| Frozen spec exists before spawn | `pre-agent-gate.sh` check 2 — `[[ -f ]]` on a `plans/specs/*.md` path named in the prompt | **Hard deny** (`exit 2`) when referenced-but-missing; **warn** when no spec is referenced at all (the hook cannot judge whether the work warranted one) |
| Worker tier is explicit, not inherited | `pre-agent-gate.sh` check 1 else-branch | **Warn** — inheriting silently routes mechanical work to the most expensive tier |
| Fan-out stays ≤3 concurrent | `pre-agent-gate.sh` check 3 — rolling 60s spawn window | **Warn only** — PreToolUse sees spawns, never completions, so "concurrent" is a proxy, not a count. Promotion to deny would need completion signal that does not exist. Same reasoning as ADL-022. |
| Tier matches task difficulty | None | None — the Claude-side §7b keyword heuristic was not ported; it is a heuristic, not a classifier, and Codex has no equivalent evidence base yet |
| Return contract ≤30 lines | None | None — no hook observes a subagent's return payload |
| Context-admission table (§1 of `codex-delegation.md`) | `pre-bash-guard.sh` → `context_gate.py` covers huge/generated reads only | Partial — cumulative-cost cases below the size threshold are unenforced prose |

Two deployment caveats, both real:

- `.dotfiles/.codex/hooks.json` is **project-scoped** — it applies when Codex runs with this repo as
  cwd. For machine-wide coverage the same `PreToolUse` entry must also exist in `~/.codex/hooks.json`.
- Codex records a `trusted_hash` per hook entry in `config.toml` under `[hooks.state]`. Editing a
  hook script or its wiring **invalidates that hash**, and Codex will re-prompt for trust on the next
  session. Expect one approval prompt after this lands.

**Why main-loop tier selection can't be closed:** every other row either has a concrete
hook today or a documented reason promotion to `deny` hasn't happened yet. Main-loop model
selection is different in kind — there is no `PreToolUse`/`PostToolUse`/`Stop` hook surface
that intercepts or rewrites which model the orchestrator itself runs on. Hooks gate tool
calls; they cannot reach into session/model state. Any future Claude Code version that
exposes such a surface would change this row; until then, treat it as permanently
advisory and rely on the `opusplan` default plus manual `/model` switches.

## Codex equivalent

Codex CLI runs its own model family and its own tier table. The **Coordinator is pinned in
`~/.codex/config.toml`** (`model = "gpt-5.6-sol"`), which is the Codex analogue of ADR 0014's fixed
Opus coordinator — deliberate, not drift. Worker tiers are chosen per spawn via the subagent call's
`model` argument; `features.multi_agent = true` is required.

| Tier | Slug | Effort | Use for |
|---|---|---|---|
| Coordinator | `gpt-5.6-sol` | `medium`; `high`/`xhigh` for architecture | Planning, spec authoring, review, synthesis, final answer. Always the main thread. |
| Escalation | `gpt-5.6-sol` | `xhigh`/`max` | Worker stalled twice, or genuinely hard debugging/design. After evidence, never first. |
| Standard worker | `gpt-5.6-terra` | `medium` | Multi-file implementation, non-trivial debugging, refactors needing judgement. |
| Cheap worker | `gpt-5.6-luna` | `low`/`medium` | Mechanical edits, boilerplate, test scaffolding, doc updates, broad searches, log triage, running builds. **Default worker tier.** |
| Cheapest | `gpt-5.4-mini` | `low` | Pure extraction: grep-and-summarize, existence checks, single-file trivial edits. |
| Second opinion | `gpt-5.5` | `medium` | Independent review of Sol's own output. |

Codex effort levels extend past Claude's: `low, medium, high, xhigh, max, ultra` (`gpt-5.6-luna`
tops out at `max`). Sol's shipped default is `low`.

**Selection rule** — cheapest tier satisfying both: the failure mode is machine-detectable (test,
compiler, exact string), and the task needs no judgement absent from the spec. Otherwise step up
exactly one tier. Escalation ladder and delegation triggers: `ai/rules/codex-delegation.md`.

Refresh this table from `~/.codex/models_cache.json` when OpenAI ships a tier; the slug enum in
`.codex/hooks/pre-agent-gate.sh` must be updated in the same commit or valid spawns will be denied.

## Cursor equivalent

`.cursor/rules/model-routing.mdc` documents the same tiers for Cursor, which has no
`opusplan`-style auto-routing or native advisor tool: model choice there is manual (UI)
or via an explicit `Task` subagent `model` argument, and auto-escalation is
self-triggered (the agent decides to spawn a `Task` at three moments — before an
ambiguous/high-stakes commitment, after 3 identical hook-tracked failures, before
declaring a hard/ambiguous task done) rather than server-side. Keep all three tier
tables — Claude, Codex, Cursor — in sync when any one changes.
