# Native Agent Orchestration (Claude Code)

Adapts the Orchestrator-Worker paradigm in `ai/rules/agent-user-global.md` § Orchestrator-Worker
to Claude Code's own primitives, replacing the tmux-driven control loop in
`ai/skills/tmux-orchestrator/SKILL.md` **for Claude-Code workers only**.

Scope: Claude Code exclusively. Every primitive named below is a real Claude Code tool, settings
key, or hook event — verified against the live tool schemas, `docs.claude.com`, and this repo on
2026-07-27 (Claude Code 2.1.220). Non-Claude CLIs (Cursor, Codex, AGY) are out of scope and stay
on tmux — see Step 7.

Renamed from `plans/native_agent_orchestration_plan.md` to the `YYYY-MM-DD-<context>` convention
required by `ai/rules/agent-user-global.md` § Plan Documents.

---

## 0. Delegation gate — when NOT to delegate

Spawning is not free: ~5-10 s spawn + 10-20 s context setup, and a fresh worker re-pays the system
prompt and re-reads the spec in its own context. Fan-out trades **tokens for wall-clock**, not for
tokens.

Delegate only when the subtask is >30 s of Coordinator work **and** at least one of:
- 10+ files touched, or inter-file dependencies the Coordinator would have to hold in context
- an isolated tool set / independent perspective is the point (review, audit, second opinion)
- large tool output (logs, test runs, doc sweeps) that must stay out of the Coordinator's context

Below that threshold the Coordinator edits locally. Source: `plans/agent-delegation-patterns.md:180-240`
("Implementation | General | Sequential | ❌ NO | Faster to edit locally", :217).

Delegation is orthogonal to skill invocation (`plans/skill-delegation-patterns.md:111-141`): a
worker spawned without naming the skill it should load degrades to the "Agent without Skill"
quadrant. Always name the skill in the spec.

## 0b. Relationship to `cap`

`ai/skills/cap/SKILL.md` + `ai/skills/cap/cap-workflow.js` are already a working orchestrator-worker
implementation on the Workflow runtime (Scope → Preflight → Plan → Tests → Implement → Review →
Finalize, with JSON schemas, bounded retries, and resume). This plan is a **generic harness**:
`cap` owns the TDD feature-delivery path; this plan owns generic delegation (research, audit,
migration, multi-file refactor) that is not a TDD cycle. Anything both need — the frozen-spec
format, the tool budget, the acceptance gate — is defined here and `cap` adopts it, so the two do
not diverge. Do not re-implement cap's phase machinery.

---

## 1. Runtime selection — the Coordinator's first decision

Three native mechanisms exist. Pick one per task; do not mix within a phase.

| Runtime | Use when | Primitive |
|---|---|---|
| **`Workflow`** | deterministic, repeatable, multi-phase fan-out; needs schema-validated returns and replay | `Workflow({script, args})` / `Workflow({scriptPath, resumeFromRunId})` |
| **Ad-hoc `Agent`** | one-off, dynamically-shaped, or single-worker delegation | `Agent({subagent_type, prompt, name, model, isolation})` |
| **Agent Teams** | long-lived named teammates the user watches and converses with | `teammateMode` + `SendMessage` (experimental) |

**`Workflow`** is the only deterministic primitive. Inside a script: `agent(prompt, opts)`,
`parallel(thunks)` (barrier), `pipeline(items, ...stages)` (no barrier — the default),
`phase(title)`, `log(msg)`, plus `args` and `budget`. `opts.schema` (a JSON Schema) forces the
worker through a StructuredOutput tool and returns a validated object. Saved scripts live in
`.claude/workflows/` — **this repo has none today**; `cap-workflow.js` is loaded by path instead.
Nesting is one level: `workflow()` inside a child throws.

Concurrency inside a workflow is capped at `min(16, cores - 2)`; lifetime cap is 1000 agents;
`parallel()`/`pipeline()` accept ≤4096 items. Prefer `pipeline()` — a barrier is only correct when
stage N genuinely needs all of stage N-1 (dedup, early-exit on zero, cross-item comparison).

