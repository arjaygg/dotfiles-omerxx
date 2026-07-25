# Goal 03 — Agentic Git Lifecycle Pipeline

## Objective

Ship the Claude Code Stop-hook decision layer (`git-pipeline-gate.sh` + `pipeline-status.sh` +
`validate-changeset.sh` + `.claude-atomic.yaml`'s `pipeline:`/`validation:` blocks +
`ai/skills/auto-ship/SKILL.md`) described in `plans/2026-07-25-agentic-git-pipeline.md`, so a
docs-only or code change in this repo can flow commit → PR → CI-wait → merge → sync → cleanup
driven by gate prompts and autonomy-tier config, with zero manual "now do X" instructions once
Step 8's shakedown passes.

## Why

Four git-lifecycle actions (smart-commit, merge-to-main, sync-local, cleanup) each require a fresh
human prompt today even though every execution leg (`commit.sh`, `stack pr`/`stack-ship`/
`stack-sync`/`stack-clean`, `ci-watch`) already exists — there is no decision layer that detects
when a step is due, auto-selects validation, or documents an autonomy contract. The design is
fully reviewed: two independent fresh-agent advisor rounds (hook mechanics, governance gaps) plus
a user-directed D7 cross-agent-portability decision, all folded into
`plans/2026-07-25-agentic-git-pipeline.md`.

## Current state

Design-complete; implementation in progress. `plans/2026-07-25-agentic-git-pipeline.md` (this
worktree, branch `docs/revise-agentic-git-pipeline-plan`) holds the full D1–D7 decision record and
the Step 0–7 breakdown — treat it as the durable design reference this goal summarizes, not
something to duplicate line-by-line. **This goal file now uses the plan doc's Step 0–7 numbering
exactly, so step references here and in the plan can never drift again; all references below are
written as "plan Step N".**

- **Plan Step 0** (Stop-hook contract spike): **done**. Throwaway spike script, nothing committed
  per its own spec; the 4 empirical findings were folded into the plan's Step 0 section on
  2026-07-25.
- **Plan Step 1** (read-only pipeline status aggregator): **done**, committed as `dd5d248`
  (`scripts/ai/pipeline-status.sh` + `scripts/test_pipeline_status.py`, 15 fixture tests, 15/15
  passing — all 7 signals, the D4 multi-worktree-topology case, and both D1b stale/mismatched
  `ci-status.md` variants). The `plans/active-context.md` checkpoint landed as `6f2bcc6`.
  Verified: `bash -n` syntax check, live dogfood run, ~0.197–0.201s warm-repo timing (under the
  200ms budget), zero network calls.
- **Plan Steps 2–7**: **not started**. Awaiting explicit per-step user go-ahead.

`scripts/validate_goals.py` (the validator the `goal-authoring` convention calls for) does not
exist in this repo, so this goal file has not been machine-validated for heading order or index
consistency — only manually checked against the convention.

## Non-goals

- Hawk-style agentic code-review tier for code repos.
- `stack-ship` consuming `ci-status.md` directly instead of re-checking CI itself (declined —
  `stack-ship`'s own CI check stays authoritative).
- Reviving `post-task-fence.sh` (declined permanently — superseded by the new git-state gate).
- Multi-worktree sync fan-out after a main merge.
- `stack-ship`'s own future Phase 3 (audit logging) / Phase 4 (automatic rollback-on-post-merge-CI-
  failure) — this goal's audit trail and rollback runbook do not depend on those landing first.
- New cross-machine locking infrastructure — relying on `gh` remote state + idempotent legs
  instead.
- Cross-agent adapters for Codex, Cursor, or Gemini CLI (D7) — approach is decided (thin per-tool
  adapter over the shared `pipeline-status.sh`/`validate-changeset.sh` engine, with a git-hook
  fallback for agents lacking a turn-level hook), but deferred until one of those tools actually
  drives git in this repo.
- The unrelated stale line in `decisions/0004-lean-ctx-pctx-upstream.md` — tracked separately.

## Steps

Numbering matches `plans/2026-07-25-agentic-git-pipeline.md` `## Steps` exactly (Step 0–7). Each
step's full rationale and D-note corrections live in the plan; this list is a tracking summary.

- **Step 0 — Stop-hook contract spike** — **done** (nothing committed by design). Files: none —
  throwaway scratch script; findings folded into the plan's Step 0 section. Empirically confirmed
  the Stop-hook `{"decision":"block","reason":"..."}` contract, `stop_hook_active` semantics (global
  across hooks, not per-script), and the 2-deny-then-degrade anti-loop prototype.
