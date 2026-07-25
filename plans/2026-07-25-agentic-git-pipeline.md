# Agentic Git Lifecycle Pipeline

**Author:** Fable plan agent (`agentic-git-pipeline-plan`), briefed and commissioned 2026-07-25.
**Revised:** 2026-07-25, folding two independent Fable advisor review rounds — round 1 (hook
mechanics: `advisor-review-git-pipeline-plan`) and round 2 (governance gaps:
`advisor-review-governance-gaps`). Isolated to branch `docs/revise-agentic-git-pipeline-plan`.
**Status:** Plan only — no implementation yet. Awaiting user go-ahead per step.

## Problem Statement

Four git lifecycle actions (smart-commit, merge-to-main, sync-local, cleanup) each require a
fresh human prompt today. Every *execution* leg already exists in this repo
(`scripts/ai/commit.sh`, `stack pr`/`stack-ship`/`stack-sync`/`stack-clean`, `ci-watch`), but there
is no *decision* layer: nothing detects "a commit/PR/merge/sync/cleanup is due right now," nothing
auto-selects the right validation for the kind of change being made, and there is no documented
autonomy contract for how far the harness may go without asking.

## Key Design Decisions

**D1 — Trigger.** A new sibling Stop sub-hook `.claude/hooks/git-pipeline-gate.sh` (not an
extension of `task-gate.sh`, not `/loop`, not `TaskCompleted`-driven), running *after*
`task-gate.sh` in `stop.sh`'s chain, with first-deny-wins arbitration between the two gates.

> **Correction (round 1, blocker):** the original text claimed this "reuses the proven deny+reason
> pattern that `task-gate.sh` already uses." That premise is **false**. `task-gate.sh` emits the
> **PreToolUse** shape (`{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":...}}`),
> which is not a valid Stop-hook blocking response. The actual Stop-hook contract is a distinct,
> top-level shape: `{"decision":"block","reason":"..."}`, with **no `additionalContext` support**
> (unlike PostToolUse). Additionally, `task-gate.sh`'s own level in `hook-config.yaml` is currently
> `warn`, so its deny branch has likely never fired in production — there is no proven precedent to
> reuse here, only an unexercised code path. `git-pipeline-gate.sh` must be built and tested against
> the correct Stop-hook shape from scratch; see **Step 0** below.

**Hard constraint: zero network calls.** It only reads local git state, `atomic-status.sh`'s
output, `plans/ci-status.md` (written by `ci-watch`), and a state file split per round 1's
finding (see D1a). Signal → stage map: `split_needed`, `commit_due`, `pr_due`, `ci_pending`
(warn-only, never blocks), `merge_due`, `sync_due`, `cleanup_due`.

