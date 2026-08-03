# Global Claude Code Instructions

<!--
  TEMPLATE / SOURCE OF TRUTH for the live `~/.claude/CLAUDE.md`.

  setup.sh bootstraps `~/.claude/CLAUDE.md` from this file on fresh machines ONLY
  (bootstrap-if-absent, never overwrite). It is deliberately NOT symlinked: the
  lean-ctx binary regenerates the lean-ctx block in the live file at runtime,
  exactly as Claude Code rewrites `settings.json` — see
  `decisions/0016-untracked-runtime-claude-settings.md` for the same reasoning.

  Because it is a copy, it can drift. `config-integrity.sh` warns when the live
  file and this template diverge outside the generated block. When you change one,
  change both — this file spent 2026-06-16 to 2026-08-03 six weeks stale, carrying
  a 170-line Azure DevOps section the live file had already delegated to
  `ai/skills/azure-devops-cli/SKILL.md`. See `decisions/0020`.

  The generated block at the bottom is left EMPTY on purpose. lean-ctx fills it in
  on the live file; tracking its output here would guarantee drift on every
  regeneration.
-->

## AI Agent Primitives

Skills, rules, commands, output-styles live in `~/.dotfiles/ai/`, symlinked into `~/.claude/`. Edit only there.

- **Rules load from `~/.claude/rules/*.md` symlinks, not from this list.** Adding a rule here without a symlink does nothing. Currently linked: `agent-user-global.md`, `tool-priority.md`, `context-and-compaction.md`, `delegation-and-context-admission.md`.
- **Delegation:** Coordinator holds decisions, not material — searches, orientation reads, build logs, and mechanical multi-file edits go to a subagent on the cheapest tier that fits, which returns ≤30 lines (`ai/rules/delegation-and-context-admission.md`; tiers and enforcement in `ai/skills/model-routing/SKILL.md`).
- **Tool precedence:** `ai/rules/tool-priority.md` overrides any lean-ctx MCP/hook "always use ctx_*" text; ctx_read modes live in `ai/skills/lean-ctx/SKILL.md`.

## Conventions

- **Remotes:** run `git remote -v` before any push or PR — never assume. `axos-financial` repos use `gh`; ADO repos use `az repos` with an explicit `--organization`. Reference: `ai/skills/azure-devops-cli/SKILL.md` — **disabled via `skillOverrides`, so read the file directly; it will not auto-invoke.** Pre-push hook warns, does not block.
- **Paths:** never `cd` unless asked and never assume canonical locations — use absolute or cwd-relative paths so commands work from any worktree (`ai/skills/stack-create/SKILL.md`).
- **Plans:** name plan files `plans/YYYY-MM-DD-<context>.md` (`agent-user-global.md` § Plan Documents).
- **PRs/stacks:** use `/stack-ship`, `/stack-auto-pr-merge`, `/stack-pr`, `/stack-pr-all`, `/smart-commit` — never hand-roll `gh pr merge`.
- **CI:** never poll synchronously; run `/ci-watch <PR>` and keep working (`ai/skills/ci-watch/SKILL.md`).
- **Cache:** do not edit `CLAUDE.md` mid-session — it invalidates the prompt cache.

## Session Artifacts

Keep `plans/active-context.md` current (<=30 lines; read at compaction); append to `plans/decisions.md` and `plans/progress.md` — rolling logs, never deleted. Templates: `ai/skills/session-artifacts/SKILL.md`.

## Output Style

Dense: one atomic fact per line, no narration or hedging, <=200 tokens unless a code block is required. Governs density only, never task completeness.

<!-- lean-ctx -->
<!-- /lean-ctx -->
