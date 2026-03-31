# Session Next — Open Next Priority Session

Automatically find and open the next highest-priority pending session in a tmux window. No interaction needed — just picks the top one and launches it.

## Instructions

### Step 1: Parse arguments and determine scope

Check `$ARGUMENTS` for commands and filters. Parse left-to-right:
- `list` — don't open, just show the ranked queue with scores
- `skip <name>` — skip a specific session and open the one after it
- Any other word — treated as a **project filter** (substring match against decoded path)

> **Note:** To defer/undefer sessions, use the separate `/session-defer` and `/session-undefer` commands.

Examples:
- `/session-next auc-conversion` — only auc-conversion and its worktrees
- `/session-next` (no filter) — scan all projects

The filter is a substring match against the decoded filesystem path. This means `auc-conversion` matches both the main repo and all `.trees/*` worktrees under it.

### Step 2: Scan project directories

**Two sources of candidates:**

**Source A — Session files:** List all directories under `~/.claude/projects/` that contain `*.jsonl` session files. For each:
- Get the latest session file (by mtime), its size, and ID (basename without `.jsonl`)
- Skip tiny sessions (<10KB)
- Decode the project dir name to its filesystem path
- **If a project filter was given in Step 1, skip any path that doesn't contain the filter string**

**Source B — Handoff-only worktrees (no session yet):** Scan for worktrees that have `plans/session-handoff.md` with `status: pending` but no corresponding `.jsonl` in `~/.claude/projects/`. These are newly created worktrees (e.g. via `stack-create`) that haven't had a Claude session started yet. Identify them by:
- Looking at git worktrees under any project matching the filter: `git worktree list`
- Checking if the worktree path has `plans/session-handoff.md` with `status: pending`
- Checking that `~/.claude/projects/` has NO directory encoding that worktree path with a valid `.jsonl`
- If found, add as a candidate with `session_id: none`

### Step 3: Filter to actionable sessions only

For each project directory, check its decoded filesystem path:
- Skip if path doesn't exist on disk (worktree already removed)
- Skip if `plans/session-handoff.md` contains `status: complete` or `status: abandoned`
- Skip if the branch is already merged to main (`git branch --merged main | grep <branch>`)
- Skip if `plans/progress.md` exists and has NO unchecked `- [ ]` boxes (all done)
- **Skip if already open in tmux** — see "Duplicate Detection" below

### Step 3a: Duplicate Detection (CRITICAL)

Do NOT rely on tmux window names. Use **pane working directories** as ground truth:

1. Get all open pane paths: `tmux list-panes -t dev -s -F '#{pane_current_path}'`
2. For each candidate session, get its **actual cwd** by parsing the `.jsonl` session file:
   - Read the first ~5 lines of the jsonl
   - Find the line with a `cwd` field (usually line 2, the `type: summary` entry)
   - This is where `claude --resume` will actually run — it may differ from the project directory encoding
3. If the session's actual `cwd` matches any open pane path → skip it (already open)
4. Also check the decoded project dir path against pane paths (covers cases where cwd is missing)

### Step 4: Rank remaining sessions

Score each session by priority:
1. **+50** — has uncommitted code changes (data loss risk)
2. **+30** — commits ahead of main > 10 (significant unmerged work)
3. **+20** — commits ahead of main 1-10
4. **+10** — `plans/session-handoff.md` exists with `status: pending`
5. **+5** — session file size > 100KB (deep conversation history)
6. **-10** — last modified > 7 days ago (stale, lower priority)
7. **-30** — `plans/session-handoff.md` contains `status: deferred`

Pick the highest-scoring session.

### Step 5: Open it

1. Derive a short tmux window name from the worktree/project name
2. Create a new tmux window in the `dev` session (without shell arg to avoid naming conflicts)
3. **If the session has a session ID** (normal case): send keys to `cd` to the session's actual cwd, then `claude --resume <session-id>`
4. **If no session ID** (handoff-only worktree from stack-create): send keys to `cd` to the worktree path, then `claude` (fresh session, no `--resume`)

```bash
# Case A: resume existing session
tmux new-window -t dev -n "<name>" && sleep 0.3 && \
tmux send-keys -t dev:<name> "cd <actual-cwd> && claude --resume <session-id>" Enter

# Case B: fresh session in new worktree
tmux new-window -t dev -n "<name>" && sleep 0.3 && \
tmux send-keys -t dev:<name> "cd <worktree-path> && claude" Enter
```

Report for Case B:
```
Opened (new session): <name> (branch: <branch>, no prior session) → tmux dev:<window>
```

### Step 6: Report

Print a one-line summary:
```
Opened: <name> (branch: <branch>, <N> ahead, <status>) → tmux dev:<window-number>
Next in queue: <name-of-second-priority> (<score>)
```

If no actionable sessions remain, print:
```
All sessions are complete, abandoned, or merged. Nothing to pick up.
```

### Key rule

`claude --resume <id>` MUST be executed from the same directory the session was originally created in. Parse the session's `cwd` from the jsonl — do NOT assume the decoded project directory path is correct.

## Arguments

- `$ARGUMENTS` — optional, space-separated. Parsed in order:
  - `list` — don't open, just show the ranked queue with scores
  - `skip <name>` — skip a specific session and open the one after it
  - `defer <name>` — deprioritize a session (-30 score penalty)
  - `undefer <name>` — remove deferred status, restore to normal scoring
  - Any other word — treated as a **project filter** (substring match against decoded path)

### Examples

```
/session-next                          # next across all projects
/session-next auc-conversion           # next within auc-conversion + worktrees
/session-next auc-conversion list      # show ranked queue for auc-conversion only
/session-next activtrak                # next within activtrak
/session-next list                     # show full ranked queue, don't open
/session-next skip observability       # skip that session, open the one after
```