**Anti-loop (revised):** max 2 denies per stage per session, then degrade to warn-only for the
rest of the session **for that stage**, with a global per-session deny cap across all stages
combined to prevent one runaway signal from exhausting turns via stage-hopping. Re-deny after
degrade is permitted only if the underlying stage actually changes (e.g. `commit_due` degrades,
then later `merge_due` fires — that's a new stage, fresh budget). Degrade-to-warn must **escalate
loudly**, not fail silently: emit to stderr and fire an `osascript` notification (reusing
`ci-watch`'s exact fire-and-forget pattern, `ai/skills/ci-watch/SKILL.md:92,97,109`) so the user
knows the gate stopped enforcing for that stage.

The gate is a no-op unless `core.hooksPath` points at the dotfiles hooks path **and**
`.claude-atomic.yaml` has a `pipeline:` block — i.e. opt-in per repo.

**D1a — State file split (round 1, should-fix).** The original single
`/tmp/.claude-git-pipeline-$CLAUDE_SESSION_ID` file conflated two different lifetimes. Split into:
- **Ephemeral, per-session** (`/tmp/.claude-git-pipeline-$CLAUDE_SESSION_ID`): deny counters,
  degrade flags — fine to lose on reboot.
- **Durable, per-branch** (`.git/pipeline-state.json`, gitignored, lives in the repo's `.git/` so
  it survives session restarts and is worktree-local): last-known stage, last network-action
  timestamp, last `ci-status.md` branch+SHA correlation (see D1b). Anything a *different* Claude
  session on the same branch would need to reconstruct state without replaying network calls goes
  here, not in `/tmp`.

**D1b — `ci-status.md` staleness (round 1, blocker).** `ci-status.md` is currently a single
global file with no branch/SHA correlation, so a stale read from a previous branch's CI run could
falsely signal `merge_due` on a different branch. Fix: `ci-watch` must key its written status to
`(branch, head_sha)`, and `git-pipeline-gate.sh` must reject any `ci-status.md` entry whose
`(branch, head_sha)` doesn't match the current worktree's actual `git rev-parse HEAD` — treat a
mismatch as `ci_pending` (unknown), never as green.

**D2 — Validation selection.** New deterministic script `scripts/ai/validate-changeset.sh`, keyed
off `atomic-status.sh`'s existing subsystem classification, mapped via a new `validation:` block in
`.claude-atomic.yaml`:
- docs-only → no extra validation
- config → `jq`/YAML parse, `bash -n`
- source → `shellcheck` (this repo) or cap's language-probe → scoped test runner (code repos)
- unknown → warn + pass (never block on an unrecognized subsystem)

> **Correction (round 1, should-fix):** `.claude/hooks/*.sh` must be explicitly classified as
> `source` (shellcheck-eligible), not fall through to `unknown` — hook scripts are exactly the kind
> of change where silent-pass-on-unknown would be most dangerous. Any unknown-subsystem warning
> must surface **visibly** (e.g. injected into the PR body via `stack pr`, not just a log line) so
> a human reviewer sees it even in a Tier-1/2 auto-PR flow.

`commit.sh` itself stays untouched — validation is a separate pre-commit leg, not folded into the
hygiene gate. An agentic/hawk-style review tier for code repos is explicitly deferred as a
follow-up, not part of this plan.

**D3 — Autonomy tiers.** Durable in `.claude-atomic.yaml`'s `pipeline:` block. Absence of the block
means full confirm-first (also the safe default for a repo that hasn't opted in).
- **Tier 0** (block present, no extra flags): local commit via `commit.sh` on a non-main branch
  once ready+validated. On `main`, always `stack create` first — hard refusal to commit on `main`,
  not just a warn.
- **Tier 1** (`auto_push`, `auto_pr` flags): push + `stack pr` + `ci-watch` (backgrounded).
- **Tier 2** (`auto_ship`, `auto_clean` flags): `stack-ship` merge, main fast-forward sync,
  `stack-clean`. Tier-2 actions fire an `osascript` notification on completion (round 2,
  should-fix) — reusing `ci-watch`'s existing pattern — since these are the least-reversible legs
  and the user should be pinged even if not actively watching the session.

**Always-confirm regardless of flags** (extended per both review rounds):
- Any force-push outside `stack-sync`'s already-reviewed `--force-with-lease` pattern.
- Discarding work to resolve a `blocked`/`overgrown` state.
- `stack clean --force` on a dirty worktree.
- `gh pr merge --admin` — **the pipeline never uses `--admin`**.
- *(round 1)* Deleting an unmerged branch — detect via squash-merge (branch tip not an ancestor of
  `main` but content-identical) vs. genuinely-unmerged, and refuse cleanup on the latter without
  confirmation, since `stack-clean`'s ancestor check alone under-detects squash-merged branches.
- *(round 1)* `ci-watch`'s auto-deploy-on-green (`gh workflow run deploy-dev.yml`) — this pipeline's
  `auto_pr`/`ci_pending` signal must never be read as blanket authorization for `ci-watch`'s
  separate deploy trigger; that authorization (if any) is out of scope for this plan and stays
  gated by whatever `ci-watch` itself requires today.
- *(round 1)* `stack-ship`'s atomic multi-branch merge semantics (i.e. shipping more than one
  stacked branch in one pipeline run) — single-branch ship only; multi-branch stack-ship always
  confirms.
- *(round 2)* Any edit the pipeline itself would make to `.claude-atomic.yaml`,
  `hook-config.yaml`, or `.claude/hooks/*` — the pipeline must never self-escalate its own
  autonomy tier or gate level; only a human edit to these files can raise autonomy.

The merge leg uses **`stack-ship`, not `stack-auto-pr-merge`**, because `stack-ship` is CI-gated
and audit-logged (`.stack-ship/log.jsonl`) with no admin bypass; `stack-auto-pr-merge` stays
exactly as-is for its own standalone use and serves only as precedent that durable
pre-authorization (a flag in a tracked config file) is an accepted way to satisfy "confirm before
risky actions."

**D3a — Identity assertion (round 2, should-fix).** Before any Tier-1/2 action, the pipeline must
assert `gh auth status` resolves to the personal `arjaygg` account (not an EMU/work account —
per this repo's standing convention), and log the resolved actor identity into the audit trail
(D6). Refuse and fall back to confirm-first if the wrong account is active.

**D4 — Chaining.** `validate-changeset.sh` → `commit.sh` → `stack pr` → `ci-watch` (background) →
`stack-ship` → `git checkout main && git pull --ff-only` → `stack-clean`.

> **Correction (round 1, blocker — worktree safety):** the sync leg (`git checkout main && git pull
> --ff-only`) as written assumes a single shared checkout. In this repo's actual topology, `main`
> and each branch typically live in **separate worktrees**. The leg must instead operate on
> whichever worktree currently has `main` checked out (resolve via `git worktree list`), and must
> carve out the case where local `main` has diverged from `origin/main` for reasons unrelated to
> this pipeline (e.g. another concurrent merge) — a non-fast-forward `git pull --ff-only` failure
> here must degrade to confirm-first, never force or rebase automatically.

Flagged seam (intentional, not a gap to build): `stack-ship` re-checks CI via `gh` itself at merge
time as the authoritative final gate, while `ci-status.md` only serves as the *trigger* that tells
the Stop hook a merge may now be due.

**D4a — CI-wait bridge (round 1, blocker).** The original plan had no mechanism for the *long-lived
wait* between "PR opened" and "CI finished" — a single turn's Stop hook can't block for minutes.
Fix: this wait is bridged by a **`Monitor` watching `plans/ci-status.md` for the
branch+SHA-keyed entry to flip to green/red** (per D1b), started immediately after `stack pr`
in the same turn that opens the PR, per the standing "Background Monitoring" convention
(`ai/rules/agent-user-global.md` § Background Monitoring). `git-pipeline-gate.sh` itself never
polls or waits — it only reads whatever `ci-status.md` currently says. This also means Step 7's
end-to-end shakedown is inherently **multi-turn, not single-turn** — rescoped accordingly (see
Step 7 below).

**D5 — Stale doc fix (in scope).** `ai/rules/hyper-atomic-commits.md` currently documents a
`TodoWrite → post-task-fence.sh` commit-fence bridge that is dead: `post-task-fence.sh` lives only
under `.claude/hooks/archive/` and is absent from `settings.json`'s hooks map. Fix the doc to
describe the fences that are actually live today (`task-gate.sh`, and the new
`git-pipeline-gate.sh` once shipped). Do **not** revive the archived hook — the new git-state-based
gate is a strictly stronger signal than the task-list-based one it would have provided.

**D6 — Governance (round 2, new section).** Four cross-cutting mechanisms the original plan
under-specified, verified against actual repo precedent rather than invented fresh:

1. **Audit trail.** Every gate decision (deny, degrade, tier-gated auto-action) is appended to a
   durable, append-only JSONL log — not `/tmp` — modeled on `stack-ship`'s existing
   `.stack-ship/log.jsonl` schema (timestamp, actor, action, hashes). Proposed path:
   `.claude/pipeline-log.jsonl` at repo root (tracked in `.gitignore`, not in git history, but
   durable across sessions unlike `/tmp`).
2. **Kill switch scope.** `hook-config.yaml`'s existing `git-pipeline-gate` level key (warn/block/
   off — same convention as every other gate in this file, no new mechanism needed) must be
   checked in **two** places, not one: the Stop-hook trigger itself (already covered by D1), *and*
   the `auto-ship` skill's own entry point (Step 5) before it takes any Tier-1/2 action. If only
   the hook checks it, setting the key to `off` stops new *prompts* but does not stop a
   already-invoked `auto-ship` skill run from completing — the skill must independently no-op when
   the level is `off`.
3. **Rollback runbook.** Not new tooling — a documented runbook section in the new `ai/skills/
   auto-ship/SKILL.md` (Step 5) describing how to recover using **existing** primitives, keyed off
   the audit log's hash fields: revert the merge commit (`git revert -m 1 <sha>`), re-open the
   branch from `.stack-ship/log.jsonl`'s recorded pre-merge SHA, or re-run `stack-clean` reversal
   (`git worktree add` back from the recorded branch name). `stack-ship`'s own rollback-on-
   post-merge-CI-failure is separately spec'd as future Phase 4 work in its RFC and is **not** a
   dependency of this plan — the runbook is manual-but-documented, not automatic.
4. **Concurrent/cross-machine sessions.** `hook-config.yaml`'s `duplicate-session-check: block`
   already covers same-machine collisions. Cross-machine has no existing lock mechanism, and this
   plan **does not add one** — instead, every Tier-1/2 leg treats `gh`'s remote state (PR status,
   merge status, branch existence) as the sole source of truth and is written idempotently (e.g.
   "push if local is ahead of the tracked remote ref" rather than "push unconditionally"), so a
   second session on another machine either no-ops safely or gets a clear `gh`-reported conflict
   to surface as a confirm-first prompt, rather than racing.

**D7 — Cross-agent portability (new section, user-directed 2026-07-25 follow-on to the two advisor
rounds).** Steps 0–7 below build the Claude Code implementation only: `git-pipeline-gate.sh` is a
Claude Code **Stop hook**, and the CI-wait bridge (D4a) relies on Claude Code's `Monitor`
primitive. Neither exists in Codex, Cursor, or Gemini CLI today. Rather than rewrite the decision
layer per tool, the chosen approach is a **thin adapter per agent** over one shared, agent-neutral
engine:

- **The engine is already agent-neutral and stays the only shared piece.** `pipeline-status.sh`
  (signal detection) and `validate-changeset.sh` (validation routing) have zero Claude Code
  dependency today — plain bash, callable by any tool or a human directly.
- **Each coding agent gets its own adapter**, not a fork of the engine: the adapter invokes
  `pipeline-status.sh` and translates the returned signal into whatever blocking/warning primitive
  that agent natively exposes. `git-pipeline-gate.sh` (D1) *is* the reference adapter — the Claude
  Code Stop-hook implementation of this pattern — not a special case to generalize away from.
- **Lowest-common-denominator fallback.** For any agent with no turn-level hook mechanism at all,
  its adapter degrades to a git-level trigger (`pre-push`/`post-commit` under `core.hooksPath`),
  which fires for any tool's commits, Claude Code included. This is strictly weaker — it can only
  stop/warn at the git-operation boundary, not steer an agent's own mid-turn decision — so it is
  the floor for agents without something richer, not the target for all agents.
- **Open question, deliberately not resolved here:** `.claude/pipeline-log.jsonl` (D6) is
  namespaced under `.claude/`, which becomes misleading once a non-Claude adapter also writes to
  it. Revisit the path (e.g. `.git/pipeline-log.jsonl`) if/when a second adapter actually ships —
  not renamed preemptively, for the same "don't build for a hypothetical future" reasoning already
  applied in D6 point 4.
- **Scope.** Researching and building adapters for Codex, Cursor, or Gemini CLI is explicit
  follow-up work (see below), triggered only once one of those tools is actually used to drive git
  in this repo. Steps 0–7 ship the Claude Code adapter only.

## Steps

### Step 0 — Stop-hook contract spike (new, round 1 blocker)
**Files:** none committed — throwaway scratch script under a session-scratch path, findings folded
back into this doc.
**Accepts:** Confirms empirically (not just by reading docs) that a Stop hook returning
`{"decision":"block","reason":"..."}` actually keeps the turn alive in this Claude Code version;
confirms `stop_hook_active` is set true on the resulting re-invocation; prototypes a minimal
two-stage deny chain (stage A denies once, stage B denies once on the next Stop, then both
degrade) to validate the anti-loop counter design in D1 before Step 3 is built on unverified
assumptions. If flipping `task-gate.sh`'s level to `block` temporarily (in a scratch/local config
only, reverted after) is used to observe real deny behavior, do so only in this isolated worktree.

