---
status: draft
---

# Frozen Spec — Step 10 Worker B: schema update, shims, ledger, eval migration

Worktree: `/Users/axos-agallentes/.dotfiles/.trees/native-agent-orchestration-step10`
Branch: `chore/native-agent-orchestration-step10` (based on `main`)

Scoped sub-spec (part 2 of 3) of `plans/specs/2026-07-28-step10.md`. Do NOT open that file or the
plan doc — everything needed is quoted below. **Wait for Worker A's commit to land first** (it
creates `ai/skills/lensed-review/`, which this spec references) — check `git log --oneline -3`
before starting; if `ai/skills/lensed-review/SKILL.md` doesn't exist yet via `Glob`, stop and
report rather than guessing at its shape.

**Tool constraint (critical, caused prior failures):** Use ONLY native `Read`/`Write`/`Edit`/
`Bash`/`Grep`/`Glob` with absolute paths. Do NOT use any `ctx_*`/`Serena.*`/`LeanCtx.*` tools — in
this worktree they are root-confined to a different worktree and will fail, thrashing context on
retries. Skip any pctx/Serena init ritual.

## Background (verbatim quotes)

**§20 "The finding contract":**
> A finding carries exactly these fields, plus any the producing lens declares: `lens` (required,
> the code of the lens that produced it — the dedupe rule needs it), `location`, `trigger_condition`,
> `guard_snippet`, `potential_consequence`. **No `severity`, `priority`, or ranking field** —
> severity is assigned by the Coordinator during triage, never by the producer.
> `ai/skills/cap/references/schemas.md` currently requires `severity` per finding at roughly lines
> 126 and 139 — remove it there.

**Confirmed by direct grep this session:** `ai/skills/cap/references/schemas.md` has `"severity":
"CRITICAL|HIGH|MEDIUM|LOW"` around line 126 (a findings-array object). Locate it and any other
`severity` occurrence in that file (there may be more than one) and remove/replace per below.

**§29 "Skill lifecycle":**
> **`REMOVALS.md`** — a machine-readable retirement ledger the installer consumes, with the
> *reason* inline, recording honest negative results. **shims** — forwarders holding no logic,
> pinning the *legacy output contract* so existing callers keep working.

**IMPORTANT correction to the full spec's assumption:** the full spec claims `ai/skills/REMOVALS.md`
"already exists — Step 9 created it" in this worktree. That was TRUE on Step 9's branch but Step
9's branch was never merged into `main`, and this worktree branched from `main` — so the file was
originally absent here. **This has already been fixed for you**: `ai/skills/REMOVALS.md` has been
materialized into this worktree (via `git show <step9-sha>:ai/skills/REMOVALS.md`) as an untracked
file, with Step 9's exact existing format. Read it now with native `Read` to see the format: it's a
markdown table with columns `| skill | state | rationale |`, states are `retired` /
`superseded-by <skill>` / `disabled-pending <reason>`. It currently has ~104 rows for skills
disabled via `.claude/settings.json`'s `skillOverrides`. This file is untracked (`git status`
will show `?? ai/skills/REMOVALS.md`) — it needs to be committed as part of your work here, not
just referenced.

## Task

1. Locate every `severity` occurrence in `ai/skills/cap/references/schemas.md` via `Grep`. Edit the
   file so findings include a `"lens"` field (matching §20's `lens` — required, the producing
   lens's code) instead of `"severity"`. Preserve everything else in the schema's structure/shape;
   this is a field swap, not a redesign.
2. Confirm via `Grep -c severity ai/skills/cap/references/schemas.md` (or equivalent count) that
   the result is 0 after your edit.
3. For each skill superseded by `lensed-review` — `hawk`, `pr-review`, `code-health`,
   `bmad-custom-pr-review` — do the following:
   a. Replace the skill's `SKILL.md` body with a **shim**: no review logic, just a short forwarder
      that says this skill is superseded by `lensed-review` and preserves the *legacy output
      contract* (i.e. still emits output shaped the way old callers expect, by delegating to
      `lensed-review` under the hood conceptually — keep this file small, it's a forwarder, not a
      reimplementation).
   b. Add one row to `ai/skills/REMOVALS.md`'s table: `| <skill> | superseded-by lensed-review |
      <one-sentence honest reason, e.g. "Consolidated into ai/skills/lensed-review/ as the
      <lens-code> lens per Step 10 of the native-agent-orchestration goal."> |`. Match the existing
      table's exact column format and voice — do not invent a new ledger format.
   c. Find that skill's eval cases (search `evals/` for references to the skill name — likely under
      `evals/cases/` or similar) and migrate them into `evals/cases/` so they now exercise
      `lensed-review` (or its shim) instead of the retired skill directly. Do not leave orphaned
      eval cases referencing a skill that no longer has real logic.
4. Also check the agents listed in §22 as being consolidated — `security-reviewer`,
   `claude-code-review-agent`, `silent-failure-hunter`, `database-reviewer`,
   `performance-optimizer` (likely under `.claude/agents/`) — via `Glob`/`Grep`. If they are genuine
   duplicate review logic (not merely named similarly), apply the same shim+ledger treatment. If
   inspecting them shows they're out of scope or ambiguous, note that in your report rather than
   guessing — do not force a shim onto something that isn't actually superseded.
5. Do NOT touch anything named `review` (Claude Code built-in) or `simplify`/`code-review`.
6. Check `~/.dotfiles/scripts/ai/atomic-status.sh`; if staged changes exceed thresholds (7 files /
   300 diff lines / 3 subsystems), split into 2 commits along natural lines (e.g. schema edit as
   one commit, shims+ledger+evals as another) rather than one giant commit. Commit via
   `~/.dotfiles/scripts/ai/commit.sh` only — never raw `git commit`. Stay on
   `chore/native-agent-orchestration-step10`. Do not merge to `main`.

## Constraints

- Anti-Nesting Rule: no nested subagents.
- Do not edit anything under `ai/skills/lensed-review/` (Worker A's scope) beyond reading it for
  context.
- Do not touch `evals/collision-baseline.md` or run collision-detection — that's Worker C's scope.
- No drive-by cleanup beyond what's listed.

## Acceptance for this worker

- [ ] `ai/skills/cap/references/schemas.md` has a `lens` field and zero `severity` occurrences
      (show the grep-equivalent count).
- [ ] Each of `hawk`, `pr-review`, `code-health`, `bmad-custom-pr-review` has: a shim `SKILL.md`, a
      `ai/skills/REMOVALS.md` row, and migrated eval cases — enumerate each explicitly.
- [ ] Any superseded agents from §22's list got the same treatment, or a clear note explaining why
      not.
- [ ] Nothing named `review` was created or touched.
- [ ] Changes committed via `commit.sh` (one or more atomic commits) on
      `chore/native-agent-orchestration-step10`.

Report back: schema diff summary + grep count, per-skill shim/ledger/eval-migration confirmation,
agent-consolidation notes, and commit SHA(s).
