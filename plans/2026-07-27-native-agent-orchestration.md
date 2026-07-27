# Native Agent Orchestration Harness (Claude Code)

**Goal:** an AI-native engineering harness that is agentic *and* autonomous, where autonomy is
earned by measured evidence rather than switched on by config.

**Scope:** Claude Code only. Every primitive named here is a real Claude Code tool, settings key, or
hook event, verified against the live tool schemas and this repo on 2026-07-27 (Claude Code
2.1.220). Non-Claude CLIs (Cursor, Codex, AGY) stay on tmux — Step 10.

**Organised by mechanism, not by source.** Each mechanism is stated exactly once, with every source
that teaches it attributed inline. What we took from where — and what we rejected — is Appendix A.
Earlier revisions organised this document by provenance; that structure was the root cause of a
forked triage taxonomy, two competing review harnesses, and three restatements of progressive
disclosure. It is not recoverable by editing; the reorganisation is the fix.

Sources: `~/git/agent-skills` @ `7829ffd` (**AS**), `~/git/BMAD-METHOD` @ `bb45db4a` v6.10.0
(**BM**), this repo (**RE**). Full paths in Sources.

---

# Part I — Foundations

## 1. Delegation gate — when not to delegate

Spawning costs ~5-10 s spawn plus 10-20 s context setup, and a fresh worker re-pays the system
prompt and re-reads the spec in its own context. Fan-out trades **tokens for wall-clock**, never
tokens for tokens.

Delegate only when the subtask exceeds ~30 s of Coordinator work **and** at least one holds:
- 10+ files touched, or inter-file dependencies the Coordinator would otherwise hold in context
- an isolated tool set or independent perspective is the point (review, audit, second opinion)
- large tool output (logs, test runs, doc sweeps) that must stay out of the Coordinator's context

Otherwise the Coordinator edits locally (**RE** `plans/agent-delegation-patterns.md:180-240`, whose
matrix row reads "Implementation | General | Sequential | ❌ NO | Faster to edit locally").

Delegation is orthogonal to skill invocation (**RE** `plans/skill-delegation-patterns.md:111-141`):
a worker spawned without naming the skill it should load degrades to the "agent without skill"
quadrant. Always name the skill in the spec.

## 2. Runtime selection

| Runtime | Use when | Invocation |
|---|---|---|
| **`Workflow`** | deterministic, repeatable, multi-phase fan-out needing schema-validated returns and replay | `Workflow({script, args})` / `Workflow({scriptPath, resumeFromRunId})` |
| **Ad-hoc `Agent`** | one-off, dynamically shaped, or single-worker delegation | `Agent({subagent_type, prompt, name, model, isolation})` |
| **Agent Teams** | teammates that must *challenge each other* to reach the answer | `teammateMode` + `SendMessage` (experimental) |

Subagent fan-out yields **a verdict on a known artifact**; Agent Teams runs **an investigation to
find the artifact among competing hypotheses** (**AS** `references/orchestration-patterns.md`).
Teams cost materially more and are justified only when the adversarial debate itself produces
correctness — an intermittent production bug with several mutually exclusive plausible causes, not a
routine review.

`Workflow` script primitives: `agent(prompt, opts)`, `parallel(thunks)` (barrier),
`pipeline(items, ...stages)` (no barrier — the default), `phase(title)`, `log(msg)`, plus `args` and
`budget`. `opts.schema` forces the worker through a StructuredOutput tool and returns a validated
object. Saved scripts live in `.claude/workflows/` — **this repo has none today**; `cap-workflow.js`
is loaded by path. `workflow()` nesting is one level; a nested call throws.

Prefer `pipeline()`. A barrier is correct only when stage N needs all of stage N-1 (dedup,
early-exit on zero, cross-item comparison).

**Parallel fan-out requires multiple `Agent` calls in one assistant turn** — sequential turns
serialize (**AS** same file).