### Step 1 — Read-only pipeline status aggregator
**Files:** `scripts/ai/pipeline-status.sh` (new)
**Accepts:** Zero network calls; completes in <200ms on a warm repo; correctly classifies all 7
fixture states (`split_needed`, `commit_due`, `pr_due`, `ci_pending`, `merge_due`, `sync_due`,
`cleanup_due`) against hand-built git/worktree fixtures, including a worktree-topology fixture
(main and branch in separate worktrees, per D4) and a stale/mismatched `ci-status.md` fixture (per
D1b); emits one of those signals (or none) plus a one-line reason.

### Step 2 — Validation selection
**Files:** `scripts/ai/validate-changeset.sh` (new), `.claude-atomic.yaml` (new `validation:` block
— stubbed here with an empty/no-op `pipeline:` sibling block to unblock Step 3's dependency, see
Step 3/4 ordering note below)
**Accepts:** Given a staged changeset, correctly routes docs-only/config/source/unknown subsystems
per D2, with `.claude/hooks/*.sh` routing as `source`; never blocks on an unrecognized subsystem;
unknown-subsystem warnings are surfaced in a way Step 5's PR-creation leg can inject into the PR
body; `commit.sh` unmodified.

### Step 3 — Stop-hook gate
**Files:** `.claude/hooks/git-pipeline-gate.sh` (new), `.claude/hooks/stop.sh` (edit — arbitration
ordering after `task-gate.sh`; note this is a **rewrite** of `stop.sh`'s previous single-emitter
pass-through invariant, not a purely additive extension, since two hooks may now each want to
block in the same invocation), `hook-config.yaml` (new `git-pipeline-gate` level key)
**Accepts:** Built against the Step 0 spike's confirmed Stop-hook contract; no-op when
`core.hooksPath` isn't the dotfiles path or no `pipeline:` block exists; denies with a clear reason
+ next-action hint on a real due-signal; degrades to warn after 2 denies per stage per session
(plus the global per-session cap from D1); never issues a 3rd consecutive deny for the same stage;
degrade emits the stderr + osascript notification from D1; writes every decision to the D6 audit
log.

