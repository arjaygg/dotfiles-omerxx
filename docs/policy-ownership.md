# Policy Ownership & Change Workflow

Last updated: 2026-04-20  
Status: Draft v1

## Purpose

Define who owns policy intent, runtime adapters, and enforcement gates so we can preserve native strengths per agent without ambiguity.

## Ownership Model

| Area | Primary Owner | Backup | Notes |
|---|---|---|---|
| Portable policy intent (shared semantics) | AI Platform Maintainer | Repo Maintainer | Must stay runtime-agnostic |
| Claude hook wiring (`.claude/settings.json`, `.claude/hooks/*`) | Claude Config Maintainer | AI Platform Maintainer | Can use Claude-only lifecycle events |
| Codex hook/rules wiring (`.codex/hooks.json`, `.codex/rules/*`) | Codex Config Maintainer | AI Platform Maintainer | Must document any unsupported parity |
| CI enforcement policy | Repo Maintainer | AI Platform Maintainer | Final authority for critical controls |
| Policy matrix docs | AI Platform Maintainer | Repo Maintainer | Source of truth for support status |

## Change Workflow

1. **Propose policy change**
   - Add/update policy in portable intent form first.
2. **Classify scope**
   - Tag as one of: `portable_required`, `claude_native`, `codex_native`, `ci_only`.
3. **Implement adapters**
   - Wire Claude and/or Codex execution paths.
4. **Add enforcement fallback**
   - If not fully portable, add/verify CI gate.
5. **Update matrix**
   - Record support status and rationale in `docs/agent-policy-matrix.md`.
6. **Validate**
   - Run replay checks + CI dry-run.

## Severity and Enforcement Defaults

| Severity | Hook Behavior | CI Behavior |
|---|---|---|
| Critical (security/data loss) | fail-closed where supported | required blocking check |
| High (workflow integrity) | warn or block based on maturity | required blocking check |
| Medium | warn-first | non-blocking advisory or required per repo policy |
| Low | telemetry-only | optional |

## Compatibility Rules

- Never remove a Claude-native control solely for parity.
- If Codex lacks native capability, elevate that policy to CI.
- “Portable” means policy intent portability, not identical runtime mechanics.

## Operational Cadence

- Weekly: drift review of matrix vs actual runtime behavior.
- Monthly: prune dead hooks/scripts, consolidate duplicate checks.
- On every agent upgrade: re-run capability audit and update the matrix date.
