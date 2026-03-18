---
name: Context Optimization & Token Management (Balanced)
overview: Reduce context waste across all 5 IDEs while preserving safety and quality. Phased approach — high-ROI low-risk items first, aggressive optimization gated behind measurement. Prioritizes signal-per-token over minimum tokens.
todos:
  - id: phase1-measure
    content: "Phase 1: Measure baseline — count lines in all always-on files (AGENTS.md, CLAUDE.md, GEMINI.md, .cursor/rules/*.mdc, Cursor workspace rules)"
    status: completed
  - id: phase1-ignore-files
    content: "Phase 1: Create .cursorignore, .claudeignore, .windsurfignore, .codexignore; update .geminiignore — conservative exclusions only"
    status: completed
  - id: phase2-standards-modules
    content: "Phase 2: Create docs/standards/ — extract bulky examples and secondary standards (testing, solid, oop, routing) from kernel files"
    status: completed
  - id: phase2-slim-kernels
    content: "Phase 2: Slim AGENTS.md by ~30%, CLAUDE.md by ~30%, GEMINI.md by ~20% — keep safety rules inline, move only examples and detail"
    status: completed
  - id: phase2-cursor-rules
    content: "Phase 2: Convert task-routing.mdc to alwaysApply:false; shrink agent-guardrails.mdc to ~30 lines keeping safety+escalation; keep security rule always-on"
    status: completed
  - id: phase2-workspace-rules
    content: "Phase 2: Migrate Cursor workspace rules (Testing, SOLID, OOP) to agent-requested .mdc files; keep Security Essentials always-on as compact summary"
    status: completed
  - id: phase3-compaction
    content: "Phase 3: Cross-IDE compaction — update pre-compact.sh, create Gemini pre-compress.sh, add Codex session guidance, create .windsurfrules"
    status: completed
  - id: phase3-hooks
    content: "Phase 3: Git hook (kernel size warning, not hard fail), Claude hook (kernel edit warning), Windsurf memory directive"
    status: completed
  - id: phase4-measure-and-validate
    content: "Phase 4: Re-measure context cost, check for quality regressions (missed standards, review defects), adjust if needed"
    status: completed
isProject: false
---

# Context Optimization & Token Management (Balanced)

## Design Principles

1. **Signal-per-token, not minimum tokens.** The goal is highest quality per token of context, not the smallest context possible.
2. **Safety rules stay always-on.** Three-tier boundaries (ALWAYS/ASK/NEVER), security constraints, and destructive-command blocks must never depend on the agent choosing to load them.
3. **Warnings before hard blocks.** Enforcement should nudge, not frustrate. Hard blocks only for genuinely dangerous actions.
4. **Phased rollout.** High-ROI, low-risk changes first. Aggressive optimization only after measuring that quality held.
5. **IDE-native, not uniform.** Each IDE gets the strategy that fits its capabilities, not a forced template.

## Problem Statement

Current always-on context varies by IDE, but is inefficient in all cases:

### Cursor (Worst Offender)

- `AGENTS.md` (146 lines)
- `.cursor/rules/*.mdc` (188 lines, all `alwaysApply: true`)
- Workspace Rules (Testing, SOLID, Security, OOP) = ~500+ lines
- **Total: ~834+ lines injected into every prompt.**

### Claude Code

- `AGENTS.md` (146 lines)
- `CLAUDE.md` (114 lines)
- **Total: ~260 lines injected.** (Contains bulky routing tables & examples).

### Gemini CLI

- `AGENTS.md` (146 lines)
- `GEMINI.md` (49 lines)
- **Total: ~195 lines injected.**

### Windsurf

- `AGENTS.md` (146 lines)
- `.windsurf/rules/*.md` (~100 lines)
- **Total: ~246 lines injected.**

Research: accuracy drops 15-20 percentage points with ~4,000 tokens of irrelevant context added. Most of this is reference material needed only for specific task types.

---

## Phase 1: Instant Wins (Low Risk, High ROI)

### 1a. Measure Baseline

Count lines across all always-on files. Record for comparison.

### 1b. Create Ignore Files

`**.cursorignore` is the single highest-ROI item** — none exists today. Cursor indexes everything it can see.

Create for all IDEs: `.cursorignore`, `.claudeignore`, `.windsurfignore`, `.codexignore`. Update `.geminiignore`.

**Conservative exclusions** (safe to ignore everywhere):

- Build artifacts: `target/`, `dist/`, `build/`, `node_modules/`
- Lock files: `Cargo.lock`, `package-lock.json`, `yarn.lock`
- Data/logs: `*.db`, `*.db-journal`, `*.db-shm`, `*.db-wal`, `*.log`
- Binary assets: `*.pdf`, `*.png`, `*.jpg`, `*.svg`
- IDE internals: `.git/`, `.serena/`
- Generated: `tools/mcp-sandbox/node_modules/`, `tools/mcp-sandbox/dist/`