`teammateMode` is a **display** setting, not a spawning one: `in-process` (default), `auto`, `tmux`,
`iterm2`. `auto` means *split into tmux/iTerm2 panes if available*, so it is the opposite of "use
native agents instead of tmux." Already `auto` at `.claude/settings.json:471`. Agent teams remain
experimental; `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set at `:6`. Clean up **through the lead**
— teammates lack full team context for cleanup.

## 3. Concurrency and cost caps

Workflow concurrency caps at `min(16, cores - 2)`; lifetime cap 1000 agents;
`parallel()`/`pipeline()` accept ≤4096 items.

**Repo hard limit:** `.claude/hooks/pre-tool-gate-v2.sh` SECTION 8 regex-counts literal `agent(`
call sites in a submitted Workflow script. **More than 3 literal sites is a hard deny.** A
`parallel()`/`pipeline()` over a `.map()` or bare variable is statically undecidable and only warns
`[fan-out-undecidable]`; there the Coordinator must bound the array to ≤3 concurrent workers itself.

**Log every cap.** Any bound on coverage (top-N, no-retry, sampling) must be `log()`ed — silent
truncation reads as "covered everything." See §21 for the concrete failure this prevents.

## 4. Roles and model tiers

- **Coordinator** — the main session: architecture, planning, spec authoring, verification. Pinned
  to Opus at `.claude/settings.json:105`; advisor `fable` at `:462`.
- **Executor** — subagents doing hands-on multi-file work.

Tier is **declared, not narrated**: `model:` in `ai/agents/<name>.md` frontmatter.

| Alias | Use for |
|---|---|
| `haiku` | mechanical, narrow, well-defined loops (go-build-resolver, cicd-auto-retry) |
| `sonnet` | standard multi-file implementation and test-writing — the executor default |
| `opus` | correctness/security review, subtle-bug hunts |
| `fable` | escalation only (stalled or beyond-frontier work) |
| ~~`inherit`~~ | **forbidden in this repo** — the Coordinator is permanently opus-pinned, so `inherit` silently produces an Opus worker and defeats the cost split |

**Aliases only.** `.claude/hooks/config-integrity.sh` `check_agent_models()` exits 1 on any dated
model ID, failing the whole tree. Product names like "Claude 3.5 Sonnet" are not writable config.

## 5. Worker spawn mode

Three options, one decision rule.

- **`Explore`** (built-in, read-only) — read-heavy research answerable *cold* from the repo. First
  choice; do not author a custom researcher before ruling it out (**AS** Pattern 5).
- **Fork** — `Agent({subagent_type: "fork"})`. Inherits the parent's full conversation and loaded
  tool context; always runs the parent's model (`model` ignored); backgrounded, keeping its tool
  output out of the parent's context; **cannot re-delegate.** Use when the answer depends on *this
  session's* loaded context or prior conversation (**RE** `ai/rules/agent-user-global.md:76-84`).
- **Fresh** — any other `subagent_type`. Starts cold: spawn prompt + project context + tools only.
  Use when isolation is the point (independent review) or a specialised tool set is needed.

**Every fresh worker in this repo must open its prompt with the pctx init mandate** —
`Serena.initialInstructions()` + `LeanCtx.ctxCall({name: "ctx_intent", ...})` before any file
access. Without it the worker reaches for `ls`/`grep` and is hard-denied by `pre-tool-gate-v2.sh`.
Reuse the existing `pctxInit()` block at `ai/skills/cap/cap-workflow.js:257-278`; do not re-author
it. This is the single normative statement of the mandate — everything else points here.

A fresh subagent inherits **nothing**; context-packing is mandatory, not avoided. Only a fork
inherits.

---

# Part II — The spec contract

## 6. Freeze the intent, not the whole spec

Freezing an entire spec file is too coarse: any spec defect then forces a human round-trip, capping
the harness at A1/A2 on the Part VIII ladder forever. **BM** (`bmad-dev-auto/step-04-review.md`) splits it:

- **`<intent-contract>`** — the captured intent, verbatim, **never modified by any agent.** Do not
  infer intent unless exactly one reading is possible. A defect traced here is an `intent_gap`
  (§23).
- **Derived sections** (tasks, ACs, verification commands) — amendable when review proves them
  wrong, but only through an append-only **`## Spec Change Log`** recording four things: the
  triggering finding, what was amended, **the known-bad state now avoided**, and the **KEEP
  instructions** (what worked and must survive re-derivation).

KEEP instructions are what make the loop *ratchet* rather than oscillate: each iteration is
forbidden from re-entering a recorded known-bad state and from discarding what already worked.
Without them a repair loop can cycle between two broken states indefinitely while appearing to
progress.

Consequences of a defect in either region are defined once, in §23. Do not restate them here.

## 7. Spec readiness bar

No worker is spawned until all seven hold (**BM** READY FOR DEVELOPMENT):

**Actionable** (every task names a file path and a specific action) · **Logical** (ordered by
dependency) · **Testable** (ACs in Given/When/Then) · **Surface-anchored** · **Complete** (no
placeholders/TBDs) · **Sufficient** (no unresolved requirement, acceptance, or dependency gaps) ·
**Coherent** (no internal contradictions).

**Surface-anchored** is the non-obvious one and the most valuable: ACs must observe the *outermost*
surface the intent references, never a more internal proxy — assert the API response, not the
database row behind it. It is the criterion that stops a worker from satisfying an AC against an
implementation detail it just wrote.

## 8. Worker prompt composition

Three parts, always:
1. the pctx init mandate (§5; fresh workers only)
2. the **absolute** path to the spec file
3. the `Accepts` criteria restated inline, the branch name, and the tool/nesting constraints

Every spec step declares `**Files:**` (absolute paths in scope) and `**Accepts:**` — an observable
condition the Coordinator can re-verify by running a command itself (**RE**
`ai/skills/session-artifacts/SKILL.md`).

## 9. Spec paths

`plans/specs/<worker-label>.md`, one per worker, from the template Step 3 creates. Per-worker files
are required: a single `plans/spec.md` cannot serve concurrent workers.

`plans/active-context.md` is **not** a spec location — it is an ephemeral ≤30-line focus pointer
re-read at compaction. Record only `plan:` / `step:` / `focus:` there.

**Open decision — Step 3.** The standing rule at `ai/rules/agent-user-global.md:140` fixes a single
`plans/spec.md`. Adopting per-worker specs requires amending that rule in the same commit so
`plans/spec.md`, `plans/specs/`, and `active-context.md` never compete as three handoff paths.

---

# Part III — Worker definitions and isolation

## 10. Definition files and the tool budget

Claude Code reads subagent definitions from `.claude/agents/*.md`; in this repo those are symlinks
created by `setup.sh:179-192`. **Edit `ai/agents/<name>.md`, never the symlink.**

Frontmatter keys in use across the 11 definitions: `name` (11), `description` (11), `model` (11),
`tools` (7), `type` (5), `version` (5), `permissionMode` (1). `memory:` and `isolation:` are used by
**zero** — adding them is real work, not a switch.

Full supported set for plugin-distributed agents (**AS** orchestration-patterns): `name`,
`description`, `tools`, `disallowedTools`, `model`, `maxTurns`, `skills`, `memory`, `background`,
`effort`, `isolation`, `color`, `initialPrompt`. Two gotchas:

- **Plugin agents silently ignore `hooks`, `mcpServers`, and `permissionMode`.** Our
  `mcp_config_manager` sets `permissionMode`; that works only because these are symlinked into
  `.claude/agents/`, not shipped as a plugin.
- **`skills:` and `mcpServers:` are honored for subagents but ignored for teammates.** A persona
  depending on a skill needs it configured at session level to work in both modes.

`memory: user|project|local` selects the agent's **memory scope** and gives zero working-tree
isolation. Independent of `isolation:`, not an alternative to it.

## 11. Anti-nesting is a config control

Subagents **can** spawn subagents by default — up to three layers below the main conversation on
2.1.219+ (this machine is 2.1.220). A system-prompt instruction enforces nothing. Controls, in
priority order:

1. **Per-agent** — an explicit `tools:` allowlist omitting `Agent`, or `Agent` in `disallowedTools`.
   **Omitting `tools:` entirely inherits every tool, including `Agent`.** Today 7 of 11 definitions
   have an allowlist and none includes `Agent`; the 4 without one — `cicd-audit`,
   `cicd-auto-retry`, `cicd-monitor`, `cicd-review` — **can nest right now.**
2. **Global** — `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (needs ≥2.1.217); `"1"` disables nesting
   outright. Not set anywhere today. Step 1 sets it, because priority 1 protects only the files that
   exist when it runs.
3. Prose in the system prompt, as a redundant third layer only.

`Agent(agent_type)` allowlist syntax applies only to an agent running as the main thread via
`claude --agent`; inside a subagent definition the parenthesized list is ignored.

## 12. Isolation and git safety

`isolation: "worktree"` (an `Agent` parameter and an agent frontmatter key) gives the worker its own
git worktree, auto-removed if unchanged, at ~200-500 ms plus disk per agent.

Constraints:
- It writes under `.claude/worktrees/`, **not** this repo's `.trees/<description>/` stack layout.
- The in-session `EnterWorktree` tool ignores the `WorktreeCreate`/`WorktreeRemove` hooks wired at
  `.claude/settings.json:399-427` (upstream anthropics/claude-code#36205) and creates a fresh
  auto-named branch.
- Default `worktree.baseRef: fresh` branches from `origin/<default-branch>`, discarding the
  Coordinator's local HEAD.

Decision table — this is the full matrix, including the case the harness is actually built for:

| Situation | Configuration |
|---|---|
| Single worker, shared tree | no isolation; worker commits on the current branch |
| Parallel writers, non-stack work | `isolation: worktree` |
| **Parallel writers on stack work** | **neither** — serialize the workers on the shared tree, **or** give each a `stack-create` worktree under `.trees/` and have the Coordinator merge. `isolation: worktree` stays forbidden for stack work. |
| Any worktree needed | create it through the `stack-create` skill, never hand-rolled `git worktree add` |

---

# Part IV — Control flow

## 13. Interactive and unattended modes are different

The mechanism table in §14 holds **only when a human or the harness is present to receive a
notification.** **BM** (`bmad-dev-auto/SKILL.md` § Subagents) is explicit:

> Never run a subagent in the background / detached / async, and never end your turn to "await a
> completion notification." This workflow runs unattended: there is no event loop to resume a
> yielded turn, so a backgrounded subagent never hands control back and the run stalls.

| | Interactive | Unattended (cron, CI, `/loop`, autonomous run) |
|---|---|---|
| Fan-out | background `Workflow`; a task notification resumes you | **synchronous only** — several blocking calls awaited together in one turn |
| Ending a turn | fine, you will be re-invoked | **forbidden** except via HALT (§15) |
| Waiting on external state | `Monitor` (event stream), `ScheduleWakeup` (timed re-entry) | unavailable — the run must conclude |

**`Workflow` is still usable unattended**, because `agent()` calls inside a script are synchronous
awaits and the script *is* the run. What is forbidden is the Coordinator ending its turn on a
backgrounded `Workflow`. An unattended entry point invokes `Workflow` and blocks on it in the same
turn.

## 14. Signalling mechanisms

| Need | Mechanism |
|---|---|
| Coordinator has nothing else to do | foreground `Agent(...)` — blocks, returns final text |
| Coordinator keeps working (interactive only) | background `Workflow`; task notification on completion |
| Wake a completed or idle teammate | `SendMessage({to, summary, message})` — resumes it from its transcript |
| External event stream (CI, pods, logs) | `Monitor` — zero tokens while silent |
| Timed re-entry (interactive `/loop`) | `ScheduleWakeup` |
| One-shot local process | `Bash(run_in_background: true)` |
| Read a background task's output | `TaskOutput` |
| Cancel a runaway worker | `TaskStop` |

There is no generic "the framework resumes the orchestrator" behaviour — name the mechanism.

`SendMessage` is the messaging primitive: PascalCase, params `{to, message, summary}`. There is no
`send_message` tool and no `@Teammate` syntax. **Plain text output is not visible to other agents** —
a worker that merely prints its result is silently unheard. *Observed live during this plan's own
review: of three reviewer agents, the two that called `SendMessage` delivered and the third went
idle with its findings stranded until explicitly asked.*

Polling is never required in an interactive session. Do not write CPU-burning wait loops.

## 15. HALT protocol (unattended)

Every exit path writes a terminal status to a durable artifact before stopping — there is nobody to
read a chat message. Minimum: `status ∈ {done, blocked}`, the blocking condition in one line, and
the artifact path, written to the spec's frontmatter or to a fallback result file when the spec path
is unknown.

**BM** is obsessive here and correctly so: even degenerate cases get a deterministic write-back path
— an unresolvable story id lands at `<id>-unresolved.md`, an ambiguous on-disk match at
`<id>-ambiguous.md`, deliberately *not* a third title-derived filename that could collide with the
existing candidates.

A run ending without a durable status is indistinguishable from a crash. Unattended, "surface it"
means *write it where the next run will find it.*

## 16. Shared task state

`TodoWrite` is per-agent and invisible to other agents. Cross-agent state uses the task list: the
Coordinator calls `TaskCreate` per spec step, orders with `TaskUpdate({addBlockedBy: [...]})`,
assigns with `TaskUpdate({owner})`. Workers claim via `TaskList` → `TaskUpdate({owner})` and resolve
with `TaskUpdate({status: "completed"})`, which fires the `TaskCompleted` hook.
`CLAUDE_CODE_TASK_LIST_ID` shares the list into worker environments (**RE**
`ai/skills/tool-routing/SKILL.md:183-194`).

`TaskCreate` does **not** spawn an agent. Spawning is a separate `Agent`/`Workflow` call.

Never abandon a list: `task-event-tracker.sh` keeps an open-task counter at
`/tmp/.claude-task-state-$CLAUDE_SESSION_ID` that `task-gate.sh` reads on session Stop, so an
orphaned worker task blocks Stop. Drive every task to `completed` or `cancelled`.

## 17. Hook events

Relevant: `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`,
`WorktreeCreate`, `WorktreeRemove`. The task/teammate three are team-only and need
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, already set at `.claude/settings.json:6`.

**`TaskCreated`, `TaskCompleted`, `TeammateIdle`, `WorktreeCreate`, and `WorktreeRemove` do not
support `matcher`** — emit the hook group with no matcher key and validate with
`scripts/hook_config_check.py` (`MATCHER_UNSUPPORTED`, `:49-62`). `SubagentStop` *does*.

Live defect: `.claude/settings.json:368,379` and the byte-identical
`ai/config/claude/settings.base.json` set `"matcher": ".*"` on `TaskCreated`/`TaskCompleted` — dead
config. Step 5 fixes it.

A `TaskCompleted` hook can block completion and feed back to the agent via exit code 2.

Already wired: `TaskCreated`/`TaskCompleted` → `task-event-tracker.sh` (`:366-387`); `PostToolUse`
matcher `Agent` → `teammate-quality-gate.sh` (`:311-319`, advisory — it never blocks).
Not wired: `TeammateIdle`, `SubagentStop`.

## 18. Observability

Give every `agent()` call a unique `label:` and a `phase:` so `/workflows` shows live per-phase
progress and yields the run id for `resumeFromRunId`. `log()` at phase boundaries.

---

# Part V — Verification and review

One mechanism, one finding shape, one taxonomy. Both **AS** and **BM** converge here; where they
differ, the merge is stated explicitly.

## 19. The two bars

Both must pass before a return is accepted (**AS** `references/definition-of-done.md`):

- **Acceptance criteria** — per-task, from the spec. *"Did we build this thing?"*
- **Definition of Done** — standing, project-wide, identical every time. *"Is it ready?"*

Sequence on every worker return:
1. Validate the return against the declared phase schema (§20).
2. **Re-run the spec's `Accepts` command yourself.** Never accept the worker's self-report.
3. Inspect the real diff by the retrieval path for the isolation mode (§12): shared tree →
   `git diff`; `isolation: worktree` → the Coordinator's diff is **empty**, so the worker must
   commit and report its branch and worktree path, and the Coordinator reads
   `git diff <base>...<worker-branch>` or enters via `EnterWorktree({path})`. A subagent's
   conversational return is a text summary, never the diff.
4. Apply the standing Definition of Done at `ai/references/definition-of-done.md` (Step 2).
5. Only then `TaskUpdate({status: "completed"})`.

Failure leaves the task `in_progress` and creates a blocker task. Do not begin Step N+1 until Step
N's `Accepts` are met.

This is the orchestration-gate instantiation of the standing behavior "verify, don't assume" (§30).

## 20. The finding contract

Every reviewer return is machine-readable. Under `Workflow`, pass `opts.schema` and branch on typed
fields; under ad-hoc `Agent`, state the JSON contract in the prompt and validate on receipt. Schema
conformance guarantees **shape only** — a worker can emit well-formed JSON that is untrue, so §19
still applies.

A finding carries exactly these fields, plus any the producing lens declares:

| Field | Meaning |
|---|---|
| `lens` | the code of the lens that produced it — **required**, the dedupe rule needs it |
| `location` | file:line-range for code, section for documents |
| `trigger_condition` | the problem, or the condition exposing it, in one line |
| `guard_snippet` | the concrete fix, guard, or missing check |
| `potential_consequence` | what goes wrong if it ships as-is |

**No `severity`, `priority`, or ranking field.** Severity is assigned by the Coordinator during
triage, never by the producer. **AS** establishes the principle — *"the reviewer's output is data,
not verdict"* (`doubt-driven-development/SKILL.md:170`) — and **BM** extends it to severity
specifically (`step-04-review.md:37`):

> Disregard any severity assigned by a reviewing subagent. Review subagents operate under by-design
> information asymmetry and do not have enough context to set final severity for this workflow.

A reviewer sees one artifact through one lens; severity is a function of consequence *for the
artifact's consumer*, which only the Coordinator knows. The Coordinator assigns `low` (none or
cosmetic) / `medium` (tolerable) / `high` (intolerable).

**Dedupe only findings with the same claim *and* the same required action.** Then evaluate each
survivor independently — *"do not reject a finding because a related finding was rejected."* Overlap
between lenses is signal, not noise.

`ai/skills/cap/references/schemas.md` currently requires `severity` per finding at `:126` and
`:139`; Step 15 amends it. Until then, cap's `REVIEW_SCHEMA` and this section conflict.

## 21. Reviewer input isolation

A reviewer receives **ARTIFACT + CONTRACT only.** Never the claim, never your reasoning, never
another reviewer's findings. Handing over a conclusion biases toward agreement.

Both sources enforce this independently: **AS** as the doubt cycle's central rule
(`doubt-driven-development/SKILL.md:106,131` — *"Pass ARTIFACT + CONTRACT only. Do NOT pass the
CLAIM"*), and **BM** per-lens (`bmad-review/SKILL.md:31` — *"Each sees the content and
`also_consider`, never another lens's findings"*, except the single lens named in an `after` field).

The reviewer prompt is adversarial: *"Find what is wrong. Assume the author is overconfident. Do NOT
validate. Do NOT summarize."*

**Stance toward zero findings is a per-lens property**, declared in config: most lenses treat an
empty result as valid; an adversarial lens treats it as **suspicious** and re-analyses before
concluding; editorial lenses hold content sacrosanct and critique only form.

**Do not import BM's numeric quota.** `lens-adversarial.md` demands "find at least ten issues" while
its own `SKILL.md` says "report what is real — never pad to look thorough." A quota manufactures
findings. Keep the suspicion, drop the number.

**Doubt theater (checkable signal):** across 2+ cycles where the reviewer surfaced substantive
findings, zero were classified actionable → you are validating, not doubting. Stop and escalate.

> **Evidence, from this document's own review.** Three fable reviewers were given artifact +
> contract only and no severity authority; they returned 58 findings and **converged independently
> on five**, including a forked triage taxonomy and two competing review harnesses in the plan
> itself. An earlier audit of this same plan instead passed each reviewer the verdict, the evidence,
> *and* the proposed correction — and a large fraction of its findings were overturned on
> re-examination, consistent with reviewers reacting to framing rather than the artifact. That
> earlier run also silently dropped high-severity findings to an unlogged `.slice(0, 8)` cap, which
> is why §3 requires logging every cap. The three-lens findings are committed with this plan; the
> earlier run's transcript was not retained, so treat its numbers as indicative only.

## 22. One review mechanism

There is **one** review implementation: the lensed review skill (Step 10). The orchestrator's
reviewer stage invokes it rather than embedding its own. The doubt cycle is its **adversarial
lens**, not a parallel harness. Every lens emits the §20 finding shape.

Lenses are declared as keyed config tables (**BM** `bmad-review/customize.toml`):

| Field | Purpose |
|---|---|
| `code` | stable identity; the merge key for overrides |
| `applies_to` | `code` \| `docs` \| `any` — the first filter |
| `when` | prose refinement of applicability |
| `after` | names the one lens whose findings this lens receives |
| `instruction` | the whole recipe; **empty string disables the lens** |

Each lens's reference file loads **just-in-time** — **BM**'s five `lens-*.md` files total 170 lines,
but only the running lens's file is ever paid for. A default review runs every enabled lens matching
`applies_to` and `when`; an explicitly requested lens runs regardless of both.

**Anti-drift:** *"Never claim a capability from this file; read the resolved lenses and work from
those."* The skill body must not assert what config decides.

This is the structural fix for the collision problem §26 describes. Review-ish skills today:
`hawk`, `pr-review`, `code-health`, `bmad-custom-pr-review`, plus `security-reviewer`,
`claude-code-review-agent`, `silent-failure-hunter`, `database-reviewer`, `performance-optimizer` as
agents. Consolidating them removes collisions rather than merely detecting them. Note `simplify`,
`review`, and `code-review` are **Claude Code built-ins**, not repo skills — they cannot be shimmed
or retired, and the consolidated skill must not take a name that collides with them (Step 10 uses
`lensed-review`).

## 23. One triage taxonomy

**AS**'s RECONCILE classes and **BM**'s five categories describe the same activity at different
points in the loop. They are merged here into one taxonomy; the **AS** class each subsumes is noted.
The first three are **this change's problem**, the last two are not.

| Category | Meaning | Action | Subsumes (**AS**) |
|---|---|---|---|
| `intent_gap` | root cause inside `<intent-contract>`; unresolvable without a human | **save the attempted change as a patch file**, revert code, HALT `blocked` with the unresolved questions and the patch path | contract misread |
| `bad_spec` | caused by the change; the spec should have prevented it | revert code (extracting KEEP instructions first, §6), amend the derived spec under the change log, re-derive | contract misread / valid+actionable |
| `patch` | caused by the change; trivially fixable | auto-fix, then re-run the spec's verification commands | valid + actionable |
| `defer` | pre-existing, surfaced incidentally | append to `deferred-work.md`; do not fix | valid trade-off |
| `reject` | noise | drop silently | noise |

Tie-breakers: **in doubt between `bad_spec` and `patch`, prefer `bad_spec`** — a spec-level fix
produces more coherent code. **Unsure between `defer` and `reject`, prefer `reject`** — only defer
what you are confident is real, or the deferred file becomes a landfill.

**Scope authority.** A finding may be routed `defer` or `reject` *as out of scope* **only on the
authority of the intent itself.** The spec's own scope language, the plan, and the shape of the diff
are **not** admissible scope authorities — if only they exclude the finding, that is evidence
*against the current reading* (route `intent_gap` or `bad_spec`), not evidence of out-of-scope. This
closes the circular-reasoning hole an autonomous agent otherwise walks into: dismissing a finding
because the artifact it just wrote does not mention it.

Findings cascade: any `intent_gap` makes everything below moot; any `bad_spec` makes `patch`
findings moot because the code is about to be re-derived.

## 24. Loop bounds — all three, all persisted

The harness has three bounded loops. **Every bounded loop persists its counter in the governing
artifact's frontmatter.** An in-context counter silently resets at compaction, on a crash, or on a
resumed cron run, and the loop then runs forever.

| Loop | Bound | Persisted counter | Terminal condition |
|---|---|---|---|
| Schema-invalid retry | 3 | `retry_count` | convert to `blocked` |
| Doubt cycle | 3 | `doubt_cycle_iteration` | escalate; if 3 feels insufficient the artifact is too big — decompose, do not raise the bound |
| `bad_spec` re-derivation | 5 | `review_loop_iteration` | HALT `blocked`, condition `review repair loop exceeded 5 iterations (non-convergence)` |

Pair with an append-only **`## Review Triage Log`** in the spec: one entry per pass, counts per
category broken down by severity, and an `addressed_findings` list (or `none`). The loop's history
becomes auditable, and a pass that fixed nothing is visibly a pass that fixed nothing.

Worker-outcome states, distinct from finding categories: **`error`** (worker died or returned
`null`) → retry once, then surface; **`retry`** (schema-invalid or `valid: false`) → the bounded loop
above; **`blocked`** → HALT per §15 and escalate with a concrete unblock path.

`agent()` returns **`null`** when the worker hit a terminal API error after retries or the user
skipped it. Guard before touching any field; `.filter(Boolean)` every `parallel()`/`pipeline()`
array. A throwing `pipeline` stage drops that item to `null` and skips its remaining stages. **A
null or empty return is a failure, not a success.** Never mark an unverified return `completed`.

## 25. Follow-up signal

Computed, not judged: `followup_review_recommended` is true if any `patch`-triaged finding was
`high`, **or** if `3 × medium_count + 1 × low_count >= 5`. It counts only `patch` findings — never
`defer` or `reject` — and is written to frontmatter with the counts and the score (**BM**
`step-04-review.md:83`).

This is the mechanical demotion trigger Part VIII needs: recorded and reproducible rather than judged.

---

# Part VI — The skill system

## 26. Five layers, and our two gaps

**AS** `docs/developer-onboarding.md` §1 frames a harness as five composable layers:

| Layer | Job | **AS** | Ours | Status |
|---|---|---|---|---|
| **Skills** (*how*) | workflows with verification gates | 24 | ~73 | present, **unvalidated** |
| **Personas** (*who*) | roles with a perspective and output format | 4 | 11 | present |
| **Commands** (*when*) | user-facing entry points | `.claude/commands/` | `ai/commands/` | present |
| **References** (*what to check*) | shared checklists pulled in on demand | 7 | — | **missing** |
| **Evals** (*does it work*) | proof skills trigger and behave | 24 | — | **missing** |

The eval gap is the serious one: ~3× their skill count with zero evidence that any skill triggers
when it should, or that two of ~73 descriptions do not collide. Collision scales quadratically; at
73 skills it is near-certain, and it presents as the wrong skill activating — which looks like a
model failure and gets debugged as one.

## 27. Skill anatomy and context efficiency

Standard sections (**AS** `docs/skill-anatomy.md`): **Overview / When to Use (including when NOT
to) / Core Process / Common Rationalizations / Red Flags / Verification.** Three matter most for
autonomy and we have none of them:

- **Common Rationalizations** — a table of excuses an agent uses to skip a step, each with a factual
  rebuttal. The direct countermeasure to an autonomous agent talking itself out of a gate under
  pressure.
- **Red Flags** — observable signs the skill is being violated. The best are *checkable*, like the
  doubt-theater signal in §21.
- **Verification** — exit criteria where every checkbox names its evidence.

**Progressive disclosure** is the governing context rule, and it applies at two granularities.
Both sources teach it:
- **Reference material** (**AS**): SKILL.md under 500 lines; supporting files loaded on demand;
  references one level deep; **prefer scripts over inline code — executing a script consumes no
  context, only its output does, whereas inline code is paid for on every load.**
- **Workflow bodies** (**BM**): decompose into step files. `bmad-quick-dev` carries
  `step-01-clarify-and-route` … `step-05-present` plus `step-oneshot.md`; `bmad-dev-auto` shares
  `step-01`–`step-04` and `spec-template.md` but has no present step and no oneshot escape hatch.
  The rule is strict: *"Read one step fully, execute it, then load the next step only when directed.
  Do not skip, reorder, or pre-load steps"* — and it needs an explicit anti-shortcut instruction to
  survive: *"If a step says read fully and follow step-XX, you read and follow step-XX. No
  exceptions."*

A five-phase skill then pays for one phase at a time, and a `step-oneshot.md` preserves the coarse
path when the full sequence is overkill. Our `cap/SKILL.md` is monolithic and pays for every phase
on every load.

## 28. The customization layer

Every **BM** skill ships a `customize.toml` stamped *"DO NOT EDIT — overwritten on every update."*
Overrides live outside it and resolve base → team → user:

1. `{skill-root}/customize.toml` — shipped defaults
2. `{project-root}/_bmad/custom/<skill>.toml` — team
3. `{project-root}/_bmad/custom/<skill>.user.toml` — personal

Merge semantics, stated explicitly, which is what makes it safe: **scalars** override; **tables**
deep-merge; **arrays of tables keyed by `code` or `id`** replace on matching key and append on new;
**all other arrays** append.

Fallbacks differ across **BM**'s own skills and the difference matters: `bmad-review` falls back to
reading base `customize.toml` and using defaults, **dropping all overrides**; `bmad-dev-auto` and
`bmad-customize` document the richer three-file fallback that preserves them. **Adopt the
three-file fallback** — it is an upgrade over `bmad-review`, not a faithful copy of it.

The `file:` convention with its failure behavior: a value prefixed `file:` is a path or glob whose
contents load, and *"if a `file:` value cannot be read, name the failed file in the output header and
continue"* — partial-failure semantics stated, not left to the model.

Declarative extension points inside a skill, which we have no equivalent of (our hooks are all
tool-level): `activation_steps_prepend`, `activation_steps_append`, `on_complete`,
`persistent_facts`, `review_guidance`, `output_format`, `report_path`, `output_preferences`.

This is a live problem for us: our skills are symlinked from `ai/skills/` into every consumer, so
per-project or personal customization means editing the shared source of truth. We already suffer
the drift it prevents — `settings-symlink-guard` reports `~/.claude/settings.json` has become a
regular file diverging from the repo.

## 29. Skill lifecycle

**BM** has a complete lifecycle mechanism. We have none, and it shows: `tech-lead`,
`monitor-patterns`, and `tmux-automation` are simply `"off"` in `skillOverrides` with no forwarder,
no rationale, and no removal plan.

- **`removals.txt`** — a machine-readable retirement ledger the installer consumes to delete stale
  skills on update, with the *reason* inline. It records honest negative results:
  *"`bmad-investigate`: retired. Plain investigation reaches the same conclusions at lower cost."*
  A ledger recording what did **not** work is worth more than one recording only renames.
- **`v6-shims/`** — forwarders holding no logic, pinning the *legacy output contract* so existing
  callers keep working and forwarding resolved customization so existing overrides still apply.
  Removal *"rides the v7 cut — never a 6.x minor."* This is what permits aggressive consolidation
  without breaking consumers.
- **`aliases`** — prior `code` values, so an install recorded under an old name resolves forward
  instead of being orphaned.
- **`deprecated: true` + `deprecation-message`** — hidden from new users, visible to existing
  installs, pointing at the replacement. The lifecycle state our bare `"off"` lacks.
- **`post-install-message`** — an action-needed notice requiring acknowledgement on interactive
  installs. `setup.sh` has no way to tell the user a follow-up step is required.

**Registry.** `module-help.csv` carries columns frontmatter cannot: `phase`, `preceded-by`,
`followed-by`, `output-location`, `outputs` — a skill dependency graph plus declared artifacts. That
is the substrate for a generated router, for detecting orphaned or unreachable skills, and for
validating that a declared output is actually written. Step 12 generates the router from it rather
than hand-writing prose.

## 30. Core operating behaviors

Six always-on behaviors above every individual skill (**AS** `using-agent-skills/SKILL.md`), plus
its 10-item failure-mode list as a self-audit:

1. **Surface assumptions** — state them before non-trivial work: "correct me now or I proceed."
2. **Manage confusion actively** — on inconsistency: STOP, name it, present the tradeoff, wait.
3. **Push back when warranted** — quantify the downside ("adds ~200 ms latency", not "might be
   slower"). *"Sycophancy is a failure mode."*
4. **Enforce simplicity** — "if you build 1000 lines and 100 would suffice, you have failed."
5. **Maintain scope discipline** — surgical precision, not unsolicited renovation.
6. **Verify, don't assume** — evidence, never "seems right." §19 is its orchestration-gate form.

---

# Part VII — Evals

Four tiers. Tiers 1-3 are **AS** (`evals/README.md`); Tier 4 is **BM**
(`test/adversarial-review-tests/`).

| Tier | Checks | Runs | Cost |
|---|---|---|---|
| **1 Structural** | frontmatter, naming, required sections, command parity | CI | free |
| **2 Trigger & routing** | positive prompts rank their skill top-k; negatives don't; no two descriptions near-collide | CI | free |
| **3 Behavioral** | an agent following the skill satisfies its `expectations[]` | on demand | tokens |
| **4 Input sensitivity** | an optional input steers the skill by the *intended amount* | on demand | tokens |

**Tier 2 first.** A deterministic lexical approximation of routing (stemmed TF-IDF over
descriptions) — no model calls, CI-safe, free. It catches the two failure modes that dominate real
trigger bugs: a description missing the vocabulary users say, and an over-broad description
outranking the right skill. Metrics: a **rank-1 rate** against a committed floor, and a **collision
check erroring at ≥75% pairwise description similarity, warning at ≥50%**. A Tier-2 failure means
*fix the description.*

Case format, `evals/cases/<skill>.json`: `trigger.positive[]` (≥3 realistic paraphrases users would
type — copying the description games the eval), `trigger.negative[]` (≥2, each naming the `owner`
skill that must outrank this one), `evals[]` (≥1 behavioral with `prompt`, `expected_output`,
`files[]`, `expectations[]`).

**Tier 3 mechanics:** each execution eval runs **in a throwaway git repo** with fixtures committed
as baseline; the grader judges the **full `--output-format stream-json` trace including tool
calls**; traces are **fenced as untrusted data and piped over stdin, never argv** (argv hits the OS
argument-size limit); the executor runs with an explicit permission mode and pre-approved tool list
so evals genuinely edit files rather than being denied and narrating; grader output validates as
JSON before write.

**Pressure cases** are part of Tier 3 and are the Part VIII A3 gate: every discipline skill carries a
**time-pressure**, **sunk-cost**, and **authority-pressure** case, verifying the workflow holds when
the prompt argues for skipping it.

**Tier 4** varies one optional input against a fixed flawed artifact and grades *distribution and
balance*, not count: a vague input should shift almost nothing, a single item should influence
without dominating, contradictory items should be handled gracefully. Every skill of ours taking
`$ARGUMENTS` or an optional steer is untested on this axis.

---

# Part VIII — The autonomy ladder

Neither source defines how a harness *becomes* autonomous. **Evals are the currency that buys
autonomy.** A checkpoint is removed only when measured evidence shows the gate behind it holds
without a human. Absent that, "autonomous" means "unsupervised."

| Tier | Human involvement | Evidence required to enter |
|---|---|---|
| **A0** Assisted | approves every tool call | none — the default |
| **A1** Supervised | approves each phase transition | Tier 1 green; the skill has a Verification section |
| **A2** Checkpointed | approves at planned checkpoints only | Tier 2 rank-1 ≥ floor; no collision ≥75% |
| **A3** Bounded-autonomous | reviews the final artifact; the agent self-gates between | Tier 3 behavioral pass **and** all three pressure cases pass |
| **A4** Delegated | reviews outcomes on a cadence | A3 sustained across N runs + rollback proven + observability alerting live |

- **Tiers are per-workflow, not global.** `/ci-watch` can be A4 while a schema migration stays A1.
- **Promotion requires evidence committed in the repo**, not a judgement call.
- **Demotion is mechanical.** Any `blocked` outcome, any failed pressure case, any
  Definition-of-Done miss, or `followup_review_recommended: true` (§25) drops the workflow one tier
  until re-earned.
- **Irreversible actions never exceed A2** regardless of evidence: production deploys, data
  migrations, public API changes, force-pushes, credential handling. Blast radius caps the tier.
- The tier lives in a **machine-writable** store the gate can update — the workflow's spec
  frontmatter or a `.claude-atomic.yaml` key — never a committed script literal.

The rule that makes this compatible with Appendix A's rejection of paraphrasing orchestrators: **automate
the transport between phases; never automate away the checkpoint.** Removal is governed by this
ladder and nothing else.

> **Current state vs this ladder.** `.claude-atomic.yaml` has all five pipeline autonomy flags
> (`auto_commit`, `auto_push`, `auto_pr`, `auto_ship`, `auto_clean`) set `true` as of commit
> `7390f63`, while none of Tiers 1-4 exist. The repo is therefore operating at roughly A4 with A0
> evidence, and `auto_ship`/`auto_clean` are irreversible actions the ladder caps at A2. This is a
> deliberate, user-accepted risk, recorded here so the gap is visible rather than implicit. Step 18
> reconciles the flags with the ladder.

---

# Steps

Dependency-ordered. Independent and parallel-safe: **1, 2, 6**. Everything else has a stated
predecessor. Accepts are runnable checks; where a body section defines the rule, the check verifies
conformance rather than restating it.

### Step 1 — Close the anti-nesting hole
**Files:** `ai/agents/cicd-audit.md`, `ai/agents/cicd-auto-retry.md`, `ai/agents/cicd-monitor.md`,
`ai/agents/cicd-review.md`, `.claude/settings.json`, `ai/config/claude/settings.base.json`
**Accepts:** each of the four declares an explicit `tools:` allowlist omitting `Agent`;
`env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` is set in both settings files (§11 layer 2);
`bash .claude/hooks/config-integrity.sh` exits 0; both settings files remain byte-identical
(`diff <(jq -S . .claude/settings.json) <(jq -S . ai/config/claude/settings.base.json)`).
*The repo-wide `grep -L '^tools:' ai/agents/*.md` invariant belongs to Step 6's linter, not here —
scoping it to this step makes acceptance order-dependent.*

### Step 2 — Create the References layer
**Files:** `ai/references/definition-of-done.md` (new), `ai/references/README.md` (new), `setup.sh`
**Accepts:** the Definition of Done separates Correctness / Quality / Integration / Documentation /
Ship-readiness and is explicitly distinguished from per-task acceptance criteria;
`test -L .claude/references` passes after `./setup.sh`; ≥2 existing skills reference it instead of
restating a checklist.

### Step 3 — Spec template and path convention *(after 2)*
**Files:** `plans/specs/TEMPLATE.md` (new), `plans/specs/.gitkeep` (new),
`ai/rules/agent-user-global.md:140`, `ai/skills/tmux-orchestrator/SKILL.md:49-50`
**Accepts:** the template contains an `<intent-contract>` region, `## Spec Change Log`, and
`## Review Triage Log` (§6, §24), plus frontmatter fields `status`, `retry_count`,
`doubt_cycle_iteration`, `review_loop_iteration`, `followup_review_recommended`; exactly one spec
convention is documented repo-wide (`grep -rn 'plans/spec\.md' ai/ .claude/` returns only the
updated rule); `active-context.md` is named as a spec location nowhere.
**Decision needed:** per-worker `plans/specs/<label>.md` (recommended, required for concurrent
workers) vs the single `plans/spec.md`.

### Step 4 — Executor agent definition *(after 1, 3)*
**Files:** `ai/agents/executor-implement.md` (new)
**Accepts:** `model: sonnet`; `tools:` allowlist excludes `Agent`; the system prompt carries the §5
init mandate and the §8 three-part prompt contract; `.claude/agents/executor-implement.md` resolves
as a symlink after `./setup.sh`; `config-integrity.sh` exits 0.

### Step 5 — Hooks: dead matchers and missing events *(one step — same JSON block)*
**Files:** `.claude/settings.json`, `ai/config/claude/settings.base.json`,
`.claude/hooks/teammate-quality-gate.sh`
**Accepts:** no `matcher` key on `TaskCreated`/`TaskCompleted`; `TeammateIdle` (no matcher) and
`SubagentStop` wired to `teammate-quality-gate.sh`; `python3 scripts/hook_config_check.py` exits 0
with no `MATCHER_UNSUPPORTED` issues; both settings files byte-identical; a spawned worker's
completion produces a hook log line.

### Step 6 — Tier 1: the skill linter
**Files:** `scripts/lib/skill_lint.py` (new), `scripts/validate_skills.py` (new),
`scripts/skill_lint_baseline.json` (new), `git/hooks/pre-commit`
**Accepts:** checks every `ai/skills/*/SKILL.md` for valid frontmatter, `name` matching the
directory, a `description` carrying both what-it-does and a "Use when" trigger, ≤500 lines, and a
Verification section reachable from `SKILL.md` (present inline **or** in a declared step file, so
§27 decomposition does not fail the lint); also enforces the repo-wide
`grep -L '^tools:' ai/agents/*.md` invariant. **Ratchet semantics:** exits 1 only on violations
absent from `skill_lint_baseline.json`; shrinking the baseline is the only permitted edit to it.
Wired into the existing hook path (`git config core.hooksPath` → `~/.dotfiles/git/hooks`) — the repo
has no pre-commit framework and adding one is out of scope.

### Step 7 — Tier 2: trigger and routing evals *(after 6)*
**Files:** `evals/cases/<skill>.json` (new, seeded for 10 skills), `scripts/run_evals.py` (new),
`evals/collision-baseline.md` (new), `git/hooks/pre-commit`
**Accepts:** stemmed TF-IDF ranking over all skill descriptions; each seeded case has ≥3 positive
and ≥2 `owner`-tagged negative prompts; the runner enforces §Part VII's thresholds (committed
rank-1 floor; 75/50 collision gates) and prints the rank-1 rate; the **current collision report
across all ~73 skills is committed** — expect real hits, that is the finding.

### Step 8 — `/tech-lead` disposition *(decision, blocks 9)*
**Files:** `~/.claude/settings.json:216`, `.claude/settings.json:206`
**Accepts:** either both `"tech-lead": "off"` entries are removed (skillOverrides merge per key —
project scope alone will not re-enable it) and the skill gains the §8 spec handoff and §19
acceptance gate, or this plan records the retirement decision. Either way the outcome is the input
to Step 9's ledger entry.
**Note:** `ai/skills/tech-lead/SKILL.md` is already v2 and already spawns via `Agent` with zero tmux
references. There is no convert-from-tmux work; the gaps are the spec handoff and the gate.

### Step 9 — Skill lifecycle ledger *(after 8)*
**Files:** `ai/skills/REMOVALS.md` (new), `setup.sh`
**Accepts:** every skill `"off"` in `skillOverrides` has a ledger entry naming its state (`retired` /
`superseded-by <skill>` / `disabled-pending <reason>`) plus a one-line rationale; `tech-lead`'s entry
records Step 8's outcome and is not independently decided here; `setup.sh` removes symlinks for
`retired` entries; at least one negative-result entry is recorded where one exists. Built-in skills
(`review`, `simplify`, `code-review`, `run`, `explore`) are explicitly out of ledger scope — the repo
cannot retire them.

### Step 10 — Consolidate review into one lensed skill *(after 7, 9)*
**Files:** `ai/skills/lensed-review/SKILL.md` (new, ≤80 lines),
`ai/skills/lensed-review/lenses.toml` (new), `ai/skills/lensed-review/references/lens-*.md` (new),
`ai/skills/REMOVALS.md`, `evals/cases/`
**Accepts:** `lenses.toml` conforms to §22's schema — parse the TOML and confirm the five keys per
lens, and confirm a lens with an empty `instruction` is skipped in a dry run; each reference file is
≤90 lines and loaded only when its lens runs; findings conform to §20 including the `lens` field and
no `severity` (`grep -c severity` in the schemas → 0); the doubt cycle exists as the adversarial
lens, not a separate harness; superseded skills get shims pinning their current output contract plus
ledger entries; Step 7's collision report shows fewer ≥50% pairs than the committed baseline; Step 7
eval cases for superseded skills are migrated in the same commit.
**Name note:** `lensed-review`, not `review` — `/review` is a Claude Code built-in.

### Step 11 — Customization layer *(after 10)*
**Files:** `scripts/resolve_customization.py` (new), `ai/skills/lensed-review/customize.toml` (new,
pilot), `ai/skills/README.md`, `tests/test_resolve_customization.py` (new)
**Accepts:** resolution order base → `.claude/custom/<skill>.toml` → `.claude/custom/<skill>.user.toml`;
the four §28 merge rules each covered by a unit test, including an **`id`-keyed** array of tables as
well as `code`-keyed; shipped `customize.toml` carries the DO-NOT-EDIT banner; the skill body
specifies the **three-file** fallback (§28) when the resolver fails; a `file:` value pointing at a
missing path is named in the output and skipped, covered by a test.

### Step 12 — Router and core operating behaviors *(after 9, 10)*
**Files:** `ai/skills/manifest.csv` (new), `ai/skills/using-my-skills/SKILL.md` (new),
`.claude/hooks/session-init.sh`, `scripts/validate_skills.py`
**Accepts:** `manifest.csv` carries `skill,phase,preceded-by,followed-by,output-location,outputs`
for every enabled skill; the router's decision tree is **generated from the manifest**, not
hand-written, and regenerating it is idempotent; the linter fails on a manifest row naming a skill
that does not exist or a skill absent from the manifest; the six §30 behaviors are stated as
non-negotiable; the hook injects the router once per session and degrades gracefully without `jq`,
with a regression test asserting the JSON payload shape.

### Step 13 — Skill anatomy and step-file decomposition *(after 6; one step — same files)*
**Files:** `ai/skills/cap/SKILL.md`, `ai/skills/cap/step-0*.md` (new),
`ai/skills/cap/step-oneshot.md` (new), `ai/skills/auto-ship/SKILL.md`,
`ai/skills/investigation-depth/SKILL.md`, `ai/skills/stack-ship/SKILL.md`
**Accepts:** each skill gains a Common Rationalizations table (≥4 rows), a Red Flags list with ≥1
*checkable* signal, and a Verification checklist naming its evidence; for `cap`, `SKILL.md` retains
only frontmatter, conventions, activation, and the pointer to step 1, with the anatomy sections
relocated into the step files and Verification into the final step; each step file carries the §27
anti-shortcut instruction verbatim; `step-oneshot.md` preserves the current single-pass path;
**context cost measured as `wc -l` of the files loaded in a phase-1 invocation (`SKILL.md` +
`step-01`) versus the previous monolithic `SKILL.md`, with both numbers recorded in the commit
body**; Step 6's linter passes on all four.

### Step 14 — Orchestrator skeleton, interactive only *(after 2, 3, 10)*
**Files:** `.claude/workflows/orchestrate.js` (new — first entry in this directory)
**Accepts:** required `export const meta = {name, description, phases}` literal;
`grep -c 'agent(' .claude/workflows/orchestrate.js` ≤ 3 so §3's hard deny does not fire; every
`agent()` call passes `schema` and `label`; every result null-guarded; the reviewer stage **invokes
Step 10's lensed-review skill** rather than embedding review logic, and passes artifact + contract
only (§21); the acceptance stage reads `ai/references/definition-of-done.md` and logs its absence
otherwise; `args.dryRun` stubs `agent()` with schema-shaped fixtures, and
`Workflow({scriptPath, args:{dryRun:true}})` completing with a schema-valid result is the check.
**Implements interactive mode only. Step 15 adds unattended paths — do not build them here.**

### Step 15 — Unattended-safety delta *(after 14)*
**Files:** `.claude/workflows/orchestrate.js`, `ai/skills/cap/references/schemas.md`,
`ai/skills/auto-ship/SKILL.md`
**Accepts:** `schemas.md` `REVIEW_SCHEMA` has `severity` removed from findings and the §20 fields
added (`grep -n severity ai/skills/cap/references/schemas.md` → no finding-level match); triage
implements §23 including the scope-authority rule, verified against a fixture whose only exclusion
basis is the spec's own scope language (must route `bad_spec`, not `defer`); the three §24 counters
persist in spec frontmatter — set `review_loop_iteration` to 6 in a fixture and observe `blocked`
with condition `non-convergence`; `followup_review_recommended` matches a hand-computed fixture;
`grep -nE 'run_in_background|detached' .claude/workflows/orchestrate.js` → no match on unattended
paths; kill a run mid-flight and confirm a terminal status file was written, including the
unresolvable and ambiguous cases.

### Step 16 — Tier 3 and pressure cases *(after 7)*
**Files:** `scripts/run_evals.py` (`--behavioral`), `evals/fixtures/<skill>/`, `evals/results/`
(gitignored), `.gitignore`
**Accepts:** the four Part VII Tier-3 properties hold — throwaway repo with committed fixture
baseline, full-trace grading including tool calls, untrusted-fenced stdin never argv,
JSON-validated grader output — each verified by running one behavioral case; every discipline skill
carries a time-pressure, sunk-cost, and authority-pressure case.

### Step 17 — Tier 4 input sensitivity *(after 10, 16)*
**Files:** `scripts/run_evals.py` (`--sensitivity`), `evals/cases/lensed-review.json`,
`evals/fixtures/lensed-review/`
**Accepts:** `lensed-review`'s optional steer carries a baseline case, a vague-input case, a
single-item case, and a contradictory-input case; grading reports finding *distribution* across
concerns, not only count; the vague-input case is asserted to shift the distribution less than the
specific-input case.

### Step 18 — Reconcile the autonomy ladder with config *(after 15, 16)*
**Files:** `.claude-atomic.yaml`, `ai/rules/agent-user-global.md`,
`.claude/hooks/git-pipeline-gate.sh`
**Accepts:** the five pipeline flags are expressed as A0-A4 tiers; every workflow and pipeline stage
declares its tier in a machine-writable store (not a script literal); promotion requires a committed
green eval run; demotion on any `blocked`, failed pressure case, Definition-of-Done miss, or
`followup_review_recommended: true` is enforced by the gate, not remembered; the gate **asserts**
that `auto_ship` and `auto_clean` cannot exceed A2, failing closed rather than by convention; the
current A4-with-A0-evidence gap noted in Part VIII is either closed or explicitly re-accepted in
writing.

---

# Appendix A — Import ledger

What each source contributed, and what we declined. This is a ledger, not a second explanation —
the mechanisms live in Parts I-VIII.

| From **AS** | Where |
|---|---|
| Five-layer harness model | §26 |
| Skill anatomy; Common Rationalizations; Red Flags; Verification | §27 |
| Progressive disclosure for reference material | §27 |
| Three-tier eval harness; rank-1 floor; collision gates; pressure cases | Part VII |
| Definition of Done as a standing bar | §19 |
| Doubt cycle; ARTIFACT+CONTRACT-only; doubt theater; reviewer-output-is-data | §21, §20 |
| Six core operating behaviors | §30 |
| Subagent-fan-out vs Agent-Teams distinction; `Explore` for research; plugin frontmatter set | §2, §5, §10 |
| RECONCILE classes | merged into §23 |

| From **BM** | Where |
|---|---|
| `<intent-contract>` + Spec Change Log + KEEP instructions | §6 |
| READY FOR DEVELOPMENT, incl. surface-anchored | §7 |
| Unattended control flow; HALT protocol | §13, §15 |
| Coordinator-owned severity; dedupe-then-evaluate-independently | §20 |
| Lens pattern; per-lens zero-findings stance; anti-drift instruction | §22 |
| Five-category triage; scope authority; cascade; tie-breakers | §23 |
| Persisted loop counters; Review Triage Log | §24 |
| `followup_review_recommended` formula | §25 |
| Progressive disclosure for workflow bodies (step files) | §27 |
| Customization layer and merge semantics; `file:` failure behavior | §28 |
| Retirement ledger; shims; aliases; deprecation states; registry columns | §29 |
| Input-sensitivity testing | Part VII Tier 4 |

**Declined, with reasons:**

- **AS's anti-nesting guarantee.** `orchestration-patterns.md:145` asserts *"Subagents cannot spawn
  other subagents (verbatim from the docs)"* and concludes two of its anti-patterns cannot exist "by
  construction." That property was removed in 2.1.219. Their safety model — and
  `doubt-driven-development`'s Loading Constraints, which inherits the premise — rests on a
  guarantee that no longer holds. §11's config controls are the compensating mechanism.
- **AS's ban on scripted orchestration.** Its Anti-pattern C forbids a sequential orchestrator, on
  three grounds: summarization drift between hand-offs, lost human checkpoints, and doubled token
  cost from paraphrase turns. Two dissolve under **artifact-passing** — a `Workflow` stage hands off
  a schema-validated object and a spec hands off a file, so there is no paraphrase step to drift and
  no orchestrator turn to pay for. The catalog was written for *conversational* orchestrators and
  does not consider the `Workflow` primitive; the term appears in it only in its generic sense. The
  checkpoint objection survives and becomes Part VIII's governing constraint.
- **BM's numeric finding quota.** §21.
- **BM personas' identity/communication-style flavor text**, **phase-based directory organization**,
  and **team compositions** — assessed against v6.10.0 and still not worth the cost.

**Reversed from `plans/2026-04-02-bmad-learnings.md`** (which reviewed v6.0.0-Beta.2):

| Prior verdict | Correction |
|---|---|
| "Step-file decomposition — extra files = extra indirection" | The indirection *is* progressive disclosure (§27): one step's tokens instead of five, with `step-oneshot.md` preserving the one-shot path. Beta.2 offered no context-efficiency framing to weigh it against. |
| "Workflow manifest/CSV registry — CSV = two places to update" | `module-help.csv` carries `phase`/`preceded-by`/`followed-by`/`output-location`/`outputs`, which frontmatter cannot express. That relationship data is the substrate Step 12 generates the router from. |

That plan's three *accepted* patterns were never implemented — `ai/knowledge/` does not exist. §28's
customization layer subsumes its config-driven-ownership idea, and `persistent_facts` with `file:`
globs subsumes its knowledge base. Prefer the general mechanism over reopening the three narrow ones.

---

# Appendix B — Open decisions

1. **Spec path** (Step 3) — per-worker `plans/specs/<label>.md` vs single `plans/spec.md`. Blocks
   Step 3; recommended: per-worker, required for concurrent workers.
2. **`/tech-lead`** (Step 8) — re-enable and retrofit, or retire. Blocks Step 9's ledger entry.
3. **Autonomy flags vs ladder** (Step 18) — the repo currently runs all five pipeline flags on with
   no eval tiers built. Accepted as deliberate risk; Step 18 either closes the gap or re-accepts it
   in writing.

---

# Sources

- **RE** — this repo: `.claude/settings.json`, `ai/config/claude/settings.base.json`,
  `.claude/hooks/pre-tool-gate-v2.sh`, `.claude/hooks/config-integrity.sh`,
  `.claude/hooks/task-event-tracker.sh`, `.claude/hooks/teammate-quality-gate.sh`,
  `scripts/hook_config_check.py`, `setup.sh`, `ai/skills/cap/` (`SKILL.md`, `cap-workflow.js`,
  `references/schemas.md`), `ai/rules/agent-user-global.md`,
  `ai/skills/session-artifacts/SKILL.md`, `plans/agent-delegation-patterns.md`,
  `plans/skill-delegation-patterns.md`, `plans/2026-06-12-ai-primitives-upgrade.md`,
  `plans/2026-04-02-bmad-learnings.md`, `.claude-atomic.yaml`
- **AS** — `~/git/agent-skills` @ `7829ffd`: `references/orchestration-patterns.md`,
  `references/definition-of-done.md`, `docs/skill-anatomy.md`, `docs/developer-onboarding.md`,
  `evals/README.md`, `CONTRIBUTING.md`, `skills/using-agent-skills/SKILL.md`,
  `skills/doubt-driven-development/SKILL.md`, `skills/context-engineering/SKILL.md`
- **BM** — `~/git/BMAD-METHOD` @ `bb45db4a` (v6.10.0):
  `src/bmm-skills/4-implementation/bmad-dev-auto/` (`SKILL.md`, `step-04-review.md`,
  `spec-template.md`), `src/bmm-skills/4-implementation/bmad-quick-dev/` (step files),
  `src/core-skills/bmad-review/` (`SKILL.md`, `customize.toml`, `references/lens-*.md`),
  `src/core-skills/bmad-customize/SKILL.md`, `src/core-skills/module-help.csv`,
  `src/core-skills/v6-shims/README.md`, `removals.txt`, `bmad-modules.yaml`,
  `test/adversarial-review-tests/`
- Live Claude Code tool schemas (`Agent`, `Workflow`, `SendMessage`, `Task*`, `Monitor`) and
  `docs.claude.com` sub-agents / hooks / agent-teams / models references — Claude Code 2.1.220
- This plan's own three-lens review (duplication, obsolescence, coherence), 58 findings, run
  2026-07-27 with artifact+contract-only inputs and no reviewer severity authority
