# Verified Architecture and Risk Report — 2026-07-13

## Goal

Establish a current, evidence-backed baseline before changing the dotfiles control
plane. This report covers the requested safety, portability, configuration-boundary,
hook, and self-modification audit; it does not authorize behavior-changing fixes.

## Verified current state

- Repository: `/Users/axos-agallentes/.dotfiles`; working branch is the isolated
  `chore/add-scratchpad-compaction-rule` worktree, based on `origin/main`.
- Open-PR check: Graphify reported **0 open PRs targeting `main`**.
- The tracked source contains `ai/`, tool adapters, `setup.sh`, hooks, plans, and
  decisions, matching the intended multi-agent control-plane shape.
- `.claude/settings.json` parses as valid JSON and registers 14 hook event classes.
- The requested scratchpad rule is already present in ancestor commit `919f8e3`:
  scratchpad files are write-mostly and should not be re-read after compaction unless
  needed again in the same step.
- `plans/pctx-functions.md` was refreshed against the live `mcp__pctx__list_functions`
  result; live namespaces are Serena, Qmd, LeanCtx, Repomix, and Graphify.

## Confirmed risks

### P0/P1 — public-repository boundary is not clean

The repository-wide search returned 109 matches across 371 files for organization
names, Azure DevOps URLs, user-specific paths, and work-context markers. Examples
include `ai/skills/ado-workitem/SKILL.md`, `ai/agents/claude-code-review-agent.md`,
`opencode/agent/mcp_config_manager.md`, `nushell/env.nu`, and historical `plans/`
artifacts. Some may be intentional examples or migration history, but a fresh clone
does not currently prove the required portable/public boundary.

### P0 — tracked runtime settings contain machine and organization context

`.claude/settings.json` contains `skipDangerousModePermissionPrompt: true`,
`model: "sonnet"`, a broad `permissions` section, local service configuration, and
organization-specific environment entries. This is tracked source, not an ignored
machine-local overlay. The setting bypasses a safety prompt and must not be retained
without an explicit, reviewed decision.

### P0 — runtime settings can mutate canonical tracked source

`.claude/hooks/settings-symlink-guard.sh` unconditionally runs `cp "$LIVE" "$SRC"`
after validating only JSON syntax, then restores the symlink. This silently adopts
live Claude settings into `~/.dotfiles/.claude/settings.json`, including permission,
model, plugin, and work-context changes. It directly violates proposal-only drift
handling and can reintroduce unsafe settings after manual cleanup.

### P1 — generation boundary is incomplete

`setup.sh` distributes configuration through symlinks/Stow, but the current evidence
does not show a deterministic `--dry-run`, `--check`, `generate`, `diff`, or `doctor`
interface, schema validation, atomic generation, backup policy, or idempotency test.
These capabilities must be verified before redesigning the distribution flow.

### P1 — portability debt is demonstrable

The search found absolute `/Users/axos-agallentes/...` paths in tracked guidance,
runtime/config examples, and hook-related artifacts, plus `/Users/omerxx/...` in
`nushell/env.nu`. This is incompatible with a fresh clone on another machine unless
each occurrence is intentionally classified as fixture, migration history, or
portable source.

## False/stale or not-yet-proven findings

- “No scratchpad rule exists” is stale: the rule is already in `919f8e3`.
- “No MCP function inventory exists” is stale: `plans/pctx-functions.md` records the
  current live inventory, including the Qmd and LeanCtx schemas.
- The presence of hook names in settings does **not** prove ordering, blocking, input
  rewrite, or schema correctness; runtime behavior still requires fixtures.
- Search matches alone do not prove every occurrence is a privacy violation; each file
  needs classification before deletion or templating.

## Checked / not yet checked

**Checked:** branch/worktree state, open PRs, tracked tree, settings JSON validity and
selected safety fields, hook event registration, symlink-guard source, `.gitignore`,
tracked absolute-path/organization matches, live pctx function inventory, and the
existing scratchpad-rule commit.

**Not yet checked:** live Claude hook response schema against fixtures; matcher reachability;
parallel mutation races; all hook exit statuses; every tool adapter's portability;
runtime symlink state; generated-config idempotency; Codex,
Gemini, Cursor, Windsurf, and PCTX schema validation; full Git history exposure; and
whether local-only overlays already exist outside this worktree.

## New safe-phase progress

Added `scripts/public_hygiene_check.py` with five deterministic rules for tracked UTF-8
files: absolute home paths, private organization URLs/names, secret assignments, and
private-key material. Five `unittest` cases cover clean portable text, each finding
class, redacted placeholders, private keys, and tracked-file filtering. The scanner
passes its tests and reports 386 current baseline findings (absolute paths and private
organization markers); this is evidence for the required cleanup, not a claim that
public-repository hygiene is complete.

## Recommendation

Do not begin broad Phase 0/1 implementation in the same change as this report. First
review the execution plan below, then handle the tracked unsafe settings and
settings-symlink adoption behavior in a dedicated, explicitly approved safety branch.
