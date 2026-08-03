# 0019 — Delegation and context-admission policy is client-agnostic, not Codex-specific

**Status:** Accepted
**Date:** 2026-08-03
**Amends:** `decisions/0018-codex-delegation-and-model-routing.md` (file naming and scope only; the
hard/warn split, the Codex tier table, and `pre-agent-gate.sh` are unchanged)

## Decision

Rename `ai/rules/codex-delegation.md` → `ai/rules/delegation-and-context-admission.md` and restate
its contents as client-agnostic. Mirror it into `.cursor/rules/` alongside the other shared rules.
Add an **All-client rows** subsection to `ai/skills/model-routing/SKILL.md`'s Enforcement section
covering the three clauses that no client can enforce.

What stays client-specific and does **not** move into the shared rule:

- Model tier tables (Claude / Codex / Cursor) — already sectioned in `model-routing/SKILL.md`.
- Enforcement mechanisms — `.claude/hooks/pre-tool-gate-v2.sh` §7b/§8 and `config-integrity.sh` for
  Claude; `.codex/hooks/pre-agent-gate.sh` for Codex.
- The pinned Coordinator model — `.claude/settings.json` (ADR 0014) and `~/.codex/config.toml`.

## Why

0018 filed the policy under a Codex-specific name because the request that produced it was about
Codex. Reviewing the result against the rest of the harness showed the name was wrong on the
substance: nothing in the context-admission table, the delegation triggers, the ≤30-line return
contract, or the escalation ladder depends on a model family or a tool surface. They are statements
about how a coordinating agent should spend its context, and they apply identically to Claude Code,
Cursor, and any future client.

The concrete cost of leaving it Codex-named was verifiable, not hypothetical: `grep` for the return
contract and the context-admission table across `ai/rules/`, `ai/skills/`, and `CLAUDE.md` returned
only `codex-delegation.md`. Claude Code — the client with the *more* developed enforcement layer
(Goal 03, Goal 05) — had no statement of either. The policy with the least enforcement was also the
one reaching the fewest clients.

Filing it under a client name would also have set the wrong precedent for the next client: a
`cursor-delegation.md` and a `gemini-delegation.md` would each re-derive the same four sections, and
they would drift. `agent-user-global.md` § File And Tool Discipline forbids exactly that, and it is
the same failure mode 0018 was written to avoid one level down.

## Alternatives rejected

- **Leave the Codex name and add a second copy for Claude:** rejected — two copies of
  client-agnostic prose is the duplication 0018 exists to prevent, restated at the client level.
- **Fold the content into `agent-user-global.md`:** rejected — that file is already the machine-wide
  baseline and is loaded in full by every client on every turn. Adding ~120 lines of delegation
  detail to it would cost context on every session, including sessions that delegate nothing.
  A separate rule can be referenced rather than inlined.
- **Fold it into `model-routing/SKILL.md`:** rejected — a skill loads on demand; a rule is always in
  force. Context admission must hold whether or not the routing skill was invoked.
- **Rewrite ADR 0018 in place:** rejected — 0018 is Accepted and its reasoning about the hard/warn
  split remains correct. Amending by a new ADR keeps the record of what changed and why.

## Consequences

- The rule now reaches Codex (`@rules/` symlink), Cursor (`.cursor/rules/` mirror), and Claude Code
  **once its `@ai/rules/` reference is added to `~/.claude/CLAUDE.md`** — deliberately left as a
  manual step, since `CLAUDE.md` § Cache forbids mid-session edits to that file.
- Gemini, Windsurf, and opencode have config templates in `ai/config/` but no rule-loading mechanism
  wired in this repo. They are out of reach until one exists; this is a known gap, not an oversight.
- The old path `ai/rules/codex-delegation.md` no longer exists. `~/.codex/rules/codex-delegation.md`
  must be repointed, and any external reference to the old name will dangle.
- Goal 06's Step 1 and its acceptance criteria refer to the old filename. They are left as written —
  they record what was true when the goal was executed — with a pointer to this ADR.
- Three clauses are now explicitly documented as unenforceable on every client rather than implicitly
  unenforced on one. This is the honest state, not a regression.

## Related

- `decisions/0018-codex-delegation-and-model-routing.md`, `decisions/0013`, `decisions/0014`.
- `ai/rules/delegation-and-context-admission.md`, `.cursor/rules/delegation-and-context-admission.md`.
- `ai/skills/model-routing/SKILL.md` § Enforcement → All-client rows.
