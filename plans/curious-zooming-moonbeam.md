# Self-Learning Prompt Library — Implementation Plan

## Context

All prompts sent to Claude Code are ephemeral — good patterns get lost across sessions. This plan builds an automated capture → scoring → curation pipeline so effective prompts graduate into `ai/prompts/` where the **existing skill picker** (`Ctrl+A /`, `skill-picker.sh`) already surfaces them.

The picker is already built — it reads `ai/prompts/*.md` and pastes content into the active pane via `tmux load-buffer` + `paste-buffer`. What's missing is the **pipeline that populates `ai/prompts/`** with battle-tested prompts.

**Branch:** `feat/self-learning-prompt-library`

### Existing infrastructure (DO NOT rebuild)

| Component | Location | Keybinding |
|---|---|---|
| Skill/prompt picker | `tmux/scripts/skill-picker.sh` | `Ctrl+A /` |
| Prompt source dir | `ai/prompts/*.md` | (scanned by picker) |
| Injection mechanism | `tmux load-buffer` + `paste-buffer` | Enter in picker |
| Preview | `cat {3}` in fzf `--preview` | Alt-P in picker |

### Design decisions (from risk analysis)

1. **SQLite from the start** — avoids JSONL→SQLite migration later. Same effort, no tech debt.
2. **Transcript import (Step 0)** — bootstrap from existing `~/.claude/projects/` JSONL transcripts so there's data to score immediately.
3. **No new picker** — the existing `skill-picker.sh` already handles `ai/prompts/*.md`. The pipeline's job is to populate that directory.
4. **Privacy filter** — skip prompts containing potential secrets (API keys, internal URLs, tokens).
5. **Min 8 words** — 3-word filter too crude; 8 words catches most throwaway prompts.
6. **Two-tier architecture** — SQLite is the working store (all captured prompts + scores). `ai/prompts/` is the curated library (only promoted prompts). The picker reads the curated tier.

---

## Phase 1 — Capture + Scoring

**Goal:** Every meaningful Claude Code prompt is captured to SQLite with basic effectiveness scoring. No UI changes — this is the data layer.
**Dependencies:** None (sqlite3, jq already installed on macOS).

### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS prompts (
  id TEXT PRIMARY KEY,          -- 8-char hex (sha256 of timestamp+prompt)
  timestamp TEXT NOT NULL,       -- ISO-8601
  prompt TEXT NOT NULL,
  session_id TEXT,
  project TEXT,
  branch TEXT,
  repo_root TEXT,
  word_count INTEGER,
  score INTEGER DEFAULT 0,
  reuse_count INTEGER DEFAULT 0,
  starred INTEGER DEFAULT 0,     -- manual curation flag
  promoted INTEGER DEFAULT 0,    -- 1 = graduated to ai/prompts/
  deleted INTEGER DEFAULT 0,
  tags TEXT DEFAULT '[]',        -- JSON array (for Phase 2 clustering)
  llm_rating REAL DEFAULT 0,    -- Phase 3: LLM judge score
  embedding BLOB                 -- Phase 2: float32[768] via sqlite-vec
);
```

**Data location:** `~/.local/share/prompt-library/prompts.db` (XDG, outside git).

### Step 0 — Transcript import (bootstrap)
**Files:** `.claude/scripts/prompt-library-import.sh`
**Accepts:** Running the script populates the DB with prompts extracted from existing Claude Code transcripts.

- Scan `~/.claude/projects/` for JSONL transcript files
- Extract user messages (role=human) from each transcript
- Apply same filters as capture hook (≥8 words, no slash commands, no secrets)
- Derive project/branch from the encoded directory name
- Correlate with `git log` timestamps for basic scoring: if a commit happened within 5 min of the prompt, score +3
- Insert into SQLite, dedup by prompt text hash
- Idempotent (safe to re-run)

### Step 1 — Capture hook
**Files:** `.claude/hooks/prompt-capture.sh`
**Accepts:** Typing a prompt in Claude Code inserts a row into SQLite; <8-word prompts, slash commands, and sensitive prompts are skipped; zero perceptible latency.

- Read stdin JSON, extract `.prompt` via jq
- Filter: skip if empty, <8 words, starts with `/`, or matches secret patterns (`(?i)(api[_-]?key|bearer |token=|password|secret)`)
- Derive metadata: `session_id`, project (basename of cwd), branch (git)
- Generate `id` = first 8 chars of `shasum -a 256` of timestamp+prompt
- Insert into SQLite via `sqlite3` CLI
- Run insert in background (`&`) to avoid latency
- Follow stdin pattern from `prompt-parallelism-hint.sh` lines 10-11

### Step 2 — Scoring hooks
**Files:** `.claude/hooks/prompt-score-commit.sh`, `.claude/hooks/prompt-score-correction.sh`, `.claude/scripts/prompt-library-score.sh`
**Accepts:** Prompts leading to commits get +3; corrected prompts get -1.

- `prompt-library-score.sh <id> <delta>` — utility: `UPDATE prompts SET score = score + $delta WHERE id = '$id'`
- `prompt-score-commit.sh` — PostToolUse hook, fires after Bash when command contains `git commit`, scores most recent prompt +3
- `prompt-score-correction.sh` — UserPromptSubmit hook, checks if prompt contains correction patterns ("no", "wrong", "undo", "revert", "actually", "instead") within 60s of prior prompt, scores prior prompt -1

### Step 3 — Hook registration
**Files:** `.claude/settings.json`
**Accepts:** All hooks fire correctly.

- Add 3 hook entries: capture (UserPromptSubmit), score-commit (PostToolUse), score-correction (UserPromptSubmit)

### Step 4 — Manual review CLI
**Files:** `.claude/scripts/prompt-library-review.sh`
**Accepts:** User can review top-scoring prompts and star/promote them from the terminal.

- `prompt-library-review.sh top` — show top 20 by score
- `prompt-library-review.sh star <id>` — toggle starred flag
- `prompt-library-review.sh promote <id>` — generate `ai/prompts/<slug>.md` from the prompt, set `promoted=1`
- Promoted file format: markdown with frontmatter matching skill-picker expectations

### Phase 1 verification
- [ ] `sqlite3 ~/.local/share/prompt-library/prompts.db "SELECT count(*) FROM prompts"` shows imported prompts
- [ ] Typing a prompt in Claude Code → `sqlite3 ... "SELECT * FROM prompts ORDER BY timestamp DESC LIMIT 1"` shows it
- [ ] `prompt-library-review.sh top` shows scored prompts
- [ ] `prompt-library-review.sh promote <id>` creates a file in `ai/prompts/`
- [ ] The promoted prompt appears in `Ctrl+A /` picker
- [ ] Prompts with <8 words and slash commands are not captured
- [ ] Prompts containing secret patterns are not captured

---

## Phase 2 — Embeddings: Similarity & Dedup

**Goal:** Near-duplicate prompts merge; semantic search enhances the review CLI.
**Dependencies:** Phase 1 complete. `ollama pull nomic-embed-text`, sqlite-vec installed.

### Setup

- `brew install ollama` (if not already), `ollama pull nomic-embed-text` (0.5GB, Apple Silicon Metal)
- sqlite-vec: `pip install sqlite-vec` or download .dylib from GitHub releases

### Step 5 — Embedding sync
**Files:** `.claude/scripts/prompt-library-embed.sh`
**Accepts:** All prompts in SQLite have embeddings; near-duplicates (cosine > 0.92) are auto-merged.

- Add `prompt_vec` virtual table: `CREATE VIRTUAL TABLE prompt_vec USING vec0(id TEXT PRIMARY KEY, embedding float[768])`
- For each prompt without embedding: call Ollama API (`curl -s http://localhost:11434/api/embeddings`), store result
- On new insert: check cosine similarity against existing vectors; if > 0.92, increment existing record's reuse_count instead of inserting
- Run as background post-insert step in capture hook (or periodic cron)

### Step 6 — Semantic search in review CLI
**Files:** modify `.claude/scripts/prompt-library-review.sh`
**Accepts:** `prompt-library-review.sh search "describe what you want"` returns semantically similar prompts from the DB.

- Embed query via Ollama → query `prompt_vec` for top-K → display results
- Helps find promotion candidates by describing the *type* of prompt you want

### Phase 2 verification
- [ ] `sqlite3 ... "SELECT count(*) FROM prompt_vec"` matches prompt count
- [ ] Submitting a near-duplicate prompt increments reuse_count instead of creating new row
- [ ] `prompt-library-review.sh search "refactor code"` returns semantically relevant results