**Repo-specific hard limit:** `.claude/hooks/pre-tool-gate-v2.sh` SECTION 8 regex-counts literal
`agent(` call sites in a submitted Workflow script. **More than 3 literal call sites is a hard
deny** (promoted 2026-07-27, ADL-022 follow-up). A `parallel()`/`pipeline()` over a `.map()` or a
bare variable is statically undecidable and only warns `[fan-out-undecidable]` — in that case the
Coordinator is responsible for bounding the array to ≤3 concurrent workers itself.

## 2. Roles and model tiers

- **Coordinator** — the main session. Architecture, planning, spec authoring, verification. Pinned
  to Opus via `.claude/settings.json:105` `"model": "opus"`; advisor is `fable`
  (`.claude/settings.json:462`).
- **Executor** — subagents doing hands-on multi-file work.

Tier is **declared, not narrated**: set `model:` in `ai/agents/<name>.md` frontmatter.

| Alias | Use for |
|---|---|
| `haiku` | mechanical, narrow, well-defined loops (go-build-resolver, cicd-auto-retry) |
| `sonnet` | standard multi-file implementation and test-writing — the executor default |
| `opus` | correctness/security review, subtle-bug hunts |
| `fable` | escalation only (stalled or beyond-frontier work) |
| `inherit` | complexity varies with the task |

**Aliases only.** `.claude/hooks/config-integrity.sh` `check_agent_models()` exits 1 on any dated
model ID, failing the whole tree (ADL-021). Product names like "Claude 3.5 Sonnet" are not writable
config. Do not set `model: inherit` on a worker while the main session is pinned to `opus` — the
worker silently becomes an Opus worker, defeating the cost split.

## 3. Worker spawn mode — fork vs fresh

Both exist; they are not interchangeable.

- **Fork** — `Agent({subagent_type: "fork", ...})`. Inherits the parent's full conversation and
  loaded tool context. Always runs on the parent's model (`model` is ignored). Runs in the
  background and keeps its tool output out of the parent's context. **A fork cannot re-delegate.**
- **Fresh** — any other `subagent_type`, or none. Starts cold: spawn prompt + project context +
  tools only. No inherited conversation, no session init.

Repo rule (`ai/rules/agent-user-global.md:76-84`): prefer a fork for search/explore/read-heavy work;
use a fresh agent when isolation is the point (independent review) or a specialised tool set is
needed.

**Mandatory for every fresh worker in this repo:** the prompt must open with the pctx init mandate
(`Serena.initialInstructions()` + `LeanCtx.ctxCall({name: "ctx_intent", ...})` before any file
access). Without it the worker reaches for `ls`/`grep` and is hard-blocked by
`pre-tool-gate-v2.sh`. `cap-workflow.js:257-278` already has this as a reusable `pctxInit()` block —
reuse it, do not re-author it.

Corollary: the prior draft's "Context Caching" claim was wrong. A fresh subagent inherits nothing;
context-packing is *mandatory*, not avoided. Only a fork inherits.

## 4. The frozen spec

The Coordinator writes the spec **before** spawning. The worker prompt is not the spec — it is a
pointer plus the non-negotiables.

Worker prompt = three parts, always:
1. the pctx init mandate (fresh workers only)
2. the **absolute** path to the spec file
3. the `**Accepts:**` criteria restated inline, the branch name, and the tool/nesting constraints

Every spec step declares `**Files:**` (absolute paths in scope) and `**Accepts:**` (an observable
condition the Coordinator can re-verify by running a command itself), per
`ai/skills/session-artifacts/SKILL.md`.

**Path — open decision, see Step 3.** The standing rule (`ai/rules/agent-user-global.md:140`) fixes
a single `plans/spec.md`. That does not survive concurrent workers, each of which needs its own
spec. Recommendation: adopt `plans/specs/<worker-label>.md` and amend the rule in the same commit,
so `plans/spec.md`, `plans/specs/`, and `plans/active-context.md` never compete as three handoff
paths.

