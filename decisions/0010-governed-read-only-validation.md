# Architecture Decision Record: Governed Read-Only Validation Before Migration

Status: Proposed
Date: 2026-07-13

## Decision

Introduce read-only validation as the first implementation layer for the AI control
plane. Public-hygiene scanning, config diagnosis, static hook-schema checks, and
structured hook fixtures may inspect tracked source and execute isolated fixtures, but
must not mutate canonical settings, live runtime files, or machine-wide hook behavior.

High-impact migration remains a separate reviewed phase. In particular, removing
permission bypass defaults, replacing runtime settings copy-back, changing hook
registration, and introducing generated runtime overlays require explicit human review
and rollback instructions before implementation.

## Why

The current repository has demonstrable privacy/path findings, a tracked
`skipDangerousModePermissionPrompt` setting, automatic live-settings copy-back, ignored
hook matchers, parallel worktree handlers, and stale/skipped fixture coverage. Applying
fixes before measuring these boundaries would make it difficult to distinguish a safety
improvement from a behavior regression.

## Chosen validation layers

- `scripts/public_hygiene_check.py`: tracked UTF-8 path, organization, secret, and key
  detection.
- `scripts/config_doctor.py`: JSON/TOML parse checks plus unsafe-setting and copy-back
  detection; never writes files.
- `scripts/hook_config_check.py`: static event, matcher, handler, and parallelism checks.
- `scripts/hook_fixture_runner.py`: fixture execution with explicit silent-allow and
  schema-valid JSON-deny assertions.

## Alternatives rejected

- Fixing `.claude/settings.json` and `settings-symlink-guard.sh` in the audit branch:
  rejected because those changes affect permissions and live configuration behavior.
- Treating the existing skipped shell harness as passing coverage: rejected because
  eight fixtures referenced absent hooks and archived deny filenames encoded stale exit
  expectations.
- Allowing the scanner to use a broad committed exception list: rejected because it
  would hide unresolved public-repository exposure instead of classifying it.

## Consequences

Validation tooling can fail against the current baseline and produce reviewable
evidence without destabilizing the machine. The repository still contains unresolved
privacy/configuration findings, and a later approved migration must provide portable
templates, ignored overlays, atomic generation, backups, idempotency checks, and
rollback verification.

Links: `plans/2026-07-13-verified-architecture-risk-report.md`,
`plans/2026-07-13-execution-plan.md`, and the
[Claude Code hooks reference](https://code.claude.com/docs/en/hooks).
