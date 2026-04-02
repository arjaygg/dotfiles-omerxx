# BMAD-METHOD Learnings → Practical Improvements

**Date:** 2026-04-02  
**Context:** Explored BMAD-METHOD (v6.0.0-Beta.2) to identify transferable patterns for `~/.dotfiles/ai/` (user-scoped) and project-specific agent infrastructure. Most BMAD architecture is overengineered for our context — it's guided SDLC facilitation, not production development tooling. Three patterns transfer well with proper scope separation.

---

## What to skip (and why)

| BMAD Pattern | Verdict |
|---|---|
| Agent personas (identity, communication_style) | Flavor text doesn't improve code output. Our agents are precise and functional. |
| Step-file decomposition | Our skills run autonomously in one shot. Extra files = extra indirection. |
| Workflow manifest/CSV registry | Claude Code reads skill frontmatter. CSV = two places to update. |
| Phase-based directory organization | Breaks symlinks, adds overhead. Flat + good naming works. |
| Team compositions | Experimental feature isn't stable. Hawk spawns agents fine. |

---

## 3 actionable improvements

### 1. Domain Knowledge Base (scoped)

**Problem:** Domain knowledge is embedded inline in skill/agent bodies. Multiple agents need overlapping patterns but can't share them.

**Scope rule:** Generic language/framework patterns → `~/.dotfiles/ai/knowledge/` (user-scoped, travels with dotfiles). Project-specific domain patterns → `ai/knowledge/` at project root (agent-agnostic).

#### User-scoped (`~/.dotfiles/ai/knowledge/`)
```
knowledge/
  go-testing-patterns.md        # determinism, assertion quality, table-driven, testify conventions
  go-observability-patterns.md   # metrics, tracing, provider/collector patterns (generic)
  ado-pr-conventions.md          # title format, reviewer rules, PR description standards
```
These are language/platform conventions that apply across any Go project or ADO repo.

#### Project-scoped (e.g. `auc-conversion/ai/knowledge/`)
```
ai/knowledge/
  etl-chunker-patterns.md       # backpressure, circuit-breaker, chunker specifics
  observability-provider.md      # MetricCollector wiring, noop pattern for this project
  streaming-pipeline.md          # Strategy B shadow mode, chunk_processor path
```
These are AUC-specific domain knowledge that only make sense in that project context. Any AI agent (Claude, Cursor, Gemini, Codex) can read from `ai/knowledge/`.

**How skills use it:** Skills `Read` from the appropriate scope:
```markdown
## Load knowledge
Read ~/.dotfiles/ai/knowledge/go-testing-patterns.md       # user-scoped
Read ai/knowledge/etl-chunker-patterns.md                   # project-scoped (agent-agnostic)
```

**Files to modify:**
- Create: `~/.dotfiles/ai/knowledge/` directory + 3 generic docs (extract from test-author, stack-pr)
- Create: `auc-conversion/ai/knowledge/` directory + project-specific docs (extract from auc-dev-a/b/c)
- Edit: test-author, test-reviewer, auc-qa, hawk — replace inline content with Read references
- Symlink: `~/.dotfiles/.claude/knowledge/` → `~/.dotfiles/ai/knowledge/` (follow existing symlink convention)

---

### 2. Create/Validate Flag Pattern

**Problem:** Skills are single-mode. No way to re-check that hawk findings were fixed, or verify PR readiness before creation.

**Scope:** This modifies user-scoped skills in `~/.dotfiles/ai/skills/`. Project-scoped verify flags go in project-specific skill overrides.

#### User-scoped flags (`~/.dotfiles/ai/skills/`)

| Skill | Flag | What it does |
|---|---|---|
| `hawk` | `--validate` | Re-read previous findings, verify each is resolved in current diff |
| `stack-pr` | `--preflight` | Check branch clean, tests pass, no WIP commits |

#### Project-scoped flags (in project `.claude/` skill overrides)

| Skill | Flag | What it does |
|---|---|---|
| `auc-dev-a/b/c` | `--verify` | Check acceptance criteria from story file are met |

**Implementation:** Add `$ARGUMENTS` check at skill entry:
```markdown
### Mode Check
If `$ARGUMENTS` contains `--validate`:
  → Load previous findings from plans/hawk-findings.md
  → For each finding, check if cited code has been changed
  → Report: resolved / still-present / new-issues
  → STOP (do not run full review)
```

**Files to modify:**
- Edit: `~/.dotfiles/ai/skills/hawk/SKILL.md` — add validate branch
- Edit: `~/.dotfiles/ai/skills/stack-pr/SKILL.md` — add preflight branch
- Edit: `auc-conversion/.claude/agents/` auc-dev-a/b/c — add verify branch (project-scoped)

---

### 3. Config-Driven File Ownership (project-scoped only)

**Problem:** auc-dev-a/b/c hardcode package ownership paths. Path changes require updating 3+ skills.

**Scope:** Entirely project-scoped. This is an `ai/project-config.yaml` pattern that any project can adopt (agent-agnostic).

**Solution:**
```yaml
# auc-conversion/ai/project-config.yaml
project_name: auc-conversion
ownership:
  dev-a: ["pkg/observability/**", "pkg/metrics/**"]
  dev-b: ["pkg/resilience/**", "pkg/scheduler/chunker.go", "pkg/circuit/**"]
  dev-c: ["pkg/pipeline/**", "pkg/streaming/**"]
test_framework: testify
lint_cmd: golangci-lint run --fix
```

Skills replace hardcoded paths with:
```markdown
## File Ownership
Read ai/project-config.yaml → extract `ownership.dev-a` paths.
Only modify files matching these globs.
```

**Files to modify:**
- Create: `auc-conversion/ai/project-config.yaml`
- Edit: auc-dev-a/b/c skill/agent definitions — replace hardcoded paths with config reads

---

## Scope summary

| Improvement | User-scoped (`~/.dotfiles/ai/`) | Project-scoped (`ai/` or `.claude/`) |
|---|---|---|
| Knowledge base | Generic Go/ADO patterns (`ai/knowledge/`) | AUC ETL domain patterns (`ai/knowledge/`) |
| Validate flags | hawk, stack-pr (`ai/skills/`) | auc-dev-a/b/c (`.claude/agents/`) |
| Config ownership | — | `ai/project-config.yaml` |

---

## Verification

1. **Knowledge base:** Run `/hawk` → verify Quality subagent loads `go-testing-patterns.md` from user scope
2. **Validate flags:** Run `/hawk` → fix an issue → run `/hawk --validate` → confirm detection
3. **Config ownership:** Edit path in `ai/project-config.yaml` → run `/auc-dev-a` → confirm updated scope
