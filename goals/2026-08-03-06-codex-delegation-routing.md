# Goal 06 — Extend delegation and model-tier routing to Codex

## Objective

Give Codex CLI the same delegation and model-routing discipline Goal 03 gave Claude Code: a
documented tier table, a context-admission policy, and a `PreToolUse` gate that hard-denies the
checks which are genuinely deterministic while warning — visibly, with a stated reason — on the ones
that are not.

"Done" means a Codex session routes mechanical work to a cheap tier by default, cannot spawn a
worker on an unsupported model slug or against a spec file that does not exist, and carries no
duplicated copy of policy that already lives in `ai/rules/agent-user-global.md`.

## Why

Three concrete gaps, all verified 2026-08-03:

1. **No Codex tier table exists anywhere in the harness.** `grep` for `gpt-5.6-*` / `gpt-5.4-mini`
   across `ai/` and `.codex/` returns only vendored `.venv` noise. `ai/skills/model-routing/SKILL.md`
   documents Claude tiers and mirrors Cursor; Codex is absent. The Codex coordinator is pinned to
   `gpt-5.6-sol` in `~/.codex/config.toml` with no record of why, which is exactly the undocumented
   state ADR 0014 exists to prevent on the Claude side.
2. **No Codex agent or model gate.** `.codex/hooks/` enforces context routing (`pre-bash-guard.sh` →
   `context_gate.py`) and bash safety only. The Claude-side equivalents —
   `pre-tool-gate-v2.sh` §7b/§8 and `config-integrity.sh`'s `check_agent_models()` — have no Codex
   counterpart, so subagent tier and fan-out are entirely unchecked there.
3. **Delegation policy was about to be duplicated.** A first pass at this work restated the
   Orchestrator-Worker roles, the `plans/specs/<label>.md` path, and the anti-nesting rule in a new
   Codex-only rule file — all three already in `ai/rules/agent-user-global.md`, which *is* Codex's
   `model_instructions_file` and therefore already loaded. `agent-user-global.md` § File And Tool
   Discipline forbids exactly this.

The cost case is unchanged from Goal 03: a coordinator that reads files, fans out searches, and
tails build logs pays frontier rates for bulk tokens that then degrade the rest of the session.

## Current state

- `~/.codex/config.toml`: `model = "gpt-5.6-sol"`, `model_reasoning_effort = "medium"`,
  `features.multi_agent = true`. Available slugs per `models_cache.json`: `gpt-5.6-sol`,
  `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`.
- Codex 0.146.0's subagent call accepts `agent_type`, `instructions`, and `model` (confirmed by
  string inspection of the shipped binary). `agents_dir` exists in the binary but `~/.codex/agents/`
  does not, so no declarative agent-file schema was assumed.
- `.codex/hooks.json` wires SessionStart, UserPromptSubmit, PreToolUse (Bash/Read shapes),
  PostToolUse, Stop. No agent matcher.
- `ai/rules/agent-user-global.md` already supplies roles, frozen-spec path, anti-nesting, and
  fresh-vs-fork.

## Non-goals

- **Do not port the Claude §7b keyword tier-mismatch heuristic.** It is a keyword matcher, not a
  difficulty classifier; ADL-022 kept it warn-only on evidence, and Codex has no comparable evidence
  base yet. Adding it now would import the false-positive surface without the justification.
- **Do not attempt to enforce the ≤30-line return contract.** No hook observes a subagent's return
  payload.
- **Do not promote the fan-out gate to deny.** PreToolUse sees spawns, never completions.
- **Do not invent an agent-definition file schema** for `~/.codex/agents/` that could not be
  verified against the shipped binary.
- **Do not change the pinned coordinator model.** That is a user decision, recorded not derived.

## Steps

1. Rewrite `ai/rules/codex-delegation.md` to the Codex-specific delta only — context admission,
   delegation triggers, return contract, escalation ladder, context hygiene — referencing
   `agent-user-global.md` for roles/spec/anti-nesting rather than restating them.
   **Files:** `ai/rules/codex-delegation.md`
   **Accepts:** the file contains no restatement of Orchestrator-Worker roles, the spec path
   convention, or the anti-nesting rule, and names `agent-user-global.md` as their source.
