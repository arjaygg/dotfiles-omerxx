# Verified Architecture and Risk Report — 2026-07-13

## Goal

Establish a current, evidence-backed baseline before changing the dotfiles control
plane. This report covers the requested safety, portability, configuration-boundary,
hook, and self-modification audit; it does not authorize behavior-changing fixes.

## Verified current state

- Repository: `.dotfiles`; working branch is the isolated
  `chore/phase0-config-boundary` worktree, based on the audit branch.
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

The risks below describe the pre-approval audit baseline. Current Phase 0 branch
resolutions are recorded in the implementation update below; remaining risks are not
silently considered accepted.

## Approved Phase 0 implementation update

- Removed `skipDangerousModePermissionPrompt` and the organization-specific `autoMode`
  environment block from `.claude/settings.json`; the file remains valid JSON and
  passes the hygiene scanner in isolation.
- Replaced the settings symlink guard's runtime-to-source adoption with a read-only
  warning path. Valid and invalid severed runtime files remain unchanged, and intact
  symlinks remain untouched.
- Removed `.claude/settings.local.json` from Git's index while preserving the local
  working-tree file and existing ignore rule.
- Added `ai/config/claude/settings.base.json`, a portable sanitized snapshot, an
  overlay example, and `scripts/config_generate.py`. The generator deep-merges JSON,
  rejects privacy/secret findings, and prints proposals without writing files.
- Added boundary and generator tests. The full Python suite now passes 34 tests.
- Current branch recheck: 368 hygiene findings (185 organization names, 132 absolute
  paths, 51 organization URLs); doctor reports 59 findings, all from residual path,
  organization, and blanket-permission data outside the approved boundary changes.

No live runtime file, canonical instruction hierarchy, broad permission allow, or
ordering-sensitive Phase 1 hook was changed.

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
passes its tests and an earlier baseline recorded 386 findings (absolute paths and
private organization markers); this is evidence for the required cleanup, not a claim that
public-repository hygiene is complete.

The audit baseline recorded 388 findings. The Phase 0 branch recheck now reports 368
findings — 185 organization-name matches, 132 absolute-home-path matches, and 51
organization-URL matches. These counts guide
classification; they are not permission to delete historical plans or evaluation
fixtures without a reviewed disposition.

Added a proposal-only `scripts/config_doctor.py`. It validates the tracked JSON/TOML
client configs, reuses the privacy rules for config files, detects the tracked
`skipDangerousModePermissionPrompt` bypass, and detects live-settings copy-back in the
symlink guard without writing files. Its eight-test combined suite passes. The current
doctor baseline was 68 issues. The Phase 0 branch now reports 59 residual issues: 26
absolute-path findings, 27 organization-name findings, and six
`blanket-permission-allow` errors; the bypass, tracked-overlay, and runtime-copyback
findings are resolved on this branch.

## Hook-schema verification update

The current Claude Code hooks reference documents that matching hook handlers execute
in parallel, that `matcher` is ignored for `UserPromptSubmit`, `Stop`, `TaskCreated`,
`TaskCompleted`, `WorktreeCreate`, and `WorktreeRemove`, and that tool matchers use
exact-string or JavaScript-regex semantics depending on their characters. See the
[official hooks reference](https://code.claude.com/docs/en/hooks).

Against that reference, the tracked settings contain six matcher fields on those
matcher-unsupported events, plus two handlers each for `WorktreeCreate` and
`WorktreeRemove`. This is a confirmed configuration risk: the six filters do not scope
execution as their authors appear to intend, and the two-handler worktree groups must
not be assumed to run sequentially. Runtime fixture tests are still required to prove
actual blocking, rewriting, and exit-code behavior.

Added `scripts/hook_config_check.py`, a read-only validator for event names, group and
handler structure, unsupported matchers, and parallel worktree handlers. The combined
12-test suite passes. Running it against the tracked settings reports eight static
issues: six ignored matchers and two parallel-handler warnings. It intentionally does
not claim runtime reachability or blocking correctness; fixture execution remains the
next Phase 1 evidence step.

The existing `.claude/hooks/test-hook.sh --all` harness was also executed. It produced
0 passes, 0 failures, and 8 skips because its fixtures reference missing
`edit-without-read.sh` and `serena-tool-priority.sh` hooks. This is direct evidence
that the current fixture suite cannot validate the live hook set; it must be repaired
or replaced before claiming hook behavior coverage.

Added three runtime tests for `scratchpad-reread-guard.sh`: the first Read is silent,
the second produces a schema-valid `PreToolUse` deny, and non-Read tools are ignored.
The combined validation suite now passes 15 tests. This proves one narrow hook path
only; it does not generalize to the rest of the hook fleet.

As an additional read-only runtime check, the seven archived `pre-tool-gate-v2`
fixtures were piped directly into the current gate: two allowed cases passed silently
and five blocked cases emitted JSON `PreToolUse` denies with exit code 0. The fixture
filenames still encode `.exit1`, so the archived harness expectations are stale relative
to the current blocking contract; the observed behavior matches the hook's documented
JSON-decision path. This evidence is useful but does not replace a maintained current
fixture suite.

Added a maintained Python fixture runner and seven-case manifest for the current
`pre-tool-gate-v2.sh`. It asserts both silent allows and schema-valid JSON denies; the
runner passes all seven cases. The old shell harness remains unchanged and still has
stale archived expectations, so both results are recorded rather than conflated.

Extended the doctor with read-only source/runtime drift detection. A live-settings
comparison must be rerun after this branch's source changes; no live file was copied,
linked, or modified by the Phase 0 implementation.

The doctor now attaches remediation guidance to every issue and exposes it in both
human-readable and JSON output. Verification found 59 issues with zero missing
remediation fields; this improves proposal quality without applying any fix.

Added an explicit `.gitignore` entry for future `.claude/settings.local.json` files.
The Phase 0 branch now leaves the existing local file in place but removes it from the
Git index; the doctor no longer reports a tracked-overlay finding.

Added `plans/2026-07-13-phase0-classification.md`, which maps the scanner findings to
portable base templates, ignored local/work overlays, sanitized fixtures, or human
review. It specifically identifies tracked `.claude/settings.local.json`, Codex trust
lists, MCP binary paths, organization-specific skills, and historical work context;
it does not delete or rewrite any of them.

## Recommendation

Review the Phase 0 branch diff and validation output. Keep live runtime application,
permission-rule changes, canonical hierarchy changes, and Phase 1 ordering work as
separate explicitly approved steps.
