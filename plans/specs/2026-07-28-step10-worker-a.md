---
status: draft
---

# Frozen Spec — Step 10 Worker A: scaffold `lensed-review` skill

Worktree: `/Users/axos-agallentes/.dotfiles/.trees/native-agent-orchestration-step10`
Branch: `chore/native-agent-orchestration-step10` (based on `main`)

This is a SCOPED SUB-SPEC (part 1 of 3) of the full Step 10 spec at
`plans/specs/2026-07-28-step10.md`. Do NOT open that file or the 1034-line plan doc — everything
you need is quoted below. Two prior full-scope worker attempts on this step died from
autocompact-thrashing; this narrower scope exists to avoid repeating that.

**Tool constraint (critical, caused a prior failure):** Use ONLY native `Read`/`Write`/`Edit`/
`Bash`/`Grep`/`Glob` with absolute paths. Do NOT use any `ctx_*`/`Serena.*`/`LeanCtx.*` tools —
in this worktree they are root-confined to a different worktree and every call will fail with
"path escapes project root", thrashing your context on retries. Skip any pctx/Serena init ritual.

## Background (verbatim quotes — do not re-derive)

**§22 "One review mechanism":**
> There is **one** review implementation: the lensed review skill (Step 10). The orchestrator's
> reviewer stage invokes it rather than embedding its own. The doubt cycle is its **adversarial
> lens**, not a parallel harness. Every lens emits the §20 finding shape.
>
> Lenses are declared as keyed config tables. The five keys per lens entry:
>
> | Field | Purpose |
> |---|---|
> | `code` | stable identity; the merge key for overrides |
> | `applies_to` | `code` \| `docs` \| `any` — the first filter |
> | `when` | prose refinement of applicability |
> | `after` | names the one lens whose findings this lens receives |
> | `instruction` | the whole recipe; **empty string disables the lens** |
>
> Each lens's reference file loads **just-in-time** — only the running lens's file is ever paid
> for. A default review runs every enabled lens matching `applies_to` and `when`; an explicitly
> requested lens runs regardless of both.
>
> **Anti-drift:** "Never claim a capability from this file; read the resolved lenses and work from
> those." The skill body must not assert what config decides.
>
> Review-ish skills/agents being consolidated: `hawk`, `pr-review`, `code-health`,
> `bmad-custom-pr-review`, plus the agents `security-reviewer`, `claude-code-review-agent`,
> `silent-failure-hunter`, `database-reviewer`, `performance-optimizer`. Note `simplify`, `review`,
> and `code-review` are **Claude Code built-ins**, not repo skills — they cannot be shimmed or
> retired, and must never be created/touched. The consolidated skill is named `lensed-review`.

**§20 "The finding contract"** (for reference only — Worker B edits schemas.md, but your new lens
reference files should describe findings in this shape):
> A finding carries exactly these fields, plus any the producing lens declares: `lens` (required),
> `location`, `trigger_condition`, `guard_snippet`, `potential_consequence`. No `severity`,
> `priority`, or ranking field.

## Task

1. Confirm the five keys above are what you'll use in `lenses.toml` (trust the quote, don't
   re-verify against the plan file).
2. Find the skills being consolidated under `ai/skills/`: `hawk`, `pr-review`, `code-health`,
   `bmad-custom-pr-review`. Use `Glob("ai/skills/{hawk,pr-review,code-health,bmad-custom-pr-review}/**")`
   or individual `Glob`/`Read` calls. Skim each `SKILL.md` briefly (just enough to know what lens
   each becomes — correctness/security/style/etc.) — do not deep-read every reference file.
3. Create `ai/skills/lensed-review/SKILL.md` (≤80 lines): frontmatter, conventions, activation,
   pointers to `lenses.toml` and `references/`. Do not inline lens instructions here. Must not be
   named `review` (Claude Code built-in — never touch/create anything named exactly `review`).
4. Create `ai/skills/lensed-review/lenses.toml`: one entry per lens derived from the consolidated
   skills (e.g. `correctness`, `security`, `style`/`simplicity`, `doubt` for the adversarial cycle,
   plus any others the source skills warrant). Each entry has exactly the five keys from §22. The
   doubt/adversarial lens is a regular entry here (`after` referencing the lens whose findings it
   critiques), not a separate script. **At least one lens must have `instruction = ""`** (empty) to
   prove skip-in-dry-run-behavior later — pick a low-value/rarely-needed lens for this, not doubt.
5. Create `ai/skills/lensed-review/references/lens-<code>.md` for every lens with a non-empty
   `instruction` — one file per lens, each ≤90 lines, self-contained recipe for that lens.
6. Run `wc -l ai/skills/lensed-review/references/lens-*.md` and confirm every file is ≤90 lines.
7. Check `~/.dotfiles/scripts/ai/atomic-status.sh` in this worktree, then commit via
   `~/.dotfiles/scripts/ai/commit.sh -m "feat(lensed-review): scaffold consolidated review skill" -m "<why>"`.
   Do NOT use raw `git commit`. Stay on branch `chore/native-agent-orchestration-step10`. Do not
   merge to `main`.

## Constraints

- Anti-Nesting Rule: do not spawn nested subagents — do all of this yourself.
- Do not edit `ai/skills/cap/references/schemas.md`, `ai/skills/REMOVALS.md`, or `evals/` — that is
  Worker B's and Worker C's scope, not yours.
- Do not delete or shim the superseded skills (`hawk`, `pr-review`, `code-health`,
  `bmad-custom-pr-review`) — that is Worker B's scope.
- No drive-by cleanup/renames beyond what's listed above.

## Acceptance for this worker

- [ ] `lenses.toml` exists, parses, every entry has exactly the five keys from §22 (show output).
- [ ] At least one lens has `instruction = ""`.
- [ ] Every `references/lens-*.md` file is ≤90 lines (show `wc -l` output).
- [ ] `ai/skills/lensed-review/SKILL.md` exists, ≤80 lines, does not inline lens instructions.
- [ ] Nothing named `review` was created or touched.
- [ ] Changes committed via `commit.sh` on `chore/native-agent-orchestration-step10`.

Report back: files created, lens list with their five-key values, line counts, and the commit SHA.
