# 0020 — User-global instruction files are reproducible and drift-checked

**Status:** Accepted
**Date:** 2026-08-03
**Extends:** `decisions/0016-untracked-runtime-claude-settings.md` (same bootstrap-if-absent
contract, applied to `CLAUDE.md`, `~/.claude/rules/`, `~/.codex/rules/`, `~/.codex/hooks.json`)

## Decision

Make every user-global instruction artifact reproducible by `setup.sh` and drift-visible via
`config-integrity.sh`:

- **`~/.claude/CLAUDE.md`** — `.claude-global/CLAUDE.md` becomes its tracked template, refreshed to
  match the live file. `setup.sh` copies it **only when the live file is absent**. Not symlinked:
  the lean-ctx binary rewrites the `<!-- lean-ctx -->` block at runtime, which is the same reason
  0016 kept `settings.json` unlinked.
- **`~/.claude/rules/` and `~/.codex/rules/`** — `setup.sh` links the four shared rules per file.
  These are real directories holding per-file symlinks, unlike `~/.cursor/rules`, which is a
  whole-directory link and was therefore already durable.
- **`~/.codex/hooks.json`** — new tracked template `ai/config/codex/hooks.global.base.json`,
  installed bootstrap-if-absent. Carries the subagent gate from 0018.
- **Three new `config-integrity.sh` checks** (advisory, `exit 0`): template drift for `CLAUDE.md`
  (excluding the generated block, the template's maintainer comment, and blank lines); missing rule
  symlinks; and a `~/.codex/hooks.json` missing the `pre-agent-gate.sh` matcher.

## Why

`~/.claude/CLAUDE.md` — the file carrying every user-global Claude policy — was **untracked and not
reproducible**. `setup.sh` never referenced it. A tracked copy existed at `.claude-global/CLAUDE.md`
but had not been touched since **2026-06-16** while the live file was restructured on **2026-07-26**,
so the two had diverged structurally: the tracked copy still carried a ~170-line Azure DevOps CLI
section that the live file had already delegated to `ai/skills/azure-devops-cli/SKILL.md`, and listed
a rules line that no longer matched.

That produced two live failure modes, neither hypothetical:

1. A machine rebuild silently loses all user-global Claude policy.
2. Any reader — human or agent — treating the tracked copy as source of truth gets six-week-old
   guidance, including a section that had been deliberately extracted.

The same gap covered the rule symlinks and the Codex global hooks. `setup.sh` linked
`~/.cursor/rules` as a directory and `~/.codex/AGENTS.md` explicitly, but nothing created
`~/.claude/rules/` or `~/.codex/rules/`, and nothing installed `~/.codex/hooks.json`. So on a
rebuild, Cursor would keep the shared rules while Claude and Codex lost them, and the Codex subagent
gate would vanish entirely — leaving policy that reads as enforced but is not.

Bootstrap-if-absent alone does not prevent recurrence: a copy can always drift, which is exactly what
happened. The drift checks are the part that closes the loop, in the same advisory style the repo
already uses for symlink and JSON integrity.

## Alternatives rejected

- **Symlink `~/.claude/CLAUDE.md` into the repo:** rejected — the lean-ctx binary regenerates its
  block in the live file, so every regeneration would dirty the working tree, and a stale generated
  block would be committed as though it were policy. This is 0016's reasoning verbatim.
- **Delete `.claude-global/` and treat the live file as the only copy:** rejected — that accepts
  permanent unreproducibility, which is the defect being fixed.
- **Track the generated lean-ctx block in the template:** rejected — guarantees drift on every
  regeneration and would make the drift check useless by making it always fire.
- **Symlink `~/.codex/hooks.json` to `.codex/hooks.json`:** rejected — those two files legitimately
  differ. The project-scoped file wires `.dotfiles`-relative hooks; the global file wires the
  `lean-ctx` binary hooks. Linking them would silently replace one client's hook set with the other's.
- **Hard-fail on drift:** rejected — drift between a live runtime file and its template is normal
  mid-edit and is not a safety issue. Warning matches how `check_symlink` and `check_json` already
  behave, and `config-integrity.sh` runs under `trap 'exit 0' ERR` anyway.
- **Auto-reconcile the live file from the template:** rejected — that is the `settings-symlink-guard.sh`
  copy-back behaviour that caused ADL-020's silent drift. Report, never overwrite.

## Consequences

- Editing `~/.claude/CLAUDE.md` now requires editing `.claude-global/CLAUDE.md` in the same change,
  or `config-integrity.sh` reports drift. This is deliberate friction; the alternative was six weeks
  of undetected divergence.
- **Adding a rule to `ai/rules/` now requires three edits**: the file, the `setup.sh` link loop, and
  the "Currently linked" line in the template. `check_rule_links` catches a missed link on the next
  config change, but only for the four rules named in the loop — a fifth rule added without
  extending the loop is invisible to the check.
- The drift check excludes blank lines, so whitespace-only divergence is not reported. Intentional;
  it is not drift worth a warning.
- `~/.claude` and `~/.codex/config.toml` remain non-symlinks and still warn in
  `config-integrity.sh`. Pre-existing, out of scope here, and now the only two remaining warnings.
- Running `setup.sh` on this machine changes nothing: all four artifacts exist, so every new block is
  a no-op. The fix is only exercised on a fresh machine — meaning it is **not** end-to-end verified
  here, only unit-verified per check.

## Related

- `decisions/0016-untracked-runtime-claude-settings.md`, `decisions/0018-codex-delegation-and-model-routing.md`,
  `decisions/0019-delegation-rule-is-client-agnostic.md`.
- `setup.sh`, `.claude-global/CLAUDE.md`, `ai/config/codex/hooks.global.base.json`,
  `.claude/hooks/config-integrity.sh`.
