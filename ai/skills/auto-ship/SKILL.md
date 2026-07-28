---
name: auto-ship
description: Orchestrates the agentic git lifecycle pipeline (commit → push → PR → CI-wait → ship → sync → clean) under the D3 autonomy-tier flags in .claude-atomic.yaml, gated by git-pipeline-gate.sh's due-signal detection. USE THIS SKILL when git-pipeline-gate.sh's Stop-hook hint names a due signal (commit_due, pr_due, merge_due, sync_due, cleanup_due) and the repo has opted into one or more pipeline autonomy flags, or when the user says "run the pipeline", "auto-ship this", "advance the stack pipeline".
triggers:
  - "run the pipeline"
  - "auto-ship this"
  - "advance the stack pipeline"
  - "ship this automatically"
version: 1.0
---

# Skill: auto-ship

**Purpose:** The orchestration layer for the agentic git lifecycle pipeline
(plan: `plans/2026-07-25-agentic-git-pipeline.md`, goal:
`goals/2026-07-25-03-agentic-git-pipeline.md`, Step 5). `git-pipeline-gate.sh`
(a Stop hook) only *detects and nudges* — it never executes a lifecycle leg
itself. This skill is what actually runs a leg, once the repo has durably
opted in via `.claude-atomic.yaml`'s `pipeline:` block.

**Do not build a new signal detector or validation router here.** Both
already exist and are reused as-is:
- `scripts/ai/pipeline-status.sh --json` — zero-network signal aggregator
  (`split_needed`/`commit_due`/`pr_due`/`ci_pending`/`merge_due`/`sync_due`/
  `cleanup_due`).
- `scripts/ai/validate-changeset.sh [--json]` — D2 validation routing
  (docs/config/source/unknown; never blocks on unknown).

---

## Entry Gate — run before touching any leg

This skill has its own independent kill-switch check (D6 point 2): the Stop
hook checking `hook-config.yaml`'s `git-pipeline-gate` level is not sufficient
on its own, because setting the level to `off` mid-run must stop an
**already-invoked** run from completing, not just stop new prompts.

1. **Level check.**
   ```bash
   LEVEL=$(grep "^git-pipeline-gate:" "$HOME/.dotfiles/.claude/hooks/hook-config.yaml" 2>/dev/null \
     | awk '{print $2}' | tr -d '"' | tr -d "'")
   [ "${LEVEL:-off}" = "off" ] && exit 0   # no-op, regardless of what invoked this skill
   ```
2. **Opt-in check.** `.claude-atomic.yaml` must have a top-level `pipeline:`
   key. Absent block = full confirm-first for every leg below (treat every
   flag as `false`).
3. **Identity assertion (D3a) — before any Tier-1/2 action, not Tier 0.**
   ```bash
   ACTIVE=$(gh api user --jq '.login' 2>/dev/null || echo "")
   [ "$ACTIVE" = "arjaygg" ] || { echo "auto-ship: active gh account is '$ACTIVE', not the personal arjaygg account — falling back to confirm-first"; ASSERT_FAILED=1; }
   ```
   Log the resolved actor identity (or the failure) into the audit trail
   (below) alongside the leg it gates. If the assertion fails, do not
   auto-run any Tier-1/2 leg — surface the pending action as a confirm-first
   prompt instead.
4. **First-enable dry-run requirement.** The first time a repo's
   `.claude-atomic.yaml` newly flips any Tier-1/2 flag (`auto_pr`,
   `auto_ship`, `auto_clean`) from `false` to `true` — detect by checking
   whether `.git/pipeline-state.json` has ever recorded an action for this
   repo — the first invocation of this skill after that must run in
   **dry-run/explain-only mode**: print the leg(s) it would run and the exact
   commands, take no action, and require an explicit follow-up confirmation
   before the next invocation executes for real.

---

## Leg Sequence (D4)

