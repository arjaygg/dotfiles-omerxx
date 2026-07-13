# Public-Hygiene Disposition Plan — 2026-07-13

This plan is proposal-only. It does not modify tracked configuration, runtime
files, permissions, hooks, or instruction hierarchy.

## Current evidence

`python3 scripts/public_hygiene_check.py --json` on the merged Phase 0 source
reports **369 findings across 88 tracked paths**:

| Area | Findings | Initial disposition |
|---|---:|---|
| `ai/` canonical agents, skills, and eval artifacts | 114 | Replace private org/project/path examples with portable placeholders; preserve behavioral content |
| `.claude/` distribution files | 61 | Update canonical `ai/` source first; retain only symlink-equivalent distribution files |
| `.codex/config.toml` | 45 | Replace machine trust/skill/MCP paths with the portable Codex base plus ignored overlay |
| `plans/` | 45 | Archive unrelated session/work-context plans outside Git; retain sanitized durable decisions |
| `.gemini/` | 26 | Generate from portable base and ignored local overlay; do not adopt live state |
| `.claude-global/` | 19 | Remove private global adapter content from the public distribution or replace with neutral loader |
| `.config/`, `.cursor/`, `.windsurf/`, `.mcp.json` | 28 | Replace machine paths with manifest-driven portable sources; preserve client schemas |
| `decisions/`, `scripts/`, `.local/`, `.serena/`, `git/`, other | 31 | Case-by-case review: durable rationale, fixture, generated artifact, or actual leak |

Counts overlap by rule when a line contains multiple findings; they are not a
line count or a deletion quota.

## Proposed safe sequence

1. **Inventory and backup:** export a manifest of affected tracked paths and
   SHA-256 values to `~/.config/dotfiles-ai/backups/`; never commit raw private
   content or transcripts.
2. **Classify:** mark each finding as `portable-source`, `local-overlay`,
   `fixture/example`, `historical-durable`, `unrelated-session`, or `secret`.
3. **Archive unrelated plans:** move raw session plans outside Git, preserve a
   sanitized pointer only when durable rationale is needed.
4. **Sanitize canonical sources:** use neutral placeholders such as
   `${ADO_ORG}`, `${PROJECT_NAME}`, `${HOME}`, and `${PCTX_CONFIG}`; keep examples
   obviously synthetic and keep secrets out of examples.
5. **Regenerate distribution links:** validate symlink targets and ensure edits
   occur in `ai/` rather than tool-specific copies.
6. **Gate:** require scanner exit 0, secret scan exit 0, JSON/TOML parsing, and
   clean repeated proposal generation before any runtime migration.

## Explicit non-goals

- Do not apply generated settings to `~/.claude`, `~/.codex`, `~/.gemini`,
  `~/.cursor`, `~/.windsurf`, or `~/.config/pctx` in this sequence.
- Do not change permission semantics, hard-deny rules, hook ordering, or the
  canonical instruction hierarchy.
- Do not silently delete raw local backups; preserve rollback evidence outside Git.

## Approval boundary

The next implementation approval should cover the classification and archive
sequence above. A separate approval remains required for live runtime migration
and for Phase 1 hook/permission changes.
