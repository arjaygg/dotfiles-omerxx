# Delegation — Context Admission & Return Contracts

**Client-agnostic.** Applies to Claude Code, Codex, Cursor, and any other agent client on this
machine. Nothing here depends on a particular model family or tool surface.

The **roles** (Coordinator/Executor), the **frozen-spec path** (`plans/specs/<label>.md`), the
**anti-nesting rule**, and the **fresh-vs-fork choice** are defined once in `agent-user-global.md`
§§ Orchestrator-Worker Paradigm / Agent Spawning and are **not restated here**.

Per-client **model tiers** live in `ai/skills/model-routing/SKILL.md` (Claude, Codex, and Cursor
tables, plus the Enforcement matrix for each). Read-volume routing lives in
`context-and-compaction.md`.

What this file adds: which inputs may enter Coordinator context, when to delegate, and the shape a
worker must return.

---

## 1. Context admission

The Coordinator's context is the scarcest resource in a run: it is re-sent every turn, and bulk
crowds out reasoning as the session lengthens. Admit decisions, not material.

**Admit:** the request; plans and specs; worker return summaries; diffs under review; the error being
reasoned about; decisions and their rationale.

**Refuse — delegate, or write to a file and cite the path:**

| Input | Cost | Instead |
|---|---|---|
| Broad search fan-out | N files × M matches, mostly noise | worker returns the answer, not the matches |
| Whole-file reads for orientation | high volume, low density | worker with `ctx_compose`, or `ctx_read(mode="signatures")` |
| Build / test / lint output | large, mostly irrelevant | worker runs it, returns pass/fail + failing cases |
| Repeated mechanical edits | linear growth, zero judgement | one worker, one spec, one summary |
| Log or data dumps | permanent context residency | worker extracts, or cite the path |
| Third-party docs / web pages | unbounded | worker returns the lines that matter |

The per-call size gate already exists in every client — `.claude/hooks/pre-tool-gate-v2.sh` §1,
`.codex/hooks/pre-bash-guard.sh`, and `.cursor/hooks/context-file-gate.sh`, all routing through
`ai/context/context_gate.py`. This table covers the cases **below** that threshold, where the cost is
cumulative across a session rather than large in any single call. Nothing enforces it.

---

## 2. Delegate when ANY holds

1. The task touches **3+ files**, or reads more than ~2.
2. The task is **mechanical**: rename, boilerplate, formatting, import fixes, test scaffolding,
   config propagation, doc updates.
3. The task is **discovery**: "find", "where is", "which callers", "does this repo have".
4. The task produces **verbose output not needed verbatim**: builds, test suites, log triage.
5. The task is **independent** of other pending work → run it alongside its siblings.
6. The task warrants a **different tier** (see `model-routing/SKILL.md` for your client's table).
7. You are about to do something whose intermediate steps you would not want in the transcript.

**Never delegate:** the final answer; the plan or spec itself; architectural and security decisions;
ambiguity that needs the user; review of returned work; irreversible actions (`git push`, PR
merge/close, deploy, destructive SQL, `rm -rf`). This list is narrower than
`agent-user-global.md`'s autonomy tiers, which govern *whether* an irreversible leg may run at all.

---

## 3. Return contract

Every worker returns **≤30 lines**, in this shape:

```
STATUS:   done | blocked | partial
CHANGED:  <file:symbol> — <one line each>
EVIDENCE: <command> → <exit code / pass counts / the failing assertion>
OPEN:     <questions or assumptions made, or "none">
```

No file contents unless the spec asked for exact lines. No narration. No restating the spec.

A worker that returns a wall of text has failed its contract: re-spec it rather than absorbing the
text — absorbing it defeats the delegation.

**Enforcement:** none. This is prose, checked by nobody. It holds only because the Coordinator
refuses oversized returns.

---

## 4. Escalation ladder

Applies to worker tier, not the Coordinator (whose model is a pinned client setting —
`.claude/settings.json` `model`, `~/.codex/config.toml` `model`).

1. Cheap tier fails → **sharpen the spec**, retry once at the same tier.
2. Fails again → step up **one** tier.
3. Fails again → the Coordinator takes it, or asks the user.

Never retry the same tier with the same spec. Never skip a tier.

A vague spec — not a weak model — is the usual cause of "the cheap model couldn't do it". Spec
quality is the real cost lever; escalating first hides the defect and pays for it.

---

## 5. Context hygiene

- **Checkpoint to disk, not transcript.** `plans/decisions.md`, `plans/progress.md`,
  `plans/active-context.md` (≤30 lines). Then cite the path.
- **Prefer a path over a paste.** File references survive compaction; pasted content is what
  compaction destroys.
- **One task per session**; checkpoint rather than accumulate a third compaction.
- **Never re-read a file to refresh it** — read the specific lines, or delegate the question.
- **Discard, don't summarize.** Once the answer is extracted, don't restate the source.

---

## 6. Anti-patterns

- The Coordinator reading ten files to answer "how does auth work" → one discovery worker on the
  cheap tier (`haiku` / `gpt-5.6-luna`).
- The Coordinator at max effort doing a mechanical rename → cheap tier with an exact spec.
- Spawning a worker without writing its spec → it invents scope, and you pay twice.
- Delegating the final user-facing answer → the Coordinator owns synthesis.
- One worker per file for a uniform change → one worker, one spec, all files.
- Escalating on the first failure → sharpen the spec first.
- A worker's raw build log reaching the transcript → that log is what the worker was for.

---
*Maintained at: `~/.dotfiles/ai/rules/delegation-and-context-admission.md`*
*Mirrored to `.cursor/rules/` for Cursor. Enforcement status per client:
`ai/skills/model-routing/SKILL.md` § Enforcement.*
