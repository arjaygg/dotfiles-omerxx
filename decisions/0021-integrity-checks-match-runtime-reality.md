# 0021 — Integrity checks assert the actual config topology, not an idealised one

**Status:** Accepted
**Date:** 2026-08-03
**Extends:** `decisions/0016-untracked-runtime-claude-settings.md`,
`decisions/0020-user-global-instruction-durability.md`
**Relates to:** `decisions/0018-codex-delegation-and-model-routing.md` (the pinned coordinator tier
this now guards)

## Decision

Replace two `config-integrity.sh` checks that asserted a topology this machine does not and should
not have, and add one that guards a value that actually matters:

- **Removed:** `check_symlink ".claude → dotfiles"`. `~/.claude` is a real directory of 58 entries,
  almost all Claude Code runtime state (`audit.log`, `bg-jobs`, `cache`, `daemon`, `debug`,
  `file-history`, `todos`, `shell-snapshots`). Replaced by per-entry symlink checks for the five
  config entries that genuinely are links: `agents`, `commands`, `output-styles`, `plugins`,
  `claude-statusline`. `hooks/` and `skills/` are real directories too and are not checked.
- **Removed:** `check_symlink ".codex/config.toml"`. Codex writes that file itself — `[hooks.state]`
  `trusted_hash`, `[notice.model_migrations]`, `[tui.model_availability_nux]`. A symlink into the
  repo would dirty the tree on every session, which is 0016's reasoning verbatim.
- **Added:** `check_codex_coordinator_model` — compares only the `model` key between live and
  tracked `.codex/config.toml`.
- **Fixed as part of this:** tracked `.codex/config.toml` pinned `model = "gpt-5.5"` /
  `model_reasoning_effort = "high"` while the live config ran `gpt-5.6-sol` / `medium` /
  `model_provider = "headroom"`. Tracked values updated.
- **Documented:** `ai/rules/lean-ctx.md` is dormant — linked into no client's rules directory, so it
  never loads; recorded in `tool-priority.md`'s precedence note, since the file itself is generated
  and edits to it are discarded.

## Why

Both removed checks had warned continuously for long enough to be treated as background noise. That
is the real cost: a checker that always warns trains its reader to ignore it, so the two warnings
worth acting on this session were sitting underneath two that were not.

Neither warning was fixable as written. Making `~/.claude` a symlink into the repo would require the
repo to absorb every session transcript, cache entry and daemon log. Making `~/.codex/config.toml` a
symlink would produce a dirty tree after every Codex session. The checks asserted an idealised
topology and the correct response was always going to be to leave them warning — which is a checker
defect, not a config defect.

Removing them would have lost real coverage, so both were narrowed to what is genuinely assertable:
the five entries that are supposed to be links, and the one key in `config.toml` that carries policy.

That narrowing immediately earned itself: the coordinator-tier check found that the tracked config
still pinned `gpt-5.5` while ADR 0018 documents `gpt-5.6-sol` as the pinned coordinator. **A rebuild
would have silently demoted the coordinator to a weaker model**, and nothing would have reported it —
the whole-file symlink check could not see it, because the whole file legitimately differs in 268
lines of runtime state.

## Alternatives rejected

- **Delete both checks outright:** rejected — loses coverage of the five entries that really are
  links, and of the coordinator tier.
- **Keep the whole-file `config.toml` comparison instead of a single key:** rejected — 268 diff
  lines, nearly all runtime state. It would warn permanently, recreating the problem this ADR fixes.
- **Make the whole-directory and whole-file symlinks real, so the original checks pass:** rejected —
  see Why. Both are actively harmful.
- **Suppress the warnings without changing the checks:** rejected — the state was fine and the
  assertion was wrong; suppressing hides that inversion instead of correcting it.
- **Add a note to `ai/rules/lean-ctx.md` saying it is dormant:** rejected — the file is generated
  (`<!-- lean-ctx-rules-vN -->`), so the note would be discarded on regeneration. Same reason
  `tool-priority.md` §5 exists.
- **Link `lean-ctx.md` so the reference stops looking dangling:** rejected — it would add a rule to
  every session for guidance `tool-priority.md` already supersedes, and the MCP server already
  injects it.

## Consequences

- `config-integrity.sh` now reports **zero** issues on this machine. Any future warning is signal.
  That is the point, and it is also fragile in a specific way: if a warning becomes routine again,
  the fix is to narrow the check, not to tolerate the noise.
- The coordinator tier must be kept in sync across three places — `~/.codex/config.toml` (live),
  `.codex/config.toml` (tracked), and `model-routing/SKILL.md` § Codex. The check covers the first
  two; the third is prose and unguarded.
- The per-entry `.claude` loop is a hardcoded list. A sixth config entry added to `.claude/` without
  extending the loop is unchecked — the same class of limitation as `check_rule_links` in 0020.
- `hooks/` and `skills/` under `~/.claude` are deliberately unchecked. They are real directories on
  this machine and it is not established whether they should be links.
- Deleted four orphaned backups found alongside this work: `~/.claude/rules/lean-ctx.md.bak`,
  `lean-ctx.md.lean-ctx.bak`, `~/.claude/CLAUDE.md.bak`, `CLAUDE.md.lean-ctx.bak`. The last was byte-
  identical in size to the stale `.claude-global` copy 0020 replaced.

## Related

- `.claude/hooks/config-integrity.sh`, `.codex/config.toml`, `ai/rules/tool-priority.md`.
- `decisions/0016`, `decisions/0018`, `decisions/0020`.
