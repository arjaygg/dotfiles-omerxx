# Active Decisions Log

Session-friendly ADL for in-flight work. Promote to `decisions/` when a decision is cross-cutting or long-lived.

---

## ADL-001 — Use pctx as MCP gateway

All agents route through `pctx mcp start --stdio -c ~/.config/pctx/pctx.json`.
Durable record: `decisions/0001-use-pctx-as-mcp-gateway.md`

---

## ADL-002 — Separate agent guidance from dotfiles distribution

Shared behavioral policy lives in `AGENTS.md`, `ai/rules/agent-user-global.md`, `docs/`, `decisions/`, `plans/`.
Tool-specific files (`.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.codex/AGENT.md`) are thin adapters that import the shared guidance.
Durable record: `decisions/0002-separate-agent-guidance-from-dotfiles-distribution.md`

---

## ADL-003 — Canonical decision record convention

Short active decisions live here. Durable decisions go in `decisions/NNNN-title.md`.
Convention documented in `docs/decision-records.md`.

---

## ADL-004 — validate-agent-guidance.sh as structural guardrail

`.claude/scripts/validate-agent-guidance.sh` checks that all required files exist and that adapters correctly import shared guidance. Run before merging guidance changes.

---

## ADL-005 — Universal constitution loading from ai/rules/

Tool priority, batching, Serena convention, developer guidelines, and session discipline live in `ai/rules/` and are loaded user-globally by Claude and Gemini via `@` imports. Codex loads `agent-user-global.md` only (known gap). AGENTS.md no longer owns tool priority content — it references `ai/rules/tool-priority.md`.
Durable record: `decisions/0003-universal-constitution-loading.md`

---

## ADL-006 — Hook output channel: stdout for Claude, stderr for terminal-only

2026-03-31 — Hook validation revealed that blocking/warning hooks must write to stdout
(not stderr) for Claude to see the reason. Stderr is terminal-only.
Hooks using `>&2` when they block/warn are silently broken.
See `plans/2026-03-31-hook-validation-report.md` for full findings.

---

## ADL-007 — Replace python3 with jq for hook JSON parsing

2026-04-01 — python3 startup is ~19ms vs jq ~3ms (6x). All per-tool-call hooks migrated from python3 to jq for JSON field extraction. python3 retained only in once-per-prompt hooks (plans-healthcheck.sh) and once-per-session hooks (session-init.sh) where startup cost is amortized.

---

## ADL-008 — Merge bash-output-guard into post-tool-handler

2026-04-01 — bash-output-guard.sh and post-tool-handler.sh were fully redundant (both measured output line count, both warned on large output). Merged into post-tool-handler.sh with 3-tier handling: compact >300, warn 200-300, hint 50-200. Eliminates one process spawn per Bash PostToolUse.

---

## ADL-009 — Hooks are scaffolding, not architecture

2026-04-01 — Hooks train behavioral patterns but have diminishing returns once Claude learns the rule via instructions. The system needs: (1) Learning Effectiveness Score (LES) metrics to measure teaching vs walling, (2) auto-graduation from hook enforcement to instruction-only when rules are learned, (3) memory reinforcement for persistently violated rules. See plan: plans/quirky-tinkering-plum.md Phases 6-9.