**Explicitly keep readable** (do not ignore):

- Test files (`tests/`) — agents need test patterns
- `docs/` — agents need project documentation
- Config files (`Cargo.toml`, `productivity_rules.toml`) — agents need project config
- Migration files, schema files — agents need to understand data shape

Audit the ignore list after 2 weeks of use.

---

## Phase 2: Kernel Slimming + Rule Tiering

### 2a. Create `docs/standards/` Modules

Extract **only bulky examples and secondary reference material**. Do not extract safety rules or three-tier boundaries.

Create:

- `docs/standards/testing.md` — full testing patterns, AAA examples, mocking (from Cursor workspace rule, ~200 lines)
- `docs/standards/solid.md` — SOLID principles with code examples (from Cursor workspace rule, ~150 lines)
- `docs/standards/oop.md` — OOP best practices with code examples (from Cursor workspace rule, ~200 lines)
- `docs/standards/routing.md` — full task routing tables, RTK commands, MCP sandbox patterns (from `CLAUDE.md` + `task-routing.mdc`)
- `docs/standards/git.md` — git workflow, commit conventions, detailed examples (from `AGENTS.md` section 6)
- `docs/standards/context.md` — context management best practices, compaction strategy, artifact-driven workflows (NEW)

**Do NOT extract:**

- Security rules — keep a compact always-on summary (security is too critical to be agent-requested)
- Three-tier boundaries (ALWAYS/ASK/NEVER) — keep inline in `AGENTS.md`
- Rust guardrails (`no unwrap`, use `?`, doc comments) — keep inline, they're already lean

### 2b. Slim the Kernel Files

**Target: ~30% reduction, not aggressive truncation.** Keep what matters; remove what's duplicated or rarely needed.

- `**AGENTS.md`** (~100 lines target): Keep project overview, tech stack, essential commands, architecture map, three-tier boundaries, escalation rules. Remove detailed git standards (move to `docs/standards/git.md`), detailed Rust examples (move to `docs/standards/`). Add `See docs/standards/<topic>.md` links.
- `**CLAUDE.md`** (~80 lines target): Keep orchestration role, subagent definitions, verification commands. Move detailed routing tables and MCP patterns to `docs/standards/routing.md`. Keep `context-mode` summary.
- `**GEMINI.md**` (~40 lines target): Already fairly lean. Minor trim of duplicated rules. Add `/compress` guidance.

### 2c. Tier Cursor Rules

Two tiers based on risk tolerance:

**Tier 1 — Always-on (must never be missed):**

- `agent-guardrails.mdc`: Shrink to ~30 lines. Keep three-tier boundaries, escalation rules, large-file discipline, session hygiene hint. Remove RTK details, MCP sandbox patterns, git standards (all move to `docs/standards/`).
- `rust-standards.mdc`: Keep as-is (18 lines, scoped to `src/**/*.rs`). Already good.
- NEW `security-summary.mdc`: Compact 15-line summary of security essentials (`alwaysApply: true`). "Never log sensitive data. Mask account numbers. Verify ownership. Validate all input. See `docs/standards/security.md` for details."

**Tier 2 — Agent-requested (loaded on demand):**

- `task-routing.mdc`: Change to `alwaysApply: false` with clear `description` field. Only loaded when the agent needs to decide where to delegate.
- `testing.mdc`: Migrate from workspace rule. `alwaysApply: false`, `description: "Testing patterns, AAA structure, mocking — load when writing or reviewing tests"`.
- `solid.mdc`: Migrate from workspace rule. `alwaysApply: false`, `description: "SOLID principles — load when designing classes, interfaces, or service boundaries"`.
- `oop.mdc`: Migrate from workspace rule. `alwaysApply: false`, `description: "OOP patterns — load when writing class hierarchies or refactoring object design"`.

**Result:** Always-on Cursor context drops from ~700+ lines to ~65 lines. Agent-requested rules remain available with good descriptions.

### 2d. Update Windsurf Rules

- Update `.windsurf/rules/agent-guardrails.md` to match the slimmed Tier 1 content.
- Update `.windsurf/rules/rust-standards.md` to match.
- Create `.windsurfrules` at project root with memory/checkpoint directives.

---

## Phase 3: Compaction & Enforcement

### 3a. Cross-IDE Compaction

Each IDE gets a strategy fitted to its capabilities:

**Claude Code** (full hook support — already strong):

- Update `pre-compact.sh` to explicitly retain `plans/*.md` and `docs/adr/*.md`.
- Add kernel-edit warning to `pre-tool-gate.sh` (soft warning via exit 2, not hard block). Suggests `ALLOW_KERNEL_EDIT=1` override.
- No changes to `context-monitor.sh` (already good at 30%/15%/5%).

**Gemini CLI** (has `PreCompress` hooks):