2. Add a Codex tier table and effort ladder to `ai/skills/model-routing/SKILL.md`, alongside the
   existing Claude and Cursor sections; update the frontmatter description and triggers so the skill
   routes on Codex tier questions.
   **Files:** `ai/skills/model-routing/SKILL.md`
   **Accepts:** all six installed slugs appear with an assigned tier; the sync note covers three
   clients, not two.
3. Add `.codex/hooks/pre-agent-gate.sh` implementing the hard/warn split, and wire it as a second
   `PreToolUse` entry in `.codex/hooks.json`.
   **Files:** `.codex/hooks/pre-agent-gate.sh`, `.codex/hooks.json`
   **Accepts:** `bash -n` clean; `jq -e .` on `hooks.json` valid; the matcher sits inside the
   existing `PreToolUse` array rather than under an invented event key.
4. Add Codex rows to `model-routing/SKILL.md`'s Enforcement table mapping every clause to its actual
   mechanism, including the clauses with no mechanism, plus the two deployment caveats
   (project-scoped `hooks.json`, `trusted_hash` re-prompt).
   **Files:** `ai/skills/model-routing/SKILL.md`
   **Accepts:** every row states hard / warn / none, and each warn or none row states why.
5. Exercise every hook branch and record the output.
   **Files:** none (evidence only)
   **Accepts:** deny, allow, both warn paths, fan-out warn, and all three fail-open paths each
   demonstrated with an observed exit code.
6. Record the decision as an ADR and add the goal to `goals/00-index.md`.
   **Files:** `decisions/0018-codex-delegation-and-model-routing.md`, `goals/00-index.md`
   **Accepts:** the ADR states its relationship to 0013 and 0014 and does not contradict either.

## Acceptance criteria

- [x] `ai/rules/codex-delegation.md` carries only the Codex delta; roles, spec path, and anti-nesting
      are referenced, not duplicated.
- [x] `ai/skills/model-routing/SKILL.md` has a Codex section covering all six installed slugs, and
      its Cursor sync note names three tier tables.
- [x] `pre-agent-gate.sh` denies an unsupported model slug — observed `exit=2` on
      `{"model":"gpt-4o"}`.
- [x] `pre-agent-gate.sh` denies a referenced-but-absent spec — observed `exit=2` on
      `plans/specs/nope.md`; allows the same shape when the file exists (`exit=0`).
- [x] Unset model and unreferenced spec each produce a warning at `exit=0`, never a denial.
- [x] Fan-out warning fires on the 4th spawn inside the window and not on the 3rd.
- [x] All three fail-open paths (empty input, malformed JSON, missing `jq`) exit 0 — malformed JSON
      exits silently, with no warning misattributed to the spawn.
- [x] `.codex/hooks.json` is valid JSON and the new matcher is a sibling entry inside `PreToolUse`.
- [x] Enforcement table states hard/warn/none per clause with a reason for every non-hard row.
- [ ] One real Codex session's fire/no-fire evidence collected before any warn→deny promotion is
      proposed. **Deliberately open** — mirrors Goal 03 Step 6; promotion is a separate decision.

## Evidence to update

- Hook branch matrix (Step 5) — rerun `pre-agent-gate.sh` against the payload fixtures after any
  edit to the slug enum or the spec-path regex.
- Slug enum drift — when `~/.codex/models_cache.json` gains or drops a model, the enum in
  `pre-agent-gate.sh` and the table in `model-routing/SKILL.md` must change in the same commit, or
  valid spawns are denied.
- Payload-shape drift — the field extractors are best-effort across Codex versions. If a Codex
  upgrade changes the subagent payload, the gate silently fails open; re-run the fixtures after any
  Codex version bump.

## Stop and ask if

- The subagent payload shape cannot be confirmed against the installed Codex version — fail open and
  ask rather than guessing at a schema.
- Any check would need to become a deny without deterministic ground truth behind it.
- The pinned coordinator model or the cheap-worker default would have to change to make a check pass.
- Machine-wide (`~/.codex/hooks.json`) installation is required — that is outside this repo's tracked
  surface and needs an explicit decision.