- **Step 1 — Read-only pipeline status aggregator** — **done** (`dd5d248`). Files:
  `scripts/ai/pipeline-status.sh` (new), `scripts/test_pipeline_status.py` (new). Zero-network,
  <200ms signal detector classifying `split_needed`/`commit_due`/`pr_due`/`ci_pending`/`merge_due`/
  `sync_due`/`cleanup_due` against 15 fixtures, including the D4 multi-worktree topology and both
  D1b stale-`ci-status.md` variants.
- **Step 2 — Validation selection** — **pending**. Files: `scripts/ai/validate-changeset.sh` (new),
  `.claude-atomic.yaml` (edit — new `validation:` block plus a stubbed empty `pipeline: {}` sibling
  block). Routes docs-only/config/source/unknown subsystems per D2 (`.claude/hooks/*.sh` classifies
  as `source`); never blocks on unknown; unknown-subsystem warnings surface visibly for PR-body
  injection; `commit.sh` stays unmodified.
- **Step 3 — Stop-hook gate** — **pending**. Files: `.claude/hooks/git-pipeline-gate.sh` (new),
  `.claude/hooks/stop.sh` (edit — first-deny-wins arbitration after `task-gate.sh`; a rewrite of its
  single-emitter invariant, not purely additive), `hook-config.yaml` (edit — new
  `git-pipeline-gate` level key). No-op unless `core.hooksPath` is the dotfiles path and a
  `pipeline:` block exists; denies with reason + next-action hint; degrades loudly per D1; logs
  every decision per D6.
- **Step 4 — Autonomy tier config** — **pending**. Files: `.claude-atomic.yaml` (edit — fills in
  the `pipeline:` block with `auto_commit`/`auto_push`/`auto_pr`/`auto_ship`/`auto_clean` flags).
  Block absent = full confirm-first; hard-coded always-confirm carve-outs are never overridable by
  any flag combination.
- **Step 5 — Orchestration skill** — **pending**. Files: `ai/skills/auto-ship/SKILL.md` (new).
  Documents the D4 leg sequence, D3 tier checks, D3a identity assertion, first-enable dry-run pass,
  the independent `hook-config.yaml` kill-switch check (D6 point 2), and the rollback runbook.
- **Step 6 — Docs reconciliation** — **pending**. Files: `ai/rules/hyper-atomic-commits.md` (edit
  per D5), `AGENTS.md` (edit if it references the old fence bridge). Removes the dead
  `post-task-fence.sh` bridge claim; describes the live `task-gate.sh` + `git-pipeline-gate.sh`
  chain.
- **Step 7 — End-to-end shakedown** — **pending**. Files: none (validation step only). A docs-only
  change on a scratch branch flows edit → committed → PR'd → CI-wait (background `Monitor` per D4a)
  → merged → synced → cleaned up, driven entirely by gate prompts; explicitly multi-turn/
  multi-session.

Ordering note (from the plan's Step 3/4 note): Step 2 must stub a minimal `pipeline: {}` in
`.claude-atomic.yaml` so Step 3's opt-in no-op check has something concrete to test; Step 4 then
fills in the real flag schema on the same key rather than introducing it fresh.

## Acceptance criteria

Each bullet is derived from the corresponding step's `**Accepts:**` line in
`plans/2026-07-25-agentic-git-pipeline.md`. `[x]` = verified satisfied; `[ ]` = pending.

Plan Step 0:
- [x] Stop hook returning `{"decision":"block","reason":"..."}` empirically confirmed to keep the
  turn alive; `stop_hook_active` semantics confirmed; the two-stage deny-then-degrade prototype
  validated the D1 anti-loop counter design. Findings recorded in the plan's Step 0 section.

Plan Step 1:
- [x] `scripts/ai/pipeline-status.sh` classifies all 7 signals (`split_needed`, `commit_due`,
  `pr_due`, `ci_pending`, `merge_due`, `sync_due`, `cleanup_due`) correctly against fixtures,
  including the D4 multi-worktree-topology fixture and both D1b stale/mismatched `ci-status.md`
  variants (`scripts/test_pipeline_status.py`, 15/15 passing at `dd5d248`).
- [x] Zero network calls; <200ms on a warm repo (measured ~0.197–0.201s); emits one signal (or
  none) plus a one-line reason.

Plan Step 2:
- [ ] `scripts/ai/validate-changeset.sh` routes docs-only/config/source/unknown staged changesets
  per D2, with `.claude/hooks/*.sh` classified as `source`; never blocks on an unrecognized
  subsystem; unknown-subsystem warnings are surfaced in a form plan Step 5's PR-creation leg can
  inject into the PR body; `commit.sh` unmodified.
- [ ] `.claude-atomic.yaml` gains the `validation:` block plus the stubbed empty `pipeline: {}`
  sibling block that unblocks plan Step 3's opt-in check.

Plan Step 3:
- [ ] `.claude/hooks/git-pipeline-gate.sh` is built against the plan Step 0 spike's confirmed
  Stop-hook contract; no-ops when `core.hooksPath` isn't the dotfiles path or no `pipeline:` block
  exists; denies with a clear reason + next-action hint on a real due-signal.
- [ ] Gate never issues a 3rd consecutive deny for the same stage in one session (2 denies/stage
  plus the D1 global per-session cap); a real degrade emits both the stderr message and an
  `osascript` notification.

Plan Step 4:
- [ ] `pipeline:` block absent = full confirm-first; each of `auto_commit`/`auto_push`/`auto_pr`/
  `auto_ship`/`auto_clean` independently gates exactly the leg named in D3.
- [ ] All always-confirm carve-outs are present and unconditional — not overridable by any flag
  combination: force-push outside `stack-sync`'s reviewed pattern, discarding work to resolve
  `blocked`/`overgrown`, `stack clean --force` on a dirty worktree, `gh pr merge --admin` (never
  used at all), deleting a genuinely-unmerged (non-squash) branch, `ci-watch`'s auto-deploy
  trigger, multi-branch `stack-ship`, and any pipeline self-edit to `.claude-atomic.yaml`/
  `hook-config.yaml`/`.claude/hooks/*`.

Plan Step 5:
- [ ] `ai/skills/auto-ship/SKILL.md` documents the full D4 leg sequence, the D3 tier checks, and
  the D3a `gh auth status` identity assertion before any Tier-1/2 action; requires a dry-run/
  explain-only pass the first time a repo newly enables any Tier-1/2 flag; independently checks
  `hook-config.yaml`'s `git-pipeline-gate` level and no-ops if `off` (not solely reliant on the
  Stop hook); includes the D6 rollback runbook as a documented section.

