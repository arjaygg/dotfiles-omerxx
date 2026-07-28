---
status: draft
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — goal05-closeout

<intent-contract>
Close four verified acceptance failures found in the Goal 05 final audit. Each already has a
verdict and evidence; your job is the mechanical fix plus its test, not re-investigation.

Success = all four items done, `python3 -m pytest scripts/ -q` still fully green, and
`python3 scripts/validate_skills.py` still exits 0. Change nothing beyond these four items.
</intent-contract>

## Working directory

`/Users/axos-agallentes/.dotfiles/.trees/autonomy-ladder-reconcile` — a git worktree on branch
`feature/autonomy-ladder-reconcile`. Work there, never in `/Users/axos-agallentes/.dotfiles`
(that is `main` and carries unrelated uncommitted changes you must not disturb).

**Tooling — you will hit blocks otherwise.** Serena refuses gitignored paths and `.trees/` is
gitignored, so use `mcp__lean-ctx__ctx_read` / `ctx_patch` / `ctx_search` for files here. To run
any repo script, `ctx_shell` is blocked by an allowlist — use `mcp__lean-ctx__ctx_call` with
`name="ctx_execute"`, `arguments={language:"shell", code:"..."}`. Inline `python3 -c` is blocked;
write a script file. Piping to `head`/`tail` in native Bash is blocked.

## Task

### 1. `setup.sh` never removes symlinks for `retired` skills (Step 9 criterion f)

**Evidence:** `setup.sh:101-104` defines `is_retired_skill()` (greps `ai/skills/REMOVALS.md` for
`| retired |`), used at `:144` and `:173` as `is_retired_skill "$_name" && continue`. That only
*skips creating* a link — it never removes one that exists. `link_skills_from_dir()` (`:109-136`,
called at `:217` for `~/.codex/skills`) has **no** retired check, so it re-creates retired links
every run via `ln -sfn` at `:134`. `check-skill-drift.sh --prune-stale-links` removes only
*dangling* links, and a retired skill's target is still valid, so it survives. Observed present:
`~/.claude/skills/tech-lead`, `~/.codex/skills/tech-lead`, `~/.gemini/skills/tech-lead`,
`~/.agents/skills/tech-lead`.

**Do:**
- Add the `is_retired_skill` guard inside `link_skills_from_dir()` so it stops re-creating them.
- Add an explicit removal pass that, for each `retired` ledger entry, removes the link from every
  managed skills dir (`.claude/skills`, `~/.claude/skills`, `~/.codex/skills`,
  `~/.gemini/skills`, `~/.agents/skills`). Remove **only** symlinks — never a real directory.
  Log each removal. Idempotent, and safe when a path is absent.
- `.claude/skills/tech-lead` is a git-TRACKED symlink (`git ls-files .claude/skills/tech-lead`
  returns a hit). `git rm --cached` it and delete the link so the tracked entry goes too.

**Accepts:** after `./setup.sh`, a `retired` skill has no link in any managed dir; running twice
is idempotent; no real directory is ever deleted. Add a test under `scripts/` (follow the
existing `scripts/test_*.py` unittest idiom) building a temp tree with one fake `retired` entry
and one live entry, asserting the retired link is removed and the live one survives.

### 2. `ai-usage-analyst` ledger row contradicts reality (Step 9 criterion d)

**Evidence:** `ai/skills/REMOVALS.md` carries a `disabled-pending` row for `ai-usage-analyst`
("off until that data access is standard"), but it has **no** `skillOverrides` key at all, so it
is not disabled. `ai/skills/ai-usage-analyst/SKILL.md` exists and is live.

**Do:** amend only that row's rationale to state the contradiction plainly — the row asserts
disabled-pending while nothing gates it, so either an `"off"` override is missing or the row is
stale, and that is a user decision. **Do not** add the override yourself; it would silently
disable a live skill.

**Accepts:** the row states the contradiction and names both resolutions. No settings file edited.

### 3. `lensed-review/SKILL.md` exceeds its stated budget (Step 10)

**Evidence:** plan line 839 specifies `<= 80 lines`; `wc -l ai/skills/lensed-review/SKILL.md` = 94.

**Do:** trim to <= 80 lines without losing meaning. The `Do not` and `Verification` sections
restate content already in `lenses.toml` comments and `ai/skills/cap/references/schemas.md` —
prefer pointing at those over repeating them. Do **not** delete the Customization section (Step 11
asserts its three-file fallback wording) and do not remove the `lens`/no-`severity` finding
contract.

**Accepts:** `wc -l` <= 80; `python3 scripts/validate_skills.py` exits 0; the strings
`three-file fallback`, `scalars override`, and `lens` are all still present.

### 4. Nothing deterministically checks `lenses.toml` (Step 10 criterion b)

**Evidence:** `grep -rn 'lenses.toml' --include=*.py --include=*.js --include=*.sh` returns ZERO
hits — no code ever parses it. "An empty-`instruction` lens is skipped" is prose in SKILL.md plus
an LLM-graded Tier-3 expectation, so no deterministic check exists that the data contract holds.

**Do:** add `scripts/test_lensed_review_lenses.py` (unittest, `tomllib`) asserting:
- `lenses.toml` parses;
- every lens has exactly the five keys `code, applies_to, when, after, instruction`;
- the enabled-lens filter — `instruction` non-empty after strip — excludes the `performance`
  lens (its instruction is `""` today) and includes `correctness`;
- at least one lens is enabled (a config where everything is skipped is a bug, not a valid state).

Do **not** invent a new runtime script or a `--dry-run` CLI; a data-contract test is the smaller
change and is what was actually missing.

**Accepts:** the new test passes, and fails if `performance.instruction` is given a value.

## Files

In scope: `setup.sh`, `ai/skills/REMOVALS.md`, `ai/skills/lensed-review/SKILL.md`,
`scripts/test_lensed_review_lenses.py` (new), one new `scripts/test_*.py` for item 1, and
`.claude/skills/tech-lead` (removal).

**Out of scope — do not touch:** `.claude/settings.json`,
`ai/config/claude/settings.base.json`, `.claude/hooks/*`, `.claude-atomic.yaml`,
`hook-config.yaml`, `scripts/skill_lint_baseline.json`, `plans/`, `goals/`. The settings/hooks
group is gated by decision D3 (no pipeline-driven config edits).

## Commits

Use `~/.dotfiles/scripts/ai/commit.sh -m "type(scope): subject" -m "body"` — never raw
`git commit`. One commit per numbered item (four total), each body explaining WHY. Run
`~/.dotfiles/scripts/ai/atomic-status.sh` before each commit. **Do not push. Do not open a PR.**

## Verification

- [ ] `python3 -m pytest scripts/ -q` → fully green, count >= 329 (the pre-change baseline) plus
      your new tests.
- [ ] `python3 scripts/validate_skills.py` → exits 0.
- [ ] `wc -l ai/skills/lensed-review/SKILL.md` <= 80.
- [ ] No `retired` skill retains a link in any managed dir; `grep -c '| retired |'
      ai/skills/REMOVALS.md` still > 0.
- [ ] Report each item's evidence (command + output) verbatim in your final message.

## Anti-nesting

Do the work yourself. Do not spawn subagents.