> **Step 3/4 ordering note (round 1, should-fix):** Step 3 depends on a `pipeline:` block existing
> in `.claude-atomic.yaml` (for the opt-in no-op check) before Step 4 formally defines that block's
> full schema. Resolve by having Step 2 stub a minimal `pipeline: {}` (present-but-empty = opt-in
> with all flags off) so Step 3 has something concrete to check; Step 4 then fills in the flag
> schema on top of the same key rather than introducing it fresh.

### Step 4 — Autonomy tier config
**Files:** `.claude-atomic.yaml` (fills in the `pipeline:` block stubbed in Step 2 with:
`auto_commit`, `auto_push`, `auto_pr`, `auto_ship`, `auto_clean` flags)
**Accepts:** Block absent = full confirm-first; each flag independently gates exactly the leg named
in D3; hard-coded always-confirm cases (force-push outside stack-sync, `--force`/`--admin`, dirty
worktree clean, unmerged-branch deletion, ci-watch auto-deploy, multi-branch stack-ship,
self-escalating edits to `.claude-atomic.yaml`/`hook-config.yaml`/`.claude/hooks/*`) are not
overridable by any flag combination.

### Step 5 — Orchestration skill
**Files:** `ai/skills/auto-ship/SKILL.md` (new)
**Accepts:** Documents the full leg sequence from D4, the tier checks from D3, the D3a identity
assertion before any Tier-1/2 action, requires a dry-run/explain-only pass the first time a repo
newly enables any tier-1/2 flag; independently checks `hook-config.yaml`'s `git-pipeline-gate`
level and no-ops if `off` (D6 point 2 — not solely reliant on the Stop hook); includes the D6
rollback runbook as a documented section.

