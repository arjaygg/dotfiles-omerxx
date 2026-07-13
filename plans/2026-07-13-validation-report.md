# Validation Report — 2026-07-13

## Scope

This report records the Phase 0 baseline and the review-gated Phase 1 test-harness
follow-up on `chore/phase1-hook-validation-tests`. Phase 0 is merged through PR #296;
this report does not authorize live runtime application, instruction-hierarchy, or
live-runtime changes.

Requirement-by-requirement status is tracked in
`plans/2026-07-13-completion-audit.md`.

## Live-apply precondition

The live `~/.claude/settings.json` still resolves to the main checkout, and its
installed `settings-symlink-guard.sh` differs from the Phase 0 branch guard. Applying
the proposal before the branch guard is active would leave the old copy-back behavior
in place and could re-adopt the proposal into the main checkout. No live apply was
performed; branch installation/merge must precede runtime application.

PR [#296](https://github.com/arjaygg/dotfiles-omerxx/pull/296) merged the Phase 0
configuration-boundary changes at `1036a591`. The current test-only follow-up is
published on branch
[`chore/phase1-hook-validation-tests`](https://github.com/arjaygg/dotfiles-omerxx/tree/chore/phase1-hook-validation-tests)
and is tracked by draft PR [#297](https://github.com/arjaygg/dotfiles-omerxx/pull/297).

## Commands and results

| Command | Result |
|---|---|
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | 168 tests passed |
| `python3 scripts/hook_fixture_runner.py .claude/hooks/pre-tool-gate-v2.sh scripts/fixtures/pretool-gate-v2.json` | not runnable: referenced hook absent from the public branch |
| `python3 scripts/hook_config_check.py .claude/settings.json` | 8 static findings; expected nonzero result |
| `python3 scripts/config_doctor.py --json` | 59 residual findings; 0 missing remediation fields; read-only |
| `python3 -m scripts.config_doctor --live-settings "$HOME/.claude/settings.json" --json` | 59 source findings plus 1 expected runtime-drift; no mutation |
| `python3 scripts/config_generate.py ... --compare-against "$HOME/.claude/settings.json"` | 6 changed JSON paths; hashes only, no target content emitted |
| `python3 scripts/public_hygiene_check.py --json` | 329 findings: 118 absolute paths, 161 private-name matches, 50 private-URL matches |
| `git diff --check` | passed |
| Preflight runtime snapshot | `~/.config/dotfiles-ai/backups/2026-07-13-pre-phase0/`; SHA-256 manifest recorded outside Git |
| `git status --short --branch` | isolated Phase 0 branch; clean after commit |

The nonzero scanner and doctor results are expected because they report the unresolved
baseline; they are not hygiene or configuration acceptance passes.

## Phase 1 test-harness follow-up

The follow-up adds static required-field validation for command, HTTP, MCP-tool, prompt,
and agent hook handlers, then extends the fixture contract to cover `ask` decisions,
non-empty reasons, and exact `updatedInput` rewrites. Commits `8906e03` and `424be3c`
touch only `scripts/hook_config_check.py`, `scripts/test_hook_config_check.py`,
`scripts/hook_fixture_runner.py`, and `scripts/test_hook_fixture_runner.py`.
The current settings still produce eight static findings, and live behavior coverage is
not claimed because the referenced `pre-tool-gate-v2.sh` is absent from this branch.

## Phase 2 read-only doctor follow-up

Draft PR [#298](https://github.com/arjaygg/dotfiles-omerxx/pull/298) adds manifest-driven
validation for canonical client bases, rejects missing or unsafe base paths, validates
their declared JSON/TOML format, and makes the direct `scripts/config_doctor.py` entrypoint
work from the repository root. It does not replace tracked-runtime scanning, write files,
or change `setup.sh`; the observed doctor baseline remains 59 issues.

## Phase 2 read-only bootstrap proof

The new `scripts/bootstrap_check.py` renders all six manifest clients twice from tracked
bases using explicit portable placeholder values, validates the generated JSON/TOML via
the existing generator, and emits per-client SHA-256 hashes. It also stages all six
proposals twice in a marked temporary root and verifies `staged_idempotent: true` and
`staged_cache_preserved: true`. The current proof reports six clients, both idempotency
checks true, `temporary_stage_writes: true`, `writes_performed: false`, and
`runtime_writes: false`. It does not alter symlinks, write repository files, authorize
the default `setup.sh` install path, or touch live runtime paths. Actual clean-machine
bootstrap, live cache preservation, and live migration remain unverified.

The manifest loader now rejects duplicate client names, duplicate runtime targets,
unsafe client identifiers, and runtime paths that do not stay beneath the declared
home-relative `~/` form. Focused manifest tests cover these rejection paths; this
hardens proposal generation without changing any runtime target.

The bootstrap proof now also compares all six staged targets through the read-only
`compare_proposals` path and requires `staged_compare_clean: true`. This validates both
JSON and TOML staged output against the proposal without treating staging as a live
installation.

## Transactional staging follow-up

The explicitly marked `ai_config.py stage` path now pre-renders and fsyncs every target
before replacing any destination. When `--replace` is used, backups are created before
replacement and retained on success; a simulated later-target failure restores earlier
replacements and removes temporary backups. This proves the staging transaction's failure
path without touching live runtime paths. Multi-process crash recovery, filesystem-level
durability across power loss, actual clean-machine bootstrap, and live migration remain unverified.
The staging test also places unmanaged cache sentinels under two client directories and
verifies their bytes are unchanged after staging; this is isolated temporary-root evidence,
not proof about caches on a live machine. Staging also rejects symlinked marker, parent,
and target paths before any temporary write, preventing an explicitly marked root from
redirecting output outside itself.

## Phase 4 instruction-budget follow-up

The stacked instruction-budget checker measures lines, words, and bytes deterministically
and reports explicit threshold violations without editing guidance. A current baseline is
`AGENTS.md` 132 lines / 742 words, `CLAUDE.md` 11 / 57, and
`ai/rules/agent-user-global.md` 175 / 1,575; no threshold was exceeded in the baseline
check. The new read-only `scripts/effective_context.py` follows Markdown imports and
client configuration sources, then reports per-client and deduplicated aggregate totals.

For the current branch, repository guidance is 132 lines / 742 words, the Claude chain is
143 / 799, the Codex chain is 307 / 2,317, the Gemini chain is 132 / 742, and the
deduplicated aggregate is 318 / 2,374. All remain under the 400-line / 3,000-word /
20,000-byte budgets. The report also exposes the existing missing `GEMINI.md` reference;
this increment reports it but does not change the canonical hierarchy.

The effective-context command is now a read-only CI check on every pull request.

## Phase 4 always-loaded compliance follow-up

The new `scripts/instruction_compliance.py` checks the always-loaded entrypoints for
dated current-state sections, transient session markers, absolute user paths, and
session-memory headings. The reviewed baseline contains one existing
`memory-section` finding in `.gemini/GEMINI.md`; no instruction files were changed.
CI compares exact structured findings and fails on new or disappearing debt, providing
compliance-regression evidence without asserting that the existing finding is resolved.

## Phase 5 dead-reference follow-up

The new `scripts/dead_reference_check.py` scans canonical command documentation for
explicit local `scripts/...` references and checks Claude command/skill distribution
symlinks without following them. The current scan has no missing command-script
references or broken distribution links; the 14 stale links to absent private skills
were removed. The empty reviewed baseline is stored in
`scripts/fixtures/dead-reference-baseline.json`; CI fails on any new finding.

## Phase 1/5 file-backed hook reference follow-up

The new `scripts/hook_reference_check.py` extracts `$HOME/.dotfiles` file-backed command
references from `.claude/settings.json` and checks them against the tracked distribution.
The current scan finds no missing references, so `scripts/fixtures/hook-reference-baseline.json`
is intentionally empty. Runtime command strings such as `lean-ctx hook redirect` are not
treated as file paths; this check does not prove matcher reachability, ordering, or runtime
execution on every platform.

## Phase 1 representative hook-event matrix follow-up

The new `scripts/hook_event_matrix.py` validates one representative, required-key-checked
payload for each of the 14 configured hook events. The PreToolUse case uses an
`mcp__pctx__execute_typescript` tool name so MCP-shaped input is represented explicitly.
This is a maintained payload/schema inventory only: it does not invoke hooks, test matcher
reachability, establish ordering, or prove macOS/Linux runtime behavior.

## Phase 5 permission/hook conflict follow-up

The stacked checker reports exact permission contradictions and exact tool-hook matchers
covered by a permission deny. The current `.claude/settings.json` produced zero exact
conflicts. An opt-in `--include-overlaps` mode now reports 62 potential overlaps for
review, while skipping alternation/regex-like matchers rather than guessing semantics.
The overlap mode is not a blocking CI check and does not claim declaration ordering or
runtime behavior.

## Phase 5 CI validation follow-up

The new `.github/workflows/ai-policy-validation.yml` runs the maintained Python tests,
the maintained pre-tool fixture runner, the explicit instruction budgets, and the exact
permission/hook conflict checker on every PR layer. A matrix runs the same read-only job
on `ubuntu-latest` and `macos-latest`. It has read-only repository permissions and parses
its own YAML with pinned `PyYAML==6.0.2`. It does not run runtime diff, setup, migration,
or unresolved baseline hygiene scanners as blocking checks. Draft PR
[#316](https://github.com/arjaygg/dotfiles-omerxx/pull/316) now represents
`ci/shellcheck-baseline`; no hosted CI pass is claimed yet because its checks
were still pending at PR creation time.

## Reviewed hook-configuration baseline follow-up

The read-only `hook_config_check.py --baseline` mode now records the eight known findings
in `scripts/fixtures/hook-config-baseline.json` and fails when a new finding appears or a
reviewed finding disappears unexpectedly. This makes unsupported matchers and parallel
worktree handlers visible as explicit debt without changing the current settings or
pretending that those findings are resolved. The baseline comparison and malformed-entry
handling are covered by unit tests; the CI workflow runs the comparison on each PR.

## Shell syntax validation follow-up

The read-only `scripts/shell_syntax_check.py` validator runs `bash -n` over the governed
Claude, Codex, Cursor, Gemini, and support-script shell trees. The current inventory is 88
`.sh`/`.bash` files and passes locally; the validator is now a blocking CI step. This is
syntax coverage only and does not claim ShellCheck, shfmt, runtime portability, or hook
behavioral coverage.

## shfmt baseline follow-up

The CI matrix installs pinned `shfmt` and compares the 88-file governed shell fleet
against `scripts/fixtures/shfmt-baseline.json`. The current baseline records 78
unformatted files without rewriting them; this is a formatting no-regressions gate,
not a claim that the existing formatting debt is resolved.

## ShellCheck baseline follow-up

The read-only `scripts/shellcheck_check.py` runner scans the same governed shell inventory
with `--severity error` and compares structured findings against
`scripts/fixtures/shellcheck-baseline.json`. The current 88-file scan has one known
SC2259 finding in `.cursor/hooks/before-shell-git-commit.sh`; the baseline matches with
no added or removed findings. CI requires ShellCheck and fails on drift. The finding is
not fixed in this increment because changing hook behavior remains a separate review.

## Maintained hook fixture contract follow-up

The maintained `scripts/hook_fixture_runner.py` now validates the declared hook event,
expected exit code, and either an explicitly empty stdout contract or one structured
decision. It still requires non-empty decision reasons and exact object-shaped rewrites,
and it rejects rewrite fixtures that drop original tool-input keys. The manifest adds a
malformed-payload, sensitive hash-file denial, and safe pipe-rewrite cases; ten PreToolUse
fixtures pass locally. This is fixture-level evidence for the current gate only, not proof of every
registered event, matcher, platform, or runtime hook ordering.

## Read-only setup modes

`setup.sh --dry-run` now emits the six-client proposal bundle and returns before any
directory, package, Stow, or symlink operation. `setup.sh --check` delegates to the
read-only doctor and preserves its nonzero result when findings exist. Both modes are
covered by subprocess tests; the default `setup.sh` install path is unchanged and remains
review-gated.

## Clean tracked-archive proposal check

`scripts/clean_clone_check.py` archives the current tracked revision into an isolated
temporary directory, validates that every extracted link stays inside the archive, and
runs `setup.sh --dry-run` with an isolated `HOME`. The check verifies all six manifest
clients, returns `runtime_writes: false`, and passed locally with zero skipped links.
The four tracked absolute Cursor rule links were converted to repository-relative links;
full clean-machine installation and runtime migration remain unverified.

## Self-improvement command reference follow-up

`ai/commands/evolve.md` no longer points at the absent `continuous-learning-v2` CLI.
It now describes review-only guidance, points to the repository-side proposal validator,
and explicitly forbids inferred plugin paths or canonical-policy mutation. A regression
test checks the stale path and preserves the proposal-only boundary; no learning data or
policy files are auto-generated.

The proposal validator now requires `review_after` to be either a valid ISO date or an
explicit `condition:<description>`, making revalidation/expiry metadata machine-checkable
without promoting or applying the proposal.

The new read-only `policy_proposal.py review` command compares explicitly supplied numeric
baseline and candidate metric artifacts, reports deltas, and always emits
`decision: review-required` with `auto_promote: false`. It does not collect transcripts,
write proposals, or infer whether a metric is better; human review remains required.

The explicit `policy_decision.py` command records human accept/reject/defer outcomes in a
caller-selected JSONL ledger using only the proposal ID, SHA-256, rationale, dates, and an
`applied: false` marker. It appends atomically, rejects invalid proposals, and never writes
canonical policy or raw evidence. The ledger path is intentionally explicit and should be
kept outside the public repository when it contains private review rationale.
The decision boundary now rejects an `accept` recorded after a proposal's dated
`review_after` deadline; reject/defer outcomes remain recordable for audit purposes,
and condition-based review dates remain human-review gates. This prevents stale
proposals from being accepted without revalidation while preserving the no-apply rule.
Before appending, the ledger now validates every existing entry's required fields,
decision enum, hash shape, dates, human attribution, and `applied: false` invariant;
malformed or already-applied history is rejected rather than silently extended.
Proposals now require a bounded portable `owner`; review reports and decision entries
carry that owner forward so expiry review has explicit accountability without storing
raw evidence.
The new `policy_decision.py --gate-review` path joins a valid review report to the
latest matching human decision and dated expiry. It reports eligibility only when the
decision is current and accepted, always emits `auto_apply: false`, and never writes
policy or the decision ledger.
Proposal validation is now closed-schema: only declared required fields and the two
explicitly false-by-default promotion flags are accepted; unknown fields are rejected.

## Phase 3 traceable signal intake

The new `scripts/learning_signal.py` validates an enumerated signal type, timezone-aware
timestamp, evidence class, and recurrence count, then hashes session/event/recurrence
references before atomically appending metadata to a caller-selected ledger outside the
repository. Raw transcripts, prompts, outputs, private context, and unknown fields are
rejected. Every record carries `raw_evidence_stored: false`, `auto_promote: false`,
`promotion_status: review-required`, and `applied: false`; duplicate IDs are refused.
The `--summarize` mode groups sanitized records by signal type and hashed recurrence key,
counts independent sessions, and marks candidates as threshold-met only after two sessions
or strong evidence. It emits review-only candidate summaries without creating proposals;
runtime hook collection, baseline evaluation, and promotion remain unimplemented and
review-gated.

## Public-hygiene no-regressions baseline

The remaining broad cleanup is deferred: the current tracked tree has 329 findings
(118 absolute-home paths, 161 private-organization names, and 50 private URLs).
`scripts/fixtures/public-hygiene-baseline.json` stores only the count and a SHA-256
fingerprint of `(path,line,rule)` keys, avoiding a second copy of sensitive excerpts.
The policy workflow compares that fingerprint on Linux and macOS and fails on any
addition or disappearance; this is a no-regressions gate, not a claim that the debt is
resolved. The scanner inspects symlink payloads without following links into another
checkout, making the baseline deterministic.

The same read-only Linux/macOS matrix now executes `bash setup.sh --dry-run` directly.
This exercises proposal-only setup without invoking the default install or symlink path;
live runtime application remains deferred.

The read-only configuration doctor now has the same privacy-safe baseline contract:
the current 59 source issues are represented by a `(path,rule,severity)` fingerprint
in `scripts/fixtures/config-doctor-baseline.json`. CI fails on doctor-debt drift while
live-settings comparison remains a separate review-gated operation.

## Tests not yet run

- Full behavior coverage for every registered hook event and matcher; the maintained
  runner currently exercises ten PreToolUse cases and the matrix inventories all 14 events.
- Hosted cross-platform macOS/Linux execution; the workflow matrix is configured but has
  no recorded run until the branch is represented by a PR.
- Full clean-machine bootstrap and runtime-wiring tests; the tracked-archive proposal
  check passes with zero skipped links, but the path remains proposal-only.
- Wildcard/regex permission-versus-hook contradiction tests and runtime confirmation.
- Intentional hook-configuration baseline cleanup and ordering changes; those remain
  review-gated because they would alter current hook behavior.
- Clean-machine bootstrap and runtime migration verification.
- Full Git-history and out-of-worktree local-overlay exposure review.
- Runtime wiring that emits signals from hooks, PR systems, or session telemetry; the
  current recorder requires an explicit input file and external ledger path.

The legacy shell harness remains incomplete: its last run produced 0 passes, 0 failures,
and 8 skips because two referenced hooks are absent. The maintained fixture runner is
therefore the only current multi-case runtime evidence for the pre-tool gate.

## Residual risks

1. Broad permission allows remain for separate permission review.
2. Portable JSON proposal bases now cover Claude, Gemini, Cursor, Windsurf, and PCTX;
   Codex/TOML generation and runtime wiring remain Phase 2 work.
3. Six configured matchers are ignored for their event types; two worktree groups have
   multiple handlers whose ordering must not be assumed.
4. Public-repository hygiene is not clean; every finding still needs a reviewed
   portable-source, fixture, history, or sensitive-data disposition.

## Review-gated migration sequence

1. Completed: snapshot live runtime settings and checksums outside Git; exclude secrets
   and transcripts from all repository artifacts.
2. Review the Phase 0 branch diff and proposal output.
3. Create any remaining sanitized tracked bases plus ignored identity, path, work-context, and secret
   overlays; generate proposal-only diffs first.
4. Validate schemas, privacy rules, secret rules, atomicity, and idempotency.
5. Apply only the approved migration, then verify runtime behavior and a clean repeated
   `git diff`.
6. Re-run this report's checks and document rollback results before Phase 1 behavior
   changes.

## Gate

Human review is required before changing permission semantics, machine-wide hooks, the
canonical instruction hierarchy, or live runtime configuration.