Run only the leg matching the current signal from `pipeline-status.sh
--json`. Never skip ahead — each leg's own precondition (the signal itself)
is what makes it safe to run unattended.

### Tier 0 — `commit_due` (flag: `auto_commit`)

- **Hard refusal, never overridable:** if the current branch is `main`, do
  not commit. Run `stack create <branch-name> main` first (see
  `ai/skills/stack-create/SKILL.md`), then re-check the signal.
- Run `scripts/ai/validate-changeset.sh --json` on the staged changeset. If
  it exits 1 (real validation failure), stop and surface the failure —
  never auto-fix or bypass.
- If validation passes, commit via the canonical wrapper:
  ```bash
  ~/.dotfiles/scripts/ai/commit.sh -m "type(scope): subject" -m "why"
  ```
  Never raw `git commit` (`ai/rules/hyper-atomic-commits.md`).

### Tier 1 — `pr_due` (flags: `auto_push`, `auto_pr`)

- Push the branch (idempotent — push only if local is ahead of the tracked
  remote ref, per D6 point 4; never force-push here).
- Open/update the PR via the `stack-pr` skill (`ai/skills/stack-pr/SKILL.md`):
  ```bash
  $HOME/.dotfiles/.claude/scripts/stack pr "$(git branch --show-current)"
  ```
- Immediately start a background `Monitor` watching `plans/ci-status.md` for
  this branch+SHA's entry to flip to green/red (D4a) — in the same turn that
  opens the PR. `git-pipeline-gate.sh` never polls; this Monitor is the only
  bridge for the CI wait, and it may span a session boundary.
- `ci_pending` itself is always advisory-only, on every gate level — there is
  nothing actionable to do besides wait.

### Tier 2 — `merge_due` (flag: `auto_ship`)

- Merge via `stack-ship` (`ai/skills/stack-ship/SKILL.md`) — **never**
  `stack-auto-pr-merge`, and **never** `gh pr merge --admin`. `stack-ship`
  re-checks CI itself at merge time as the authoritative final gate;
  `ci-status.md` was only ever the trigger, not the merge authority.
  ```bash
  $HOME/.dotfiles/.claude/scripts/stack-ship.sh --branch "$(git branch --show-current)"
  ```
- **Single-branch ship only.** If the dependency graph has more than one
  stacked branch to merge, stop and confirm — multi-branch atomic
  `stack-ship` always confirms, regardless of flags.
- Fire an `osascript` notification on completion (reusing `ci-watch`'s
  fire-and-forget pattern) — Tier-2 actions are the least reversible, so the
  user is pinged even if not watching the session.

### `sync_due` (part of Tier 2, gated by `auto_ship`)

- Fast-forward `main` from `origin/main`, resolving whichever worktree
  currently has `main` checked out via `git worktree list` (never assume a
  single shared checkout):
  ```bash
  MAIN_WT=$(git worktree list --porcelain | awk '/^worktree/{wt=$2} /^branch refs\/heads\/main$/{print wt}')
  git -C "$MAIN_WT" pull --ff-only
  ```
- If the pull fails non-fast-forward (local `main` diverged from
  `origin/main` for reasons unrelated to this pipeline), **degrade to
  confirm-first** — never force or rebase automatically.

### Tier 2 — `cleanup_due` (flag: `auto_clean`)

- Run `stack-clean` (`ai/skills/stack-clean/SKILL.md`) on the merged branch.
- Before cleaning, distinguish squash-merged (safe) from genuinely-unmerged
  (unsafe) branches — `stack-clean`'s own ancestor check under-detects
  squash-merges. If the branch is genuinely unmerged, refuse and confirm;
  never pass `--force` on a dirty worktree under any flag.
- Fire an `osascript` completion notification, same as the ship leg.

### `split_needed`

Never auto-run anything for this signal — it means the staged changeset
itself is mixed-concern. Surface `atomic-status.sh`'s own guidance and stop;
discarding work to resolve `blocked`/`overgrown` state is always-confirm,
never automated.

