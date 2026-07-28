# Harness end-to-end proof — first non-dry orchestrate.js run

**Date:** 2026-07-28 · **Run:** `wf_48902af9-8a4` · **Label:** `2026-07-28-e2e-probe`
**Result:** the cycle completes, but **the harness is not safe to run from a worktree** — which is
the workflow this repo mandates for all non-trivial work.

## Why this run happened

Goal 05 verified the harness's parts. Every Step 14/15 acceptance check used
`args:{dryRun:true}`, and `dryRun` short-circuits `runStage()` to return fixtures — so **no check
ever touched the filesystem or spawned a worker**. The integrated path had never run once.

Two findings pointed the same way: `executor-implement` no-opped on its first real use, and
`orchestrate.js` builds `plans/specs/<label>.md` undated while `pre-tool-gate-v2.sh` enforces a
date on `plans/` writes. Both suggested the real path was untested.

## What was tested

A deliberately trivial spec (`plans/specs/2026-07-28-e2e-probe.md`): create one file with exact
content, touch nothing else. Trivial on purpose — completing the *cycle* was the test, not the task.

The label was dated (`2026-07-28-e2e-probe`) so that `specPath` = `plans/specs/2026-07-28-e2e-probe.md`
satisfies the hook. **That is the undocumented workaround for the undated-path defect: the date has
to live in the label.** Nothing states this, and `plans/specs/TEMPLATE.md` says the path is
`plans/specs/<label>.md`.

## What worked

- **All five stages ran** — `mark_running`, `implement`, `review`, `triage`, `halt`. 5 agents,
  ~13 min, 258k tokens.
- **`markRunning()` fired for real.** The spec frontmatter went `status: draft` → `status: running`.
  The Step 15 fix works: the SIGKILL detector now has a live producer.
- **The implement worker respected the tree.** The spec warned in bold that cwd is the main checkout
  and demanded absolute paths; the worker complied, wrote only
  `.trees/harness-end-to-end-proof/docs/e2e-probe.md`, byte-exact, and verified its own criteria
  programmatically. Main stayed clean at that point.
- **Triage did its job.** 4 findings → 2 `intent_gap`, 2 `bad_spec`; the §23 cascade fired
  (`an intent_gap is present — every other finding is moot this pass`), and the run halted
  `blocked` for a human instead of proceeding. That is the designed behaviour, not a failure.
- **The review stage produced a genuinely good finding** via the `doubt` lens: the artifact's
  terminal state is *untracked*, and this repo's own worktree teardown would delete it. That is a
  real observation about the probe, found unprompted.

## What broke — the headline

**`halt` wrote the terminal status to the wrong repository tree.**

- `mark_running` resolved to `…/.trees/harness-end-to-end-proof/plans/specs/2026-07-28-e2e-probe.md`
  ✅
- `halt` resolved to `/Users/axos-agallentes/.dotfiles/plans/specs/2026-07-28-e2e-probe.md` ❌ —
  **main**, where it created a **new 11-line file** containing only frontmatter.
- The real 63-line spec in the worktree **still says `status: running`** and was never updated.
- The run nonetheless reported **`terminal_status_written: true`**.

### Root cause

`orchestrate.js` uses paths relative to `SPEC_DIR = 'plans/specs'`. A workflow script's stage agents
run with cwd = the **main checkout**, not the worktree the script lives in. `mark_running` survived
only by accident — its prompt says "set status in the frontmatter of X", so the agent searched and
found the sole existing copy. `halt`'s prompt says *"if the file exists, update it in place;
otherwise create it"* — from main's cwd it did not exist, so it created one.

### Why this is worse than a misplaced file

1. **`terminal_status_written: true` is a lie.** The run believes it recorded its outcome. §15's
   whole premise is that a run ending without a terminal status is indistinguishable from a crash —
   here the status exists, just not where any reader will look.
2. **It manufactures a false crash signature.** The worktree spec is left at `status: running` with
   no terminal status, which is *precisely* the killed-run signature `markRunning()` was added to
   create. The next run treats a completed, correctly-blocked run as a crash. The Step 15 fixes
   interact badly: giving the detector a producer made this defect *worse*, not visible-but-harmless.
3. **It dirties `main`.** An untracked file appears on the trunk from a run that was scoped to a
   worktree.

## Secondary observations

- **The undated spec path is real but has a workaround** — put the date in the label. Undocumented,
  and it means `label` is load-bearing for hook compliance, not just identity.
