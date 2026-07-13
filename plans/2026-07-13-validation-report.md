# Validation Report — 2026-07-13

## Scope

This report records read-only validation for the Phase 0/1 control-plane audit on
`chore/add-scratchpad-compaction-rule`. It does not authorize permission, hook,
instruction-hierarchy, or live-runtime changes.

## Commands and results

| Command | Result |
|---|---|
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | 22 tests passed |
| `python3 scripts/hook_fixture_runner.py .claude/hooks/pre-tool-gate-v2.sh scripts/fixtures/pretool-gate-v2.json` | 7 passed, 0 failed |
| `python3 scripts/hook_config_check.py .claude/settings.json` | 8 static findings; expected nonzero result |
| `python3 scripts/config_doctor.py --json` | 68 findings; 0 missing remediation fields; read-only |
| `python3 scripts/public_hygiene_check.py --json` | 388 findings: 140 absolute paths, 195 private-name matches, 53 private-URL matches |
| `git diff --check` | passed |
| `git status --short --branch` | clean worktree on the isolated audit branch |

The nonzero scanner and doctor results are expected because they report the unresolved
baseline; they are not hygiene or configuration acceptance passes.

## Tests not yet run

- Full behavior coverage for every registered hook event and matcher.
- Cross-platform macOS/Linux execution of the complete hook fleet.
- Generator schema, atomic-write, idempotency, and clean-clone tests; no generator has
  been introduced yet.
- Permission-versus-hook contradiction tests after a reviewed policy disposition.
- Clean-machine bootstrap and runtime migration verification.
- Full Git-history and out-of-worktree local-overlay exposure review.

The legacy shell harness remains incomplete: its last run produced 0 passes, 0 failures,
and 8 skips because two referenced hooks are absent. The maintained fixture runner is
therefore the only current multi-case runtime evidence for the pre-tool gate.

## Residual risks

1. Tracked settings still contain an unsafe bypass default and broad permission allows.
2. The settings symlink guard still adopts live settings into tracked source.
3. A machine-local settings overlay remains tracked, despite a future-file ignore rule.
4. Six configured matchers are ignored for their event types; two worktree groups have
   multiple handlers whose ordering must not be assumed.
5. Public-repository hygiene is not clean; every finding still needs a reviewed
   portable-source, fixture, history, or sensitive-data disposition.

## Review-gated migration sequence

1. Snapshot live runtime settings and checksums outside Git; exclude secrets and
   transcripts from all artifacts.
2. Approve the Phase 0 disposition matrix and permission/runtime ownership boundaries.
3. Create sanitized tracked bases plus ignored identity, path, work-context, and secret
   overlays; generate proposal-only diffs first.
4. Validate schemas, privacy rules, secret rules, atomicity, and idempotency.
5. Apply only the approved migration, then verify runtime behavior and a clean repeated
   `git diff`.
6. Re-run this report's checks and document rollback results before Phase 1 behavior
   changes.

## Gate

Human review is required before changing permission semantics, machine-wide hooks, the
canonical instruction hierarchy, or live runtime configuration.
