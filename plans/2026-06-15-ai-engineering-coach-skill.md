# Plan: AI Engineering Coach Integration

**Date:** 2026-06-15  
**Branch:** `ai-engineering-coach`

---

## Context

The Microsoft [AI-Engineering-Coach](https://github.com/microsoft/AI-Engineering-Coach) is a VS Code extension. Its coaching value lives in two assets usable directly without the extension runtime:

- `src/core/rules/*.md` — 45 anti-pattern rule files with human-readable descriptions, "when triggered", "how to improve", and examples
- `src/chat/system-prompt.ts` — the coaching persona (pure text, no VS Code API dependency)

**Goal:** A native Claude Code `/coach` skill powered by Microsoft's rule content. Claude reads JSONL session files (basic jq stats) and applies the rule descriptions using its own reasoning — no TypeScript DSL interpreter needed.

**Sync model:** Rules are fetched from upstream by `sync.sh`, stored in `ai/skills/coach/rules/` (gitignored — upstream content), and re-synced when updates are wanted. The user controls when to pull.

**Why this works:**
- Rule files contain everything Claude needs in plain English (descriptions, examples, improvement advice)
- Claude's reasoning replaces the compiled DSL interpreter
- Updates pull from the same source that powers the VS Code extension dashboard

---

## Step 1 — Create `sync.sh`

**Files:** `ai/skills/coach/sync.sh`

**Accepts:** `bash ai/skills/coach/sync.sh` populates `ai/skills/coach/rules/` with 45 `.md` files.

Uses `gh api` to fetch only the rule files and coaching persona — no full clone needed:

```bash
#!/usr/bin/env bash
# Syncs AI Engineering Coach rules from microsoft/AI-Engineering-Coach
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES_DIR="$SKILL_DIR/rules"
mkdir -p "$RULES_DIR"

gh api "repos/microsoft/AI-Engineering-Coach/git/trees/main?recursive=1" \
  --jq '.tree[] | select(.path | startswith("src/core/rules/")) | .path' |
while IFS= read -r path; do
  name=$(basename "$path")
  gh api "repos/microsoft/AI-Engineering-Coach/contents/$path" \
    --jq '.content' | base64 -d > "$RULES_DIR/$name"
done

gh api "repos/microsoft/AI-Engineering-Coach/contents/src/chat/system-prompt.ts" \
  --jq '.content' | base64 -d > "$SKILL_DIR/coach-persona.ts"

echo "Synced $(ls "$RULES_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ') rules to $RULES_DIR"
```

---

## Step 2 — Create `/coach` skill

**Files:** `ai/skills/coach/SKILL.md`

**Accepts:** `/coach` produces a coaching response citing specific upstream rule IDs with concrete improvement actions drawn from the synced rule files.

**SKILL.md frontmatter:**
```yaml
name: coach
version: 1.0.0
description: >
  On-demand AI engineering coaching using the Microsoft AI Engineering Coach rule catalog
  (synced from microsoft/AI-Engineering-Coach). Reads Claude Code session logs and surfaces
  personalized anti-pattern feedback. Run sync.sh first to populate rules from upstream.
triggers:
  - coach me
  - how am I using AI
  - review my AI usage
  - AI coaching session
  - show my anti-patterns
  - am I using AI well
  - what bad habits do I have
  - coach sync
```

**Skill execution steps:**

1. **Sync check:** If `ai/skills/coach/rules/` is empty or missing, run `sync.sh` first
2. **Load rules:** Read all `ai/skills/coach/rules/*.md` — each has `id`, `name`, `group`, `severity`, description, trigger conditions, examples, and improvement advice
3. **Load coaching persona:** Read `ai/skills/coach/coach-persona.ts` for the PERSONA constant
4. **Gather session data** via jq on `~/.claude/projects/**/*.jsonl`:
   - Message counts per session file (mega-sessions)
   - User message char lengths (lazy-prompting)
   - Model names from assistant lines (model-overreliance)
   - Tool names from tool_use blocks (yolo-mode, agentic-no-tools)
   - Slash commands in user messages (no-plan-mode, no-slash-commands)
5. **Apply rules:** Match data against each rule's trigger description; note severity
6. **Output:** Top 3 triggered rules (high severity first), citing the rule's upstream "How to Improve" text verbatim; plus 1 strength (non-triggered rule)

**Modes:**
| Invocation | Behavior |
|-----------|---------|
| `/coach` | Last 7 days of sessions |
| `/coach sync` | Run `sync.sh` to pull latest rules from upstream |
| `/coach check <rule-id>` | Load one rule file and assess whether it applies |

---

## Step 3 — Gitignore and `setup.sh`

**Files:** `.gitignore`, `setup.sh`

- `.gitignore`: add entries for `ai/skills/coach/rules/` and `ai/skills/coach/coach-persona.ts` (upstream content, not ours to track)
- `setup.sh`: add one line after the skill symlink block — `bash "$HOME/.dotfiles/ai/skills/coach/sync.sh"` (idempotent; safe to re-run)

---

## Step 4 — Cleanup

**Files:** `plans/session-handoff.md`

Delete the handoff file (fully read and incorporated into this plan).

---

## File Scope

| File | Action | Why |
|------|--------|-----|
| `ai/skills/coach/sync.sh` | Create | Fetches rules + persona from upstream |
| `ai/skills/coach/SKILL.md` | Create | Skill definition; loads synced upstream rules |
| `ai/skills/coach/rules/` | Populated by sync (gitignored) | Upstream rule content |
| `.gitignore` | Edit | Exclude upstream content from dotfiles |
| `setup.sh` | Edit | Auto-sync on install |
| `plans/session-handoff.md` | Delete | Consumed |

`setup.sh` skill symlink loop — **no change.** Auto-discovers `ai/skills/coach/SKILL.md`.

---

## Verification

1. `bash ai/skills/coach/sync.sh` → "Synced 45 rules"
2. `ls ai/skills/coach/rules/*.md | wc -l` → 45
3. `~/.claude/skills/coach/SKILL.md` symlink resolves correctly after `setup.sh`
4. `/coach` → response cites specific upstream rule IDs with verbatim improvement text
5. `/coach sync` → re-syncs, updated count reported
6. `/coach check mega-sessions` → loads `rules/mega-sessions.md` and assesses fit

---

## Out of Scope

- Building/installing the VS Code extension (no published releases; skill is the CLI path)
- Reimplementing the TypeScript DSL interpreter (Claude's reasoning replaces it)
- Syncing rule test cases or DSL `detect` blocks (not needed for Claude-driven analysis)
- MCP server registration (VS Code extension only; no standalone server)
