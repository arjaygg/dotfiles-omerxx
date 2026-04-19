# Agent Policy Matrix (Portable Core + Native Extensions)

Last updated: 2026-04-20  
Status: Draft v1 (first-pass mapping)

## Objective

Preserve **Claude-native capabilities** while still enforcing a consistent baseline across AI agents (Claude Code, Codex, and future IDE agents).

This document defines the 3-layer enforcement model:

1. **Portable Core (required everywhere)**  
   Runtime-agnostic policy intent and checks.
2. **Agent-Native Extensions**  
   Agent-specific capabilities we should not downgrade.
3. **CI/Repo Gates (final authority)**  
   Deterministic enforcement when runtime hook coverage differs.

---

## Design Principles

- Do **not** force lowest-common-denominator behavior.
- Keep one policy intent, multiple enforcement backends.
- Any non-portable critical policy must have a CI fallback.
- Treat agent hooks as early guardrails; CI is final gate.

---

## Capability Snapshot (Current)

| Capability | Claude Code | Codex |
|---|---|---|
| Hook configuration | `settings.json` hooks block | `hooks.json` |
| Session lifecycle hooks | Strong | Available (experimental) |
| Tool interception breadth | Broad (`Read/Edit/Write/...`) | Limited today; strongest on Bash |
| Native policy files | N/A (hook-centric + settings) | `.rules` support for command policy |
| Maturity | Higher | Evolving |

---

## Enforcement Layer Matrix

Legend: ✅ native / ⚠️ partial / ❌ unavailable / 🛡 CI required

| Policy Intent | Portable Core | Claude Native | Codex Native | CI Gate Required |
|---|---:|---:|---:|---:|
| Session bootstrap and context sync | ✅ | ✅ SessionStart | ✅ SessionStart | Optional |
| Prompt-time hygiene checks | ✅ | ✅ UserPromptSubmit | ✅ UserPromptSubmit | Optional |
| Dangerous shell command control | ✅ | ✅ PreToolUse(Bash) | ✅ `.rules` + PreToolUse(Bash) | Recommended |
| Tool-wide preflight guard (read/write/edit/etc.) | ✅ intent only | ✅ PreToolUse tool matcher | ⚠️ limited today | 🛡 Yes |
| Post-tool analytics/telemetry | ✅ schema | ✅ PostToolUse | ⚠️ partial | Optional |
| Stop-time completion checks | ✅ | ✅ Stop | ✅ Stop | Recommended |
| Notification/event stream hooks | Optional | ✅ Notification | ❌ direct parity | Optional |
| Pre-compact lifecycle checks | Optional | ✅ PreCompact | ❌ direct parity | Optional |
| Worktree lifecycle hooks | Optional | ✅ WorktreeCreate/Remove | ❌ direct parity | Optional |

---

## First-Pass Mapping from Current `.claude/settings.json`

### A) Keep as Portable Core + Native per agent

| Current Claude Hook Script | Current Event | Portable Intent | Codex Strategy |
|---|---|---|---|
| `session-init.sh` | SessionStart | initialize session state | SessionStart hook |
| `session-init-enforcer.sh` | UserPromptSubmit | block/repair missing session init | UserPromptSubmit hook |
| `plans-healthcheck.sh` | UserPromptSubmit | plan file integrity checks | UserPromptSubmit hook + CI fallback |
| `plan-todowrite-reminder.sh` | UserPromptSubmit | workflow discipline reminder | UserPromptSubmit hook |
| `prompt-capture.sh` | UserPromptSubmit | prompt telemetry capture | UserPromptSubmit hook (best effort) |
| `session-end.sh` | Stop | finalize session artifacts | Stop hook |
| `plan-completion-check.sh` | Stop | ensure plan/acceptance completion | Stop hook + CI fallback |
| `todo-gate.sh` | Stop | fail if tasks left incomplete | Stop hook + CI fallback |

### B) Keep Claude-native; provide Codex alternatives

| Claude-native Hook | Why Native | Codex Alternative |
|---|---|---|
| `pre-tool-gate-v2.sh` matcher over `Read|Edit|Write|MultiEdit|Grep|Glob|Agent` | broad tool interception | Bash-only pre-check + `.rules` + CI required checks |
| `post-read-auto-delete.sh` (Read event) | read-specific post-processing | move to command wrapper/CI policy if needed |
| `context-monitor.sh` (Notification event) | notification hook surface | Codex `notify` command or background monitor scripts |
| `pre-compact.sh` (PreCompact) | lifecycle not mirrored | run equivalent checks on prompt submit / stop |
| `worktree-create.sh`, `worktree-remove.sh` | dedicated worktree lifecycle events | explicit `stack-*` scripts + CI/worktree health checks |

---

## Codex Implementation Profile (Target)

1. `~/.codex/hooks.json`
   - `SessionStart`, `UserPromptSubmit`, `Stop`
   - `PreToolUse`/`PostToolUse` for Bash-focused checks
2. `~/.codex/rules/*.rules`
   - hard-deny/require-confirmation patterns for risky shell commands
3. CI / pre-commit
   - enforce anything that depends on non-Bash tool interception

---

## Risk Controls

- **Coverage drift:** weekly parity replay tests against sample hook payloads.
- **False security assumptions:** matrix is source of truth; “unsupported in Codex” must point to CI gate.
- **Performance drag:** hook time budgets and fail-open vs fail-closed policy by severity tier.

---

## Acceptance Criteria for v1 rollout

- Every active policy tagged as: `portable_required`, `claude_native`, `codex_native`, or `ci_only`.
- No critical policy exists without at least one enforceable path in each active agent environment.
- Claude-native capabilities remain enabled (no functional downgrade).
