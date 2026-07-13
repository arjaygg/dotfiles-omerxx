# Phase 0 Exposure Classification — 2026-07-13

## Purpose

Classify the current scanner findings before any cleanup or migration. This is a
proposal artifact, not an allowlist and not authorization to delete or rewrite files.

## Measured baseline

- Public-hygiene scanner: 368 findings — 185 organization names, 132 absolute home
  paths, and 51 organization URLs (current Phase 0 branch recheck).
- Highest-count files: `.codex/config.toml` (45), `.claude/agents/claude-code-review-agent.md`
  (22), `ai/agents/claude-code-review-agent.md` (22), `.claude-global/CLAUDE.md` (19),
  `ai/skills/azure-devops-cli/SKILL.md` (13), `.gemini/config/mcp_config.json` (12),
  `.config/pctx/pctx.json` (10), and `ai/skills/ado-workitem/SKILL.md` (10).

## Disposition matrix

| Area | Current evidence | Proposed disposition | Risk/gate |
|---|---|---|---|
| `.claude/settings.json` | sanitized tracked settings; portable base now added | proposal base plus reviewed local overlay | live-runtime review |
| `.claude/settings.local.json` | local permissions and worktree-specific paths; now untracked | preserve ignored local file; generate only after review | runtime review |
| `.codex/config.toml` | project trust list, absolute paths, local MCP paths | base model/MCP defaults plus ignored trust/path overlay | runtime review |
| `.gemini/config/mcp_config.json` | absolute binaries, local data/config paths | `${HOME}`/PATH-based base plus optional local overlay | runtime review |
| `.config/pctx/pctx.json` | absolute server binaries and Homebrew paths | portable command names/PATH defaults plus machine overlay | MCP bootstrap review |
| `.mcp.json`, `.gemini/mcp.json`, `.windsurf/mcp_config.json` | client-specific MCP wiring and local paths | shared portable template where schemas permit; client overlays otherwise | schema verification |
| ADO/Axos skills and agents | organization URLs, project names, operational paths | parameterize or move to private organization context; retain generic workflow only | content-owner review |
| `plans/` and `.claude-global/` | unrelated work-session and organization context | archive outside public source or rewrite as generic examples | history/privacy review |
| evaluation/workspace artifacts | generated paths and sample operational context | keep only sanitized fixtures; remove generated transcripts/metrics | fixture review |
| hooks and helper binaries | pinned executable paths in tracked scripts/config | resolve through PATH or `${HOME}`; test macOS/Linux | machine-wide hook review |

## Required migration order

1. Snapshot live settings and hashes outside Git; do not copy secrets into the repo.
2. Implement the approved settings/permission and symlink-guard branch changes.
3. Review the sanitized base templates and ignored local/work overlays.
4. Generate proposal-only diffs and validate JSON/TOML/YAML plus privacy rules.
5. Apply atomically only after review; back up runtime files and verify idempotency.
6. Re-run the scanner and doctor; require zero unsanctioned findings before claiming
   the public-repository acceptance criteria.

## Explicitly unresolved

This classification does not decide whether specialized ADO skills belong in a public
repo, which runtime fields are user-managed, or whether the live settings should be
replaced immediately. Live application and any Phase 1 permission changes remain
separate human decisions.