---

## Always-Confirm Carve-Outs (D3, not overridable by any flag)

- Any force-push outside `stack-sync`'s own `--force-with-lease` pattern.
- Discarding staged/unstaged work to resolve a `blocked`/`overgrown` state.
- `stack clean --force` on a dirty worktree.
- `gh pr merge --admin` — this pipeline never uses `--admin`, period.
- Deleting a genuinely-unmerged (not squash-merged) branch.
- `ci-watch`'s auto-deploy-on-green trigger — out of scope for this
  pipeline's flags entirely.
- `stack-ship`'s multi-branch atomic merge — single-branch ship only.
- Any pipeline-driven edit to `.claude-atomic.yaml`, `hook-config.yaml`, or
  `.claude/hooks/*` — this skill must never self-escalate its own autonomy
  tier or gate level. Only a human edit to these files raises autonomy.

## Audit Trail (D6 point 1)

Every leg this skill runs (or refuses to run, including a D3a identity
failure or a degrade-to-confirm) is appended to `.claude/pipeline-log.jsonl`
— the same durable, gitignored-but-not-`/tmp` log `git-pipeline-gate.sh`
already writes to, modeled on `stack-ship`'s own `.stack-ship/log.jsonl`
schema (timestamp, actor, action, hashes). Reuse that file; do not create a
second log.

## Terminal Status (HALT)

This skill runs unattended, so **every leg that can stop writes a terminal status before
stopping** — there is nobody to read a chat message, and a leg that ends without one is
indistinguishable from a crash. That includes the boring exits: a refused leg, a
degrade-to-confirm, a D3a identity failure, and `split_needed`.

The definition lives in `plans/2026-07-27-native-agent-orchestration.md` §15 and is implemented
in `.claude/workflows/orchestrate.js` (`halt()`). Do not restate the rules here — reuse them.
The minimum payload is `status` (`done`|`blocked`), the blocking condition in one line, the
artifact path, and **`stage`** — the leg the status belongs to
(`auto_commit`/`auto_push`/`auto_pr`/`auto_ship`/`auto_clean`).

`stage` is what makes autonomy demotion possible (plan Part VIII, Step 18).
`git-pipeline-gate.sh` writes a demotion marker only for an entry that names its own stage,
because a stage-less `blocked` cannot be attributed to a leg without guessing — and guessing
would demote a leg the failure never touched. An entry without `stage` is therefore silently
non-demoting: omitting it does not fail loudly, it just means the ladder never reacts.

Word the condition accurately, because it decides whether the leg is demoted. A stop for
*missing authorization* — a refusal, a degrade-to-confirm, a D3a identity failure — must read
as such; those are matched as non-defects and never demote, precisely so that an unattended
run does not ratchet its own tier down every time it correctly stops to ask. Only genuine
defects should read like defects.

Where it goes: the existing audit trail, `.claude/pipeline-log.jsonl`. Do not create a second
log — the status is one more entry in the file this skill already appends to, so a resumed run
finds it by reading what it already reads.

Degenerate cases get their own deterministic filename rather than a third name that could
collide with either candidate: an unresolvable branch or PR id lands at `<id>-unresolved.md`, an
ambiguous match at `<id>-ambiguous.md`.

A `done` status that could not be persisted is **not** reportable as success. If the write
fails, the leg is `blocked` — the run finished but cannot prove it, which is the same thing to
whoever picks it up next.

## Rollback Runbook (D6 point 3)

No new tooling — recovery uses existing primitives, keyed off the audit
log's recorded hashes:

- **Undo a bad merge:** `git revert -m 1 <merge-sha>` (the merge commit SHA
  is in `.stack-ship/log.jsonl`'s `hash_after` field for that entry).
- **Recover a branch after `stack-clean` removed it:** re-create the
  worktree from the branch name recorded in the audit log —
  `git worktree add .trees/<name> <branch>` — then, if the branch ref itself
  was deleted, recreate it from the pre-merge SHA recorded in
  `.stack-ship/log.jsonl`'s `hash_before` field: `git branch <branch>
  <hash_before>`.
- **Recover from a bad auto-commit:** `git reset` is a manual, confirm-first
  operation — this runbook does not automate it. Identify the commit via
  `.claude/pipeline-log.jsonl`'s `sha` field for the `commit_due` entry.
- `stack-ship`'s own automatic rollback-on-post-merge-CI-failure is separate,
  future Phase 4 work in its RFC (`decisions/RFC-STACK-SHIP-001.md`) and is
  **not** a dependency here — this runbook is manual-but-documented.

## Common Rationalizations

| Excuse | Rebuttal |
|---|---|
| "The user enabled auto-ship once, so future tiers are pre-approved too" | Each tier (commit/push+PR/merge/clean) has its own gate and its own opt-in key in `.claude-atomic.yaml` — enabling Tier 0 never implies Tier 2 approval. |
| "This is the second run today, skip the first-enable dry-run" | The dry-run requirement is keyed to first-enable of a *tier*, not a calendar day — a newly-enabled tier still needs its dry-run regardless of how many prior runs of other tiers happened. |
| "D3a identity check already passed earlier this session" | Identity can drift mid-session (`gh auth switch`) — re-assert identity at the leg that actually ships, not from a cached earlier check. |
| "auto_ship above A2 is basically the same risk as A2" | The always-confirm carve-outs exist precisely because merge/ship actions are irreversible in a way commit/PR actions aren't — never auto-escalate past A2 without explicit confirmation. |

## Red Flags

- A tier's action runs without checking that tier's specific key in `.claude-atomic.yaml` (e.g. `auto_ship` action running when only `auto_commit` is enabled) — *checkable*: does the executed leg match an enabled key in the config file?
- `gh api user` (or equivalent identity assertion) was not re-run immediately before a Tier 2 leg.
- A tier runs its first-ever execution without a preceding dry-run.
- Any autonomy tier above A2 executes without an explicit user confirmation logged in the audit trail.

## Verification

- [ ] The executed leg's config key (`auto_commit`/`auto_push`/`auto_pr`/`auto_ship`/`auto_clean`) is present and enabled in `.claude-atomic.yaml` (evidence: config file content quoted alongside the executed leg).
- [ ] Identity was asserted via `gh api user` immediately before any Tier 2 action (evidence: command output timestamp near the ship action).
- [ ] A dry-run preceded the first-ever execution of a newly-enabled tier (evidence: audit trail entry for the dry-run).
- [ ] Every entry above A2 has a corresponding explicit user-confirmation record in the audit trail (evidence: audit log line).
- [ ] Every leg that stopped — including refusals, degrade-to-confirm, and identity failures — wrote a terminal status to `.claude/pipeline-log.jsonl` (evidence: the status entry, quoted, with its `status` and condition).

## Related

- `ai/skills/stack-pr/SKILL.md`, `ai/skills/stack-ship/SKILL.md`,
  `ai/skills/stack-sync/SKILL.md`, `ai/skills/stack-clean/SKILL.md`,
  `ai/skills/stack-create/SKILL.md`, `ai/skills/ci-watch/SKILL.md`
- `.claude/hooks/git-pipeline-gate.sh` — the Stop-hook trigger this skill
  responds to (detection only, never executes a leg itself)
- `scripts/ai/pipeline-status.sh`, `scripts/ai/validate-changeset.sh`
- `plans/2026-07-25-agentic-git-pipeline.md` — full design (D1-D7)
- `plans/2026-07-27-native-agent-orchestration.md` §15 — the terminal-status (HALT) definition this skill reuses
- `ai/rules/hyper-atomic-commits.md` — canonical commit wrapper discipline