### Step 6 — Docs reconciliation
**Files:** `ai/rules/hyper-atomic-commits.md` (edit per D5), `AGENTS.md` (edit if it references the
old fence bridge)
**Accepts:** No remaining reference to `post-task-fence.sh` as a live mechanism anywhere in tracked
docs; the live fence chain (`task-gate.sh` + `git-pipeline-gate.sh`) is accurately described.

### Step 7 — End-to-end shakedown (rescoped, round 1)
**Files:** none (validation step only)
**Accepts:** A docs-only change on a scratch branch in this repo goes from edit → committed → PR'd
→ (background `Monitor` bridges the CI wait per D4a, potentially across a session boundary) →
merged → synced → cleaned up driven entirely by gate prompts, with zero manual "now do X"
instructions from the user. Explicitly **not** required to complete within a single turn or single
session — the CI-wait leg is allowed to span a `Monitor`-driven resumption.

## Explicit Follow-ups (out of scope for this plan)

- Hawk-style agentic code review tier for code repos (D2 follow-up).
- Having `stack-ship` consume `ci-status.md` directly instead of re-checking CI itself (declined —
  `stack-ship`'s own CI check stays authoritative).
- Reviving `post-task-fence.sh` (declined permanently — superseded by D1's git-state gate).
- Multi-worktree sync fan-out after a main merge.
- `stack-ship`'s own future Phase 3 (full audit logging) and Phase 4 (automatic rollback-on-
  post-merge-CI-failure) work, per its RFC — this plan's D6 audit trail and rollback runbook are
  independent of and do not require those phases to land first.
- New cross-machine locking infrastructure (D6 point 4 — deliberately not building this; relying on
  `gh` remote state + idempotent legs instead).
- The unrelated pre-existing stale line in `decisions/0004-lean-ctx-pctx-upstream.md` (tracked
  separately, not part of this pipeline work).
- Cross-agent adapters for Codex, Cursor, or Gemini CLI (D7) — approach is decided (thin per-tool
  adapter over the shared `pipeline-status.sh`/`validate-changeset.sh` engine, with a git-hook
  fallback for agents lacking a turn-level hook mechanism), but deferred until one of those tools
  is actually used to drive git in this repo.

## Critical Files

- `.claude/hooks/git-pipeline-gate.sh` (new)
- `.claude/hooks/stop.sh` (edit — rewrite of single-emitter invariant)
- `scripts/ai/pipeline-status.sh` (new)
- `scripts/ai/validate-changeset.sh` (new)
- `ai/skills/auto-ship/SKILL.md` (new — includes rollback runbook)
- `.claude-atomic.yaml` (new/edit — `pipeline:` + `validation:` blocks)
- `hook-config.yaml` (edit — new `git-pipeline-gate` level key)
- `ai/rules/hyper-atomic-commits.md` (edit)
- `.git/pipeline-state.json` (new, gitignored, durable per-branch state — D1a)
- `.claude/pipeline-log.jsonl` (new, gitignored, durable audit trail — D6)

## Review Provenance

- **Round 1** (`advisor-review-git-pipeline-plan`, fresh Fable agent): mechanical feasibility of
  Stop-hook chaining, autonomy-tier carve-outs, validation coverage, step sequencing,
  underspecification. Findings folded: D1 correction, D1a, D1b, D4 correction, D4a, D2 correction,
  3 additional always-confirm carve-outs, Step 0 (new), Step 3/4 ordering note, Step 7 rescope,
  loud-degrade requirement, unknown-subsystem visibility requirement.
- **Round 2** (`advisor-review-governance-gaps`, fresh Fable agent): audit trail, Tier-2
  notification, kill-switch scope, rollback runbook, self-escalation carve-out, concurrent-session
  handling, identity assertion — verified against actual repo mechanisms
  (`hook-config.yaml` levels, `.stack-ship/log.jsonl`, `ci-watch` notification pattern,
  `.claude-atomic.yaml` precedent) rather than invented fresh. Findings folded: D6 (new section),
  D3a (new), Tier-2 notification in D3, self-escalation carve-out in D3, Step 5/Step 4 accepts
  updates.
