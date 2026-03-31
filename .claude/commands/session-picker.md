# Session Picker — Find and Resume Claude Code Sessions

Scan all Claude Code session files, auto-detect completion status, and let the user pick one to resume in a tmux window.

## Instructions

### Step 1: Scan sessions

List all project directories under `~/.claude/projects/` that contain `*.jsonl` session files. For each:
- Count sessions
- Get latest session file date, size, and ID (basename without `.jsonl`)
- Skip tiny sessions (<10KB) — likely empty/accidental
- Sort by most recent first

### Step 2: Decode project paths

Each project dir name encodes the filesystem path:
- `-Users-axos-agallentes-git-auc-conversion` → `/Users/axos-agallentes/git/auc-conversion`
- `--trees-k8s-supervisor-platform` suffix → `.trees/k8s-supervisor-platform/` worktree

### Step 3: Auto-detect session status

For each session, determine its status using these signals (in priority order):

| Signal | Status | How to check |
|---|---|---|
| `plans/session-handoff.md` has `status: complete` | **DONE** | grep for `^status: complete` |
| `plans/session-handoff.md` has `status: abandoned` | **ABANDONED** | grep for `^status: abandoned` |
| Branch merged to main | **DONE** | `git branch --merged main \| grep <branch>` |
| PR merged/closed for branch | **DONE** | `gh pr list --state merged --head <branch>` (if gh available) |
| All `plans/progress.md` boxes checked (no `- [ ]` remaining) | **LIKELY DONE** | grep for unchecked boxes |
| `plans/session-handoff.md` exists with `status: pending` or no status field | **PENDING** | file exists, no complete/abandoned marker |
| Dirty files, no handoff | **ABANDONED** | git status dirty + no handoff |
| Clean, no handoff, >7 days stale | **STALE** | mtime check |

### Step 4: Enrich with git context

For each project with recent sessions, gather:
- Branch name and commits ahead of main/origin
- Uncommitted changes (if any)
- Session count and latest session size (as proxy for conversation depth)

### Step 5: Present ranked list

Show a table with a **Status** column, ranked by priority:
1. **PENDING** — sessions with uncommitted code changes (data loss risk)
2. **PENDING** — sessions with branches far ahead of main (unmerged work)
3. **PENDING** — recent sessions with large conversation history
4. **STALE** — old sessions that may need cleanup
5. **LIKELY DONE** — all progress checked, may just need merge/cleanup
6. **DONE** / **ABANDONED** — show only if user passes `--all` or `all` argument

Default: hide DONE and ABANDONED sessions. Show them with `all` argument.

### Step 6: Resume selected session

When the user picks a session (by number or name):
1. Decode the project dir to its filesystem path
2. Create a new tmux window in the `dev` session with a descriptive name
3. **CRITICAL**: `cd` to the decoded path FIRST, then run `claude --resume <session-id>`

```bash
tmux new-window -t dev -n "<name>" && sleep 0.5 && \
tmux send-keys -t dev:<name> "cd <decoded-path> && claude --resume <session-id>" Enter
```

### Key rule

`claude --resume <id>` MUST be executed from the same directory the session was originally created in. If run from the wrong directory, it silently opens an empty new session.

## Arguments

- `$ARGUMENTS` — optional filter:
  - `all` — include DONE and ABANDONED sessions
  - `worktree` — only worktree sessions
  - `main` — only main repo sessions
  - `cleanup` — show only DONE/ABANDONED/STALE for cleanup
  - project name — filter to specific project
