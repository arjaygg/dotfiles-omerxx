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

Design-complete. `plans/2026-07-25-agentic-git-pipeline.md` (this worktree, branch
`docs/revise-agentic-git-pipeline-plan`) holds the full D1–D7 decision record and Step 0–7
breakdown — treat it as the durable design reference this goal summarizes, not something to
duplicate line-by-line. Step 0 (Stop-hook contract spike) is complete: findings folded into the
plan's Step 0 section (2026-07-25); the spike script was throwaway and has been deleted per its own
spec, nothing from it is committed. Awaiting explicit user go-ahead before starting Step 1.

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

1. **Stop-hook contract spike** — throwaway scratch script, nothing committed. Confirm
   empirically that a Stop hook returning `{"decision":"block","reason":"..."}` keeps the turn
   alive and sets `stop_hook_active` on re-invocation; prototype the 2-deny-then-degrade anti-loop
   counter.
2. **Read-only pipeline status aggregator** — new `scripts/ai/pipeline-status.sh`. Zero network
   calls, <200ms on a warm repo, classifies all 7 signals (`split_needed`/`commit_due`/`pr_due`/
   `ci_pending`/`merge_due`/`sync_due`/`cleanup_due`) against fixtures including a multi-worktree
   topology and a stale/mismatched `ci-status.md`.
3. **Validation selection** — new `scripts/ai/validate-changeset.sh`, plus a stubbed empty
   `pipeline: {}` sibling block in `.claude-atomic.yaml` to unblock Step 4. Routes docs/config/
   source/unknown subsystems (`.claude/hooks/*.sh` must classify as `source`); never blocks on
   unknown; unknown-subsystem warnings surface visibly (e.g. in the PR body).
4. **Stop-hook gate** — new `.claude/hooks/git-pipeline-gate.sh`; edit `.claude/hooks/stop.sh`
   (first-deny-wins arbitration with `task-gate.sh` — a rewrite of its single-emitter invariant,
   not purely additive); new `git-pipeline-gate` level key in `hook-config.yaml`. No-op unless
   `core.hooksPath` is the dotfiles path and a `pipeline:` block exists; denies with a reason plus
   next-action hint; degrades to warn after 2 denies/stage/session (plus a global per-session cap)
   with a loud stderr + `osascript` notification; writes every decision to the audit log.
5. **Autonomy tier config** — fill in `.claude-atomic.yaml`'s `pipeline:` block: `auto_commit`/
   `auto_push`/`auto_pr`/`auto_ship`/`auto_clean` flags. Block absent = full confirm-first.
   Hard-coded always-confirm cases are never overridable by any flag combination (see Acceptance
   criteria and Stop-and-ask-if below).
6. **Orchestration skill** — new `ai/skills/auto-ship/SKILL.md`. Documents the full leg sequence
   (`validate-changeset.sh` → `commit.sh` → `stack pr` → `ci-watch` background → `stack-ship` →
   main sync → `stack-clean`), the D3a `gh auth status` identity assertion before any Tier-1/2
   action, a required dry-run/explain-only first pass per repo, an independent check of
   `hook-config.yaml`'s `git-pipeline-gate` level (no-ops if `off`, not solely reliant on the Stop
   hook), and the rollback runbook.
7. **Docs reconciliation** — edit `ai/rules/hyper-atomic-commits.md` (remove the dead
   `post-task-fence.sh` fence-bridge claim, describe the live `task-gate.sh` +
   `git-pipeline-gate.sh` chain instead) and `AGENTS.md` if it references the old bridge.
8. **End-to-end shakedown** — no new files. A docs-only change on a scratch branch flows edit →
   committed → PR'd → (background `Monitor` bridges the CI wait, potentially across a session
   boundary) → merged → synced → cleaned up, driven entirely by gate prompts, zero manual
   "now do X" instructions. Explicitly allowed to span multiple turns/sessions.

## Acceptance criteria

- All 7 fixture states in Step 2 classify correctly; the worktree-topology and stale-`ci-status.md`
  fixtures pass.
- Step 4's gate never issues a 3rd consecutive deny for the same stage in one session; a real
  degrade emits both the stderr message and an `osascript` notification.
- Step 5's always-confirm carve-outs are all present and unconditional: force-push outside
  `stack-sync`'s reviewed pattern, discarding work to resolve `blocked`/`overgrown`, `stack clean
  --force` on a dirty worktree, `gh pr merge --admin` (never used at all), deleting a genuinely-
  unmerged (non-squash) branch, `ci-watch`'s auto-deploy trigger, multi-branch `stack-ship`, and
  any pipeline self-edit to `.claude-atomic.yaml`/`hook-config.yaml`/`.claude/hooks/*`.
- Step 8's shakedown completes on a real scratch branch with zero manual "now do X" prompts from
  the user, end to end (commit through cleanup), across however many turns/sessions the CI wait
  actually takes.
- No remaining tracked-doc reference to `post-task-fence.sh` as a live mechanism.
- Every gate decision (deny/degrade/tier-gated auto-action) has a corresponding entry in
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

- Before starting Step 0 at all — the plan's status is "Awaiting user go-ahead per step"; do not
  begin without explicit go-ahead.
- Before beginning Step N+1 when Step N's Accepts are not met.
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
