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
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | 48 tests passed |
| `python3 scripts/hook_fixture_runner.py .claude/hooks/pre-tool-gate-v2.sh scripts/fixtures/pretool-gate-v2.json` | not runnable: referenced hook absent from the public branch |
| `python3 scripts/hook_config_check.py .claude/settings.json` | 8 static findings; expected nonzero result |
| `python3 scripts/config_doctor.py --json` | 59 residual findings; 0 missing remediation fields; read-only |
| `python3 -m scripts.config_doctor --live-settings "$HOME/.claude/settings.json" --json` | 59 source findings plus 1 expected runtime-drift; no mutation |
| `python3 scripts/config_generate.py ... --compare-against "$HOME/.claude/settings.json"` | 6 changed JSON paths; hashes only, no target content emitted |
| `python3 scripts/public_hygiene_check.py --json` | 369 findings: 133 absolute paths, 185 private-name matches, 51 private-URL matches |
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

## Tests not yet run

- Full behavior coverage for every registered hook event and matcher.
- Cross-platform macOS/Linux execution of the complete hook fleet.
- Atomic-write, clean-clone, TOML generation, and runtime-wiring tests; the generator
  remains proposal-only JSON and does not write runtime files.
- Permission-versus-hook contradiction tests after a reviewed policy disposition.
- Clean-machine bootstrap and runtime migration verification.
- Full Git-history and out-of-worktree local-overlay exposure review.

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