- Create `.gemini/hooks/pre-compress.sh` with Gemini-compatible retention instructions (verify against Gemini's hook protocol, which differs from Claude Code's).
- Update `.gemini/settings.json` `PreCompress` section to use the Gemini-specific script.
- Add to `GEMINI.md`: "Run `/compress` after completing a research task."

**Codex CLI** (no hooks):

- Add session guidance to `.codex/config.yaml` or a new `CODEX_INSTRUCTIONS.md`: "Prefer short sessions. After committing, start fresh. Use `/compact` at most once per session."
- Research shows 3-5+ compactions degrade Codex quality. The primary defense is session discipline, not compaction.

**Cursor** (no hooks, auto-summarization only):

- Prevention, not recovery. The Tier 1/Tier 2 rule split handles this.
- Add to `agent-guardrails.mdc`: "After completing a task and committing, suggest starting a new chat."
- Cursor's dynamic context discovery naturally avoids some waste by writing long tool outputs to files.

**Windsurf** (Memories + Cascade):

- Create `.windsurfrules`: "Before context exceeds 50% capacity, save task state to `plans/<task>.md`. On resume, read the latest plan first."
- Leverage Windsurf Memories for cross-session persistence.

### 3b. Git Hook: Kernel Size Guard

- Create `scripts/git-hooks/check-kernel-size.sh`.
- **Warning, not hard failure.** Print a clear message if `AGENTS.md` > 120 lines, `CLAUDE.md` > 100 lines, or `GEMINI.md` > 60 lines. Exit 0 (allow commit) but make the warning visible.
- Rationale: A clear 130-line file is better than a cryptic 95-line file. Warnings catch drift; hard blocks cause workarounds.
- Add to `.pre-commit-config.yaml` at `pre-commit` stage.

### 3c. `docs/standards/context.md` (User-Facing Best Practices)

Document in `docs/standards/context.md`:

- **Artifact-driven state:** Important decisions and progress go in `plans/`. Chat history is ephemeral.
- **Session discipline:** One feature or tightly-related bug cluster per session. New session when changing domain.
- **Request scoping:** Scoped prompts ("fix `src/db.rs` line 42") use ~88% fewer tokens than unscoped ("fix the database bug"). Reference specific files.
- **Use `@filename` not `@Codebase`** in Cursor/Windsurf.
- **Prompt caching:** Don't edit kernel files mid-session (invalidates Claude Code's cache).
- **Compaction as fallback:** Prefer short sessions and artifact checkpoints over repeated compaction cycles.

---

## Phase 4: Measure, Validate, Adjust

### 4a. Re-Measure

Count always-on context lines after changes. Compare to baseline.

### 4b. Validate Quality

After 1-2 weeks of use, check for regressions:

- Did agents miss security or testing rules that were moved to agent-requested?
- Did review defects increase?
- Were any ignored files needed and had to be manually re-included?
- How often did agents actually request the Tier 2 rules?

### 4c. Adjust

- If security rules are being missed: promote `security-summary.mdc` to a longer always-on version.
- If agents never request certain Tier 2 rules: consider removing them entirely (dead documentation).
- If ignore files excluded something needed: add it back.
- If kernel size warnings fire often: the limit may be too tight.

---

## Execution Order (by Phase)

**Phase 1 (immediate, ~1 hour):**

1. Measure baseline.
2. Create ignore files (`.cursorignore` first).

**Phase 2 (focused work, ~2-3 hours):**
3. Create `docs/standards/` modules.
4. Slim `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`.
5. Migrate Cursor workspace rules to Tier 2 `.mdc` files.
6. Refactor Cursor project rules (`task-routing.mdc` to agent-requested, slim `agent-guardrails.mdc`, create `security-summary.mdc`).
7. Update Windsurf rules and create `.windsurfrules`.

**Phase 3 (enforcement, ~1-2 hours):**
8. Configure cross-IDE compaction (Gemini, Codex, Windsurf).
9. Create git hook (kernel size warning) and update `.pre-commit-config.yaml`.
10. Update Claude Code hooks (kernel edit warning, `pre-compact.sh` artifact retention).
11. Write `docs/standards/context.md`.

**Phase 4 (after 1-2 weeks):**
12. Re-measure and compare.
13. Validate quality (check for regressions).
14. Adjust based on findings.

---

## Verification Checklist

- Always-on context reduced by at least 40% (line count).
- `.cursorignore` prevents indexing of `target/`, `Cargo.lock`, etc.
- Open Cursor on a `.rs` file — only `rust-standards.mdc` + lean guardrails + security summary injected.
- Edit `AGENTS.md` in Claude Code — hook warns (but does not block).
- Compact a Claude Code session — `pre-compact.sh` retains plan file references.
- Compress a Gemini CLI session — `pre-compress.sh` outputs retention instructions.
- Security rules remain loaded on every prompt in every IDE.
- Agents can find and load `docs/standards/testing.md` when writing tests.
- No increase in review defects or missed standards after Phase 2.