`plans/active-context.md` is **not** a spec location — it is an ephemeral ≤30-line focus pointer
re-read at compaction (`ai/skills/session-artifacts/SKILL.md`). Record only
`plan:` / `step:` / `focus:` pointers there.

## 5. Worker definitions — tool budget, isolation, anti-nesting

Claude Code reads subagent definitions from `.claude/agents/*.md`. In this repo those are symlinks
created by `setup.sh:179-192` — **edit `ai/agents/<name>.md`, never the symlink.**

Frontmatter keys in use today across the 11 definitions: `name` (11), `description` (11),
`model` (11), `tools` (7), `type` (5), `version` (5), `permissionMode` (1).
`memory:` and `isolation:` are used by **zero** — adding them is real work, not a switch to flip.

### Anti-nesting is a config control, not a prompt

Subagents **can** spawn subagents by default — up to three layers below the main conversation on
2.1.219+ (this machine is 2.1.220). The prior draft's "hardcode the rule into the worker's system
prompt" is the weakest available control. Enforce declaratively, in priority order:

1. **Per-agent** — declare an explicit `tools:` allowlist that omits `Agent`, or list `Agent` under
   `disallowedTools`. Critical caveat: **omitting the `tools:` field entirely inherits every tool,
   including `Agent`.** Today 7 of 11 definitions have a `tools:` allowlist and none of the 7
   includes `Agent`, so those 7 cannot nest. The 4 that lack `tools:` —
   `cicd-audit`, `cicd-auto-retry`, `cicd-monitor`, `cicd-review` — **can nest right now.**
2. **Global** — `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` in settings.json (needs ≥2.1.217);
   `"1"` disables nesting outright. Not set anywhere in this repo today.
3. Keep the prose rule in the system prompt as a redundant second layer only.

`Agent(agent_type)` allowlist syntax applies only to an agent running as the main thread via
`claude --agent`; inside a subagent definition the parenthesized type list is ignored.

### Isolation is not free and not stack-compatible

`isolation: "worktree"` — available both as an `Agent` tool parameter and as agent frontmatter —
gives the worker its own git worktree, auto-removed if unchanged. Costs ~200-500 ms plus disk per
agent. Use it **only** when parallel workers write concurrently and would otherwise conflict.