- **`.claude/references` IS present in worktrees.** The recorded decision
  (`plans/decisions.md`, "defer the `.claude/references` worktree gap") says no worktree has it.
  That is now stale — it resolves. `DOD_PATH` uses the tracked `ai/references/...` path anyway.
- **`.claude/settings.json` re-dirties itself continuously.** Within minutes of discarding the
  machine-local absolutization, the live app rewrote the same three lean-ctx `$HOME` paths. It is a
  drift loop, not user work — relevant to anything that needs a clean trunk.

## The fix, not applied here

`orchestrate.js` needs a **repo-root anchor** so every stage resolves paths against the tree the run
belongs to, rather than each agent's cwd. Options, and this is a design call:

1. **`args.root`** — caller passes the worktree root; the script prefixes every path with it.
   Explicit, no magic, but every caller must remember.
2. **Derive from the script's own location** — the runtime does not currently hand the script its
   own path, so this needs a runtime affordance.
3. **Make each stage prompt demand an absolute path** and fail loudly if given a relative one — the
   implement worker succeeded precisely because the *spec* insisted on absolute paths.

(1)+(3) together is the smallest change that closes it: pass the root, and make `halt`'s prompt
refuse to create a file outside it.

**Until this is fixed, `orchestrate.js` should only be run from the main checkout**, and Part VIII's
ladder should not credit any autonomy to a path whose terminal-status guarantee silently writes to
the wrong tree.

---

## Fix applied and verified (same day)

**Chosen approach:** `args.root` + a confinement clause on every writing prompt.

- `ROOT` comes from `args.root`; `atRoot(rel)` prefixes it. Every path that reaches a stage prompt
  now goes through it — `haltPathFor()`, `specPath`, `patch_file`, and `DOD_PATH`. Omitting
  `args.root` preserves the old relative behaviour, which is correct only from the main checkout.
- `CONFINE` is appended to both writing prompts (`halt`, `mark_running`): *the path is absolute and
  final, write only to it, do not create anything outside ROOT, report `written:false` and stop
  rather than creating the file elsewhere or "finding" a similar file in another checkout.* The
  create-if-absent instruction is what converted a wrong cwd into a wrong-tree write, so the refusal
  had to be explicit rather than implied by the path.

**Re-run with the fix** (`wf_8ed52c3a-6fe`, same spec, spec reset to `status: draft` first):

| | Before (`wf_48902af9-8a4`) | After (`wf_8ed52c3a-6fe`) |
|---|---|---|
| `mark_running` target | worktree (by accident) | worktree |
| `implement` target | worktree | worktree |
| **`halt` target** | **`<main>/plans/specs/…` — new 11-line file** | **`<worktree>/plans/specs/…` — updated in place** |
| Worktree spec final state | `status: running`, never updated | `status: blocked` + condition |
| Body preserved | n/a (wrote a new file) | yes — 66 lines, `intent-contract` intact |
| Stray file on `main` | yes | **no** |
| `terminal_status_written` | `true` (false claim) | `true` (accurate) |

The false-crash-signature problem is gone: the spec now ends at `blocked` with its condition, so the
next run reads a completed-and-blocked run correctly instead of inferring a kill.

**Regression tests** (`scripts/test_orchestrate_workflow.py`, 37 passing): every `SPEC_DIR`/`DOD_PATH`
interpolation must go through `atRoot()`, and both writing prompts must carry `${CONFINE}` including
the `report written:false` refusal. A future un-anchored path fails the suite.

### Still open, deliberately

- **Nothing forces callers to pass `args.root`.** Omitting it silently restores the old behaviour.
  A stricter version would refuse to run from a non-main cwd without a root, but the script cannot
  see its own location, so it cannot detect that today. Option (3) from above — a runtime affordance
  giving a script its own path — remains the durable fix.
- **The undated `plans/specs/<label>.md` convention still conflicts with the hook.** The workaround
  is to date the *label*. `plans/specs/TEMPLATE.md` should say so, or `haltPathFor()` should insert
  the date itself.
- Triage produced different-but-valid findings across the two runs (`intent_gap`×2 then
  `bad_spec`×2 — the doubt lens critiqued this very document's claims). Both correctly halted for a
  human. Non-determinism across runs is expected of an LLM stage and is not a defect, but it does
  mean a single green run is not evidence of a stable contract.