Plan Step 6:
- [ ] No remaining tracked-doc reference to `post-task-fence.sh` as a live mechanism; the live
  fence chain (`task-gate.sh` + `git-pipeline-gate.sh`) is accurately described in
  `ai/rules/hyper-atomic-commits.md` (and `AGENTS.md` if applicable).

Plan Step 7:
- [ ] The shakedown completes on a real scratch branch with zero manual "now do X" prompts from
  the user, end to end (commit through cleanup), across however many turns/sessions the CI wait
  actually takes (the `Monitor`-bridged CI-wait leg may span a session boundary per D4a).

Cross-cutting (spans plan Steps 3–7):
- [ ] Every gate decision (deny/degrade/tier-gated auto-action) has a corresponding entry in
  `.claude/pipeline-log.jsonl`.

## Evidence to update

- `scripts/ai/pipeline-status.sh`, `scripts/ai/validate-changeset.sh` (new)
- `.claude/hooks/git-pipeline-gate.sh` (new), `.claude/hooks/stop.sh` (edit)
- `hook-config.yaml` (new `git-pipeline-gate` level key)
- `.claude-atomic.yaml` (new `pipeline:`/`validation:` blocks)
- `ai/skills/auto-ship/SKILL.md` (new)
- `ai/rules/hyper-atomic-commits.md`, `AGENTS.md` (docs reconciliation)
- `.git/pipeline-state.json`, `.claude/pipeline-log.jsonl` (new, gitignored, runtime evidence —
  durable per-branch state and audit trail respectively)
- `plans/2026-07-25-agentic-git-pipeline.md` — source design doc; update its D-notes if a step's
  implementation deviates from what is recorded there.
- `plans/progress.md` / `plans/decisions.md` — chronological step completion and any in-session
  decisions.

## Stop and ask if

- Before starting each remaining step (plan Steps 2–7) — the plan's status is "Awaiting user
  go-ahead per step"; do not begin any step without explicit go-ahead for that specific step.
  Authorization for one step never extends to the next.
- Before beginning plan Step N+1 when plan Step N's Accepts are not met.
- Before flipping any `.claude-atomic.yaml` `pipeline:` flag beyond Tier 0, or any
  `hook-config.yaml` level change, without explicit user instruction.
- Any of the hard-coded always-confirm cases fire (see Acceptance criteria) — these are never
  satisfied by a flag, only by direct user confirmation in the moment.
- `gh auth status` resolves to anything other than the personal `arjaygg` account before a
  Tier-1/2 action (D3a) — fall back to confirm-first, do not proceed.
- A non-fast-forward `git pull --ff-only` failure during the sync leg (main diverged for reasons
  unrelated to this pipeline) — degrade to confirm-first, never force or rebase automatically.
- `ci-status.md`'s `(branch, head_sha)` does not match the current worktree's actual HEAD — treat
  as `ci_pending`/unknown, never as green, and surface rather than silently proceeding.
- Considering building Codex/Cursor/Gemini CLI adapters (D7) before one of those tools is actually
  used to drive git in this repo — that is explicit follow-up scope, not part of this goal.
