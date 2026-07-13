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

The current committed baseline was subsequently rechecked after the scanner landed:
390 findings remain — 196 organization-name matches, 141 absolute-home-path matches,
and 53 organization-URL matches. The largest source areas are `ai/` (114), `.claude/`
(79), `plans/` (48), `.codex/` (45), and `.gemini/` (26). These counts guide
classification; they are not permission to delete historical plans or evaluation
fixtures without a reviewed disposition.

Added a proposal-only `scripts/config_doctor.py`. It validates the tracked JSON/TOML
client configs, reuses the privacy rules for config files, detects the tracked
`skipDangerousModePermissionPrompt` bypass, and detects live-settings copy-back in the
symlink guard without writing files. Its eight-test combined suite passes. The current
doctor baseline is 62 issues: 59 warnings for config privacy/path findings and three
errors (`unsafe-bypass`, `tracked-local-overlay`, and `runtime-copyback`).

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

Extended the doctor with read-only source/runtime drift detection. The live
`~/.claude/settings.json` currently resolves to the main checkout; comparing it with
this branch's tracked settings produced no `runtime-drift` issue. The doctor still
reports the same 62 source issues. No file was copied, linked, or modified.

Added `plans/2026-07-13-phase0-classification.md`, which maps the scanner findings to
portable base templates, ignored local/work overlays, sanitized fixtures, or human
review. It specifically identifies tracked `.claude/settings.local.json`, Codex trust
lists, MCP binary paths, organization-specific skills, and historical work context;
it does not delete or rewrite any of them.

## Recommendation

Do not begin broad Phase 0/1 implementation in the same change as this report. First
review the execution plan below, then handle the tracked unsafe settings and
settings-symlink adoption behavior in a dedicated, explicitly approved safety branch.