Gotchas that must be respected:
- It writes under `.claude/worktrees/`, **not** this repo's `.trees/<description>/` stack layout.
- The in-session `EnterWorktree` tool ignores the `WorktreeCreate`/`WorktreeRemove` hooks wired at
  `.claude/settings.json:399-427` (upstream anthropics/claude-code#36205) and creates a fresh
  auto-named branch.
- Default `worktree.baseRef: fresh` branches from `origin/<default-branch>`, discarding the
  Coordinator's local HEAD.

Rule: **for stack work, do not isolate** — have the worker commit on the stack branch in the shared
tree. Reserve `isolation: worktree` for agents that never touch Charcoal or the `stack-*` skills.
When a worktree *is* needed, create it through the `stack-create` skill, never hand-rolled
`git worktree add`.

`memory: user|project|local` selects the agent's **memory scope**. It provides zero working-tree
isolation. The two keys are independent decisions, not alternatives.

## 6. Retrieving worker output

The prior draft's "the orchestrator just reads the `git diff`" is only true in one of two cases.
State both:

- **No isolation** — worker edits the shared tree; Coordinator reads `git diff` / `git status`
  directly.
- **`isolation: worktree`** — `git diff` in the Coordinator's tree is **empty**. The worker must
  commit and report its branch and worktree path; the Coordinator reads
  `git diff <base>...<worker-branch>` or enters via `EnterWorktree({path: "<abs path>"})`.

A subagent's conversational return is a text summary, never the diff. Note also that a subagent's
final report is not shown to the user — the Coordinator must relay what matters.

**Every return must be machine-readable.** Under `Workflow`, pass `opts.schema` and branch on typed
fields. Under ad-hoc `Agent`, state the JSON contract in the prompt and validate on receipt. Reuse
the existing contracts in `ai/skills/cap/references/schemas.md` (`IMPL_SCHEMA`, `REVIEW_SCHEMA`,
`VERDICT_SCHEMA`) rather than inventing new ones. Schema conformance guarantees **shape only** — a
worker can emit well-formed JSON that is untrue, so §9 still applies.

## 7. Signalling and the control loop

There is no single "the framework resumes the orchestrator" behaviour. Name the mechanism:

| Need | Mechanism |
|---|---|
| Coordinator has nothing else to do | foreground `Agent(...)` — blocks, returns final text |
| Coordinator keeps working | `Workflow` (background; task notification on completion) |
| Wake a completed/idle teammate | `SendMessage({to, summary, message})` — resumes it from its transcript |
| External event stream (CI, pods, logs) | `Monitor` — zero tokens while silent |
| One-shot local process | `Bash(run_in_background: true)` |
| Cancel a runaway worker | `TaskStop` |

`SendMessage` is the messaging primitive — PascalCase, params `{to, message, summary}`. There is no
`send_message` tool and no `@Teammate` syntax. **Plain text output is not visible to other agents**:
a worker that merely prints its result is silently unheard.

Polling is never required. Do not write CPU-burning wait loops.

### Hook events

Real events relevant here: `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`,
`TeammateIdle`, `WorktreeCreate`, `WorktreeRemove`. The task/teammate three are team-only and
require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — already set at `.claude/settings.json:6`.

**`TaskCreated`, `TaskCompleted`, `TeammateIdle`, `WorktreeCreate`, and `WorktreeRemove` do not
support `matcher`.** Emit the hook group with no matcher key and validate with
`scripts/hook_config_check.py` (`MATCHER_UNSUPPORTED`, :49-62). Existing defect to fix:
`.claude/settings.json:368,379` and `ai/config/claude/settings.base.json` set `"matcher": ".*"` on
`TaskCreated`/`TaskCompleted` — dead config. `SubagentStop` *does* support matchers.

A `TaskCompleted` hook can block completion and send feedback back to the agent via exit code 2.

Already wired: `TaskCreated`/`TaskCompleted` → `.claude/hooks/task-event-tracker.sh`
(`.claude/settings.json:366-387`); `PostToolUse` matcher `Agent` →
`.claude/hooks/teammate-quality-gate.sh` (`:311-319`, advisory — it never blocks).
Not wired: `TeammateIdle`, `SubagentStop`.

## 8. Shared task state

`TodoWrite` is per-agent and invisible to other agents. Cross-agent state uses the task list:
Coordinator calls `TaskCreate` per spec step, encodes ordering with
`TaskUpdate({addBlockedBy: [...]})`, assigns with `TaskUpdate({owner})`. Workers claim via
`TaskList` → `TaskUpdate({owner})` and resolve with `TaskUpdate({status: "completed"})` — which is
what fires the `TaskCompleted` hook. `CLAUDE_CODE_TASK_LIST_ID` shares the list into worker
environments (`ai/skills/tool-routing/SKILL.md:183-194`).

`TaskCreate` does **not** spawn an agent. Spawning is a separate `Agent`/`Workflow` call.

Never abandon a list: `task-event-tracker.sh` keeps an open-task counter at
`/tmp/.claude-task-state-$CLAUDE_SESSION_ID` that `task-gate.sh` reads on session Stop, so an
orphaned worker task blocks Stop. Drive every task to `completed` or `cancelled`.

## 9. Verification gate — the Coordinator never accepts output on trust

On every worker return, before advancing:

1. Validate the return against the declared phase schema.
2. **Re-run the spec's `Accepts` command yourself.** Never accept the worker's self-report.
3. Inspect the real diff via the correct retrieval path for the isolation mode (§6).
4. Apply the quality checklist: conventional-commit format, no commits on `main`, PR stacked on the
   correct parent, CI green or the failure surfaced with a run URL, no secrets committed.
5. Only then `TaskUpdate({status: "completed"})`.

If verification fails the task stays `in_progress` and a blocker task is created. Do not begin
Step N+1 until Step N's `Accepts` criteria are met.

## 10. Failure semantics

`agent()` returns **`null`** when the worker hit a terminal API error after retries or the user
skipped it. Always guard (`if (!result) return {error: '<label>-agent-failed'}`) before touching any
field; `.filter(Boolean)` every `parallel()`/`pipeline()` result array. A `pipeline` stage that
throws drops that item to `null` and skips its remaining stages.

Three terminal states, reported differently:
- **`error`** — worker died. Retry once, then surface with the label.
- **`retry`** — schema-invalid or `valid: false` output. Bounded at 3 attempts, each re-prompted
  with the prior `issues[]`, then convert to `blocked`.
- **`blocked`** — gate failed after the retry budget. Stop, `TaskCreate` a blocker, escalate to the
  user with a concrete unblock path.

Escalation ladder: re-send the spec via `SendMessage` naming the specific gap → escalate the model
tier and respawn → `TaskStop` a hung worker. Never mark an unverified return `completed`.

A null or empty return is a failure, not a success.

## 11. Observability

Give every `agent()` call a unique `label:` and a `phase:` so `/workflows` shows live per-phase
progress and yields the run id for `resumeFromRunId`. Use `log()` at phase boundaries. Out of band:
`TaskList`/`TaskGet` read shared state, `TaskOutput` reads a background task's output, `TaskStop`
cancels.

**Log every cap.** If the orchestration bounds coverage (top-N, no-retry, sampling), `log()` what
was dropped — silent truncation reads as "covered everything" when it did not.

## 12. Agent Teams and `teammateMode` — correcting a common error

`teammateMode` is a **display** setting, not a spawning setting. Values: `in-process` (default),
`auto`, `tmux`, `iterm2`. `auto` means *split into tmux/iTerm2 panes if available* — so
`teammateMode: "auto"` is the opposite of "use native agents instead of tmux". It is already set at
`.claude/settings.json:471`.

Agent teams remain experimental. `SendMessage` addresses teammates by name; idle teammates stay
running and addressable (hidden from the panel after 30 s, resumed on message).

---

## Steps

### Step 1 — Close the anti-nesting hole in existing agent definitions
**Files:** `ai/agents/cicd-audit.md`, `ai/agents/cicd-auto-retry.md`, `ai/agents/cicd-monitor.md`,
`ai/agents/cicd-review.md`
**Accepts:** each of the four declares an explicit `tools:` allowlist that omits `Agent`;
`grep -L '^tools:' ai/agents/*.md` returns nothing; `bash .claude/hooks/config-integrity.sh`
exits 0.

### Step 2 — Author the executor worker definition
**Files:** `ai/agents/executor-implement.md` (new)
**Accepts:** `model: sonnet`; `tools:` allowlist excludes `Agent`; the system prompt carries the
pctx init mandate and the "read the spec at the path given in your prompt" contract;
`.claude/agents/executor-implement.md` resolves as a symlink after `./setup.sh`;
`config-integrity.sh` exits 0.

### Step 3 — Resolve the frozen-spec path conflict (one commit, three files)
**Files:** `ai/rules/agent-user-global.md:140`, `ai/skills/tmux-orchestrator/SKILL.md:49-50`,
`plans/specs/.gitkeep` (new)
**Accepts:** exactly one spec convention is documented repo-wide;
`grep -rn 'plans/spec\.md' ai/ .claude/` returns only the updated rule text;
`plans/active-context.md` is not named as a spec location anywhere.
**Decision needed from the user:** adopt per-worker `plans/specs/<label>.md` (recommended — required
for concurrent workers) vs keep the single `plans/spec.md`.

### Step 4 — Fix the dead matcher config on task hooks
**Files:** `.claude/settings.json:366-387`, `ai/config/claude/settings.base.json` (same block)
**Accepts:** no `matcher` key on `TaskCreated` / `TaskCompleted`;
`python3 scripts/hook_config_check.py` reports no `MATCHER_UNSUPPORTED` issues; both files stay
byte-identical.

### Step 5 — Wire the missing completion signal
**Files:** `.claude/settings.json`, `ai/config/claude/settings.base.json`,
`.claude/hooks/teammate-quality-gate.sh`
**Accepts:** `TeammateIdle` (no matcher) and `SubagentStop` are wired to
`teammate-quality-gate.sh`; `hook_config_check.py` exits clean; a spawned worker's completion
produces a hook log line.

### Step 6 — Add the generic orchestration workflow script
**Files:** `.claude/workflows/orchestrate.js` (new — first entry in this directory)
**Accepts:** script has the required `export const meta = {name, description, phases}` literal;
≤3 literal `agent(` call sites so `pre-tool-gate-v2.sh` SECTION 8 does not hard-deny; every
`agent()` call passes a `schema` and a `label`; every result is null-guarded; a dry run completes
and returns a validated object.

### Step 7 — Scope `tmux-orchestrator` to non-Claude CLIs
**Files:** `ai/skills/tmux-orchestrator/SKILL.md`
**Accepts:** frontmatter `description` names Cursor/Codex/AGY only; a pointer to this plan appears
at the top for Claude-Code workers; the frozen-spec path matches whatever Step 3 decides.
**Do not delete the skill** — it is the only cross-CLI capability and no Claude primitive replaces
it.

### Step 8 — Decide the fate of `/tech-lead`
**Files:** `~/.claude/settings.json:216`, `.claude/settings.json:206`
**Accepts:** either the `"tech-lead": "off"` entries are removed at **both** scopes (skillOverrides
merge per key; project scope alone will not re-enable it) and the skill is updated to carry the
frozen-spec handoff and the §9 acceptance gate — or this plan records a decision to retire it in
favour of Step 6's workflow.
**Note:** `ai/skills/tech-lead/SKILL.md` is already v2 and already spawns via the `Agent` tool with
zero tmux references. There is no "convert from tmux" work here; the only real gaps are the spec
handoff and the acceptance gate.

---

## Corrections applied to the prior draft

| Prior claim | Reality |
|---|---|
| `invoke_subagent`, `send_message`, `@Teammate` | `Agent`, `SendMessage` — no `@` syntax exists |
| "Claude 3.5 Sonnet / 3.5 Haiku" | aliases only (`opus`/`sonnet`/`haiku`/`fable`/`inherit`); dated IDs hard-fail `config-integrity.sh` |
| Sub-agent APIs "leverage context caching without manual context-packing" | a fresh subagent inherits nothing; only `subagent_type: "fork"` inherits |
| `memory: project` is an isolation flag | `memory:` is a memory *scope*; isolation is only `isolation: worktree` |
| Anti-nesting via system prompt | nesting is allowed by default (3 layers); enforce via `tools:` allowlist / `disallowedTools` / `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` |
| "the orchestrator just reads the `git diff`" | empty under worktree isolation — needs `git diff <base>...<branch>` or `EnterWorktree` |
| "the framework automatically resumes the orchestrator" | no such generic behaviour; name the mechanism (§7) |
| Next Step 1: convert tmux worker definitions | no tmux worker definitions exist; `ai/agents/` already has 11 |
| Next Step 2: change tech-lead "instead of tmux pane splitting" | tech-lead v2 has zero tmux references — and is currently disabled |
| `teammateMode: "auto"` as the anti-tmux switch | it is a *display* setting; `auto` means "split into tmux/iTerm2 panes if available" — already set |
| `TaskCompleted`/`TeammateIdle` proposed as new | `TaskCompleted` already wired; both ignore `matcher` |
| (absent) | `Workflow` — the actual deterministic orchestration primitive |