---

## Phase 3 — Self-Learning: Auto-Curation

**Goal:** High-scoring prompts are auto-reviewed by LLM and promoted to `ai/prompts/` where the existing picker surfaces them.
**Dependencies:** Phase 2 complete.

### Step 7 — LLM-as-judge evaluation
**Files:** `.claude/scripts/prompt-library-judge.sh`
**Accepts:** Prompts with score >= 5 and reuse_count >= 2 (or starred) are rated by Ollama; ratings stored in `llm_rating` column.

- Batch script: select eligible prompts → send to Ollama (llama3.2) with judge prompt
- Judge criteria: "Rate this prompt 1-10 for clarity, specificity, and reusability across different projects. If >= 7, extract a reusable template by replacing project-specific details with {PROJECT}, {BRANCH}, {FILE} placeholders."
- Store rating + extracted template in DB

### Step 8 — Auto-promotion
**Files:** `.claude/scripts/prompt-library-auto-promote.sh`
**Accepts:** Prompts rated >= 7 are auto-promoted to `ai/prompts/<slug>.md`; appears in existing `Ctrl+A /` picker.

- Reuses the same promotion logic from `prompt-library-review.sh promote` (Step 4)
- Replace project-specific names with `{PROJECT}`, branches with `{BRANCH}`, paths with `{FILE}`
- Write as markdown with frontmatter (name, description, tags, source_id, llm_rating)
- Set `promoted=1` in DB to avoid re-promoting
- Optional: `prompt-library-cron.sh` orchestrator to run embed + judge + auto-promote in sequence

### Phase 3 verification
- [ ] `sqlite3 ... "SELECT prompt, llm_rating FROM prompts WHERE llm_rating >= 7"` shows judged prompts
- [ ] `ls ai/prompts/` shows auto-promoted templates
- [ ] Templates have project-specific details replaced with placeholders
- [ ] Auto-promoted prompts appear in `Ctrl+A /` picker alongside skills and commands

---

## Tools & Dependencies Summary

| Phase | New Dependencies | Effort |
|---|---|---|
| 1 (Capture + Scoring) | None (sqlite3, jq) | ~120 lines, 6 files |
| 2 (Embeddings) | ollama (nomic-embed-text), sqlite-vec | ~65 lines, 2 files |
| 3 (Self-Learning) | ollama (llama3.2, already have) | ~80 lines, 2 files |

**Premium alternatives (not needed but noted):** LangSmith, Braintrust, Humanloop, Portkey, Langfuse (self-hostable). All cloud-oriented, overkill for local-first use. promptfoo is worth considering for eval if Phase 3 scaling needs it.

---

## Architecture Summary

```
                    ┌─────────────────────────┐
                    │  Claude Code session     │
                    │  (user types prompt)     │
                    └──────────┬──────────────┘
                               │ UserPromptSubmit hook
                               ▼
                    ┌─────────────────────────┐
                    │  prompt-capture.sh       │
                    │  (filter + insert)       │
                    └──────────┬──────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │  SQLite (working store)  │  ← ~/.local/share/prompt-library/prompts.db
                    │  all prompts + scores    │
                    │  + embeddings (Phase 2)  │
                    └──────────┬──────────────┘
                               │ promote (manual or auto)
                               ▼
                    ┌─────────────────────────┐
                    │  ai/prompts/*.md         │  ← curated library (git-tracked)
                    │  (battle-tested only)    │
                    └──────────┬──────────────┘
                               │ scanned by
                               ▼
                    ┌─────────────────────────┐
                    │  skill-picker.sh         │  ← Ctrl+A / (ALREADY EXISTS)
                    │  (fzf + tmux paste)      │
                    └─────────────────────────┘
```

---

## Critical Reference Files

- `.claude/hooks/prompt-parallelism-hint.sh` — UserPromptSubmit stdin pattern (lines 10-11)
- `tmux/scripts/skill-picker.sh` — **existing picker** that reads `ai/prompts/*.md` (lines 47-51, 86-94)
- `tmux/tmux.conf` line 89 — `Ctrl+A /` keybinding for skill-picker
- `.claude/scripts/context-eval-log.sh` — logging pattern reference
- `.claude/settings.json` lines 249-278 — hook registration format
- `~/.claude/projects/` — transcript JSONL files for Step 0 import
