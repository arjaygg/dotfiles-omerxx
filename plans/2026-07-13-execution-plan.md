# Execution Plan — Portable, Governed AI Configuration

## Scope and sequencing

Implement one phase per reviewable stack branch. Each phase must pass its acceptance
criteria before the next phase starts. No phase may weaken an existing hard-deny or
permission boundary; policy changes require human approval.

## Phase 0 — privacy and configuration boundaries

**Files:** `.claude/settings.json`, `.claude/hooks/settings-symlink-guard.sh`,
`setup.sh`, `.gitignore`, new `ai/config/` templates/overlays, privacy-test fixtures.

**Accepts:** a clean clone has no organization-specific runtime context or user paths;
runtime edits do not write back to tracked source; generation from base plus ignored
overlays is deterministic, idempotent, atomic, and secret-safe.

**Safe progress:** `scripts/public_hygiene_check.py` and its five-case unittest suite
now provide a deterministic baseline scanner. It currently reports 386 findings on
the tracked source, so the phase remains incomplete.

**Additional safe progress:** `scripts/config_doctor.py` provides a read-only doctor
for tracked client configs and reports 61 current issues without mutating files.

1. Classify every organization/path/secret match as portable source, fixture,
   historical record, work context, or sensitive data; preserve only intentional
   examples and scrub or relocate the rest.
2. Remove the bypass-permission default and separate portable base settings from
   ignored identity, path, work-context, and secret overlays.
3. Replace `settings-symlink-guard.sh` copy-back with detect-and-report/proposal-only
   behavior; preserve a manual migration and rollback path.
4. Add one generator/check interface following existing `setup.sh` conventions. It
   must validate JSON/TOML/YAML, reject secrets and absolute user paths in templates,
   write atomically, and leave `git diff` clean on repeat runs.
5. Add deterministic privacy, secret, idempotency, and migration tests.

## Phase 1 — deterministic hook architecture

**Files:** `.claude/settings.json`, `.claude/hooks/`, hook fixture/test harness,
`ai/rules/` only where the verified ownership boundary requires documentation.

**Accepts:** every governed matcher is reachable and tested; hard security checks run
before contextual checks; each invocation emits one valid decision; blocking and
rewriting are proven by observed behavior; analytics is off the synchronous path.

**Verified baseline:** the official hooks reference confirms parallel handler
execution and ignored matchers on several current event types; the tracked settings
contain six such unsupported matchers and two-handler worktree groups. No hook code has
been changed yet.

1. Capture representative payloads for PreToolUse, PostToolUse, UserPromptSubmit,
   SessionStart, Stop, PreCompact, ConfigChange, worktree, and MCP calls.
2. Validate the current hook schema and exit semantics on macOS and Linux-compatible
   shells; test allow, ask, deny, rewrite, malformed payload, missing dependency,
   sensitive path, branch safety, and large output cases.
3. Consolidate ordering-sensitive PreToolUse logic behind one dispatcher only where
   evidence proves shared mutation or ordering dependence; do not refactor unrelated
   hooks.
4. Keep permissions as the hard boundary, hooks as contextual validation/rewrite, and
   post-tool analytics asynchronous or PostToolUse-only.

## Phase 2 — portable multi-client generation

**Files:** `ai/config/`, `setup.sh`, `.codex/`, `.gemini/`, `.cursor/`, `.windsurf/`,
PCTX templates and schema/doctor tests.

**Accepts:** a clean machine bootstraps all supported clients from tracked bases plus
ignored local/work overlays; drift is reported rather than adopted; repeated runs are
idempotent and preserve user-managed caches.

## Phase 3 — governed self-improvement

**Files:** continuous-learning/evolution skills, proposal schema, evaluation harness,
review-only branch/PR automation, decisions documentation.

**Accepts:** signals become traceable proposals only; recurrence/evidence thresholds,
conflict analysis, baseline-vs-candidate evaluation, owner/review expiry, and rejected
proposal memory are implemented. No process edits or merges canonical policy silently.

## Phase 4 — instruction-cost reduction

**Files:** `AGENTS.md`, root `CLAUDE.md`, `ai/rules/`, scoped skills, instruction-size
checks.

**Accepts:** always-loaded layers contain only stable invariants and repository facts;
specialized procedures load on demand; size budgets and compliance evals show no
regression.

## Phase 5 — ongoing governance

**Files:** CI workflows, shell/JSON/TOML/YAML validators, symlink and dead-reference
checks, hook fixtures, portability/privacy scanners.

**Accepts:** CI and local doctor share validators and fail on invalid policy/config,
unsupported matchers, malformed updatedInput, stdout contamination, privacy leaks,
conflicting permissions/hooks, dead references, and instruction-budget regressions.

## Migration, rollback, and review gates

- Before Phase 0, snapshot live runtime settings outside Git and record checksums;
  never commit secrets or raw transcripts.
- Generate proposal-only diffs first; apply runtime changes only after explicit review.
- Keep the old distribution path available until a clean-machine bootstrap and a
  repeated idempotency run pass.
- Roll back by restoring the prior runtime backup and reverting the phase commit; do
  not use destructive reset/clean commands.
- Stop for human review before changing permission semantics, machine-wide hooks,
  canonical instruction hierarchy, or live runtime configuration.

## Immediate next step

Review this report and plan, then approve a dedicated Phase 0 implementation branch.
The current branch contains audit documentation plus read-only validation tooling; it
does not silently apply the high-impact safety or runtime-configuration changes
identified above.
