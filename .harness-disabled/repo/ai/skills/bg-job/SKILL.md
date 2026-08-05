---
name: bg-job
description: "Launch, list, and manage long-running LOCAL OS processes (builds, index/migration scripts, long computations) that survive the Claude Code session exiting AND the launching tmux pane/window/session being closed, and remain discoverable — with status, exit code, and logs — from any later session, repo, or git worktree. Use when a local process must outlive this session. NOT for Kubernetes Jobs (already persistent via the K8s control plane) and NOT a replacement for Claude-agent-level primitives (Monitor, /loop, CronCreate, Bash run_in_background)."
triggers:
  - "/bg-job"
---

# /bg-job — Persistent Local Background Jobs

Runs an arbitrary command fully detached from the invoking shell / tmux /
Claude Code process: new session via `setsid(2)` (perl `POSIX::setsid`
fallback on macOS, which has no `setsid` binary), stdin from `/dev/null`,
stdout+stderr to a per-job log file, reparented to PID 1, no controlling
terminal. Closing the pane, window, tmux session, or exiting Claude Code
cannot deliver SIGHUP to it.

This is a machine-wide (user-scoped) capability — usable from any repo or
worktree, not tied to a single project.

All state lives in a **user-level registry** at
`~/.claude/bg-jobs/<repo-slug>/<job-id>/` — deliberately outside any repo,
because per-repo worktree conventions often copy `.claude/` per worktree and
an in-repo registry would fragment across worktrees. The slug is derived
from the git remote origin URL (falling back to the shared git-common-dir),
so every worktree and every session of the same repo sees one registry. When
run outside any git repo, jobs fall under the `_global` slug.

## Usage

```
/bg-job start [-n name] -- '<command>'   # start detached job, prints job id
/bg-job list                             # this repo's jobs + status
/bg-job status <job-id>                  # detail + last log lines (prefix match ok)
/bg-job logs [-f] [-n N] <job-id>        # tail the log
/bg-job stop <job-id>                    # SIGTERM (then SIGKILL) the job's process group
/bg-job prune [--days N]                 # delete finished records older than N days (default 7)
```

## Instructions

The implementation is `~/.dotfiles/scripts/ai/bg-job.sh`. Map the user's
request to a subcommand and run it via Bash — it prints everything needed:

```bash
~/.dotfiles/scripts/ai/bg-job.sh start -n reindex -- 'go run ./cmd/reindex --full'
~/.dotfiles/scripts/ai/bg-job.sh list
~/.dotfiles/scripts/ai/bg-job.sh status reindex-20260708
~/.dotfiles/scripts/ai/bg-job.sh logs -n 100 reindex-20260708
```

- `start` prints the job id on stdout (pid + log path on stderr). Report the
  job id to the user — it's the handle any future session uses.
- Status values: `running`, `exited:<code>` (authoritative — the runner
  writes the exit code to a file; never inferred from `ps`, since PIDs get
  reused), `dead` (process gone with no exit code: SIGKILL, crash, or reboot).
- `stop` signals the whole process group; the runner traps TERM and records
  the real exit status (e.g. `exited:143`).
- Job ids accept unambiguous prefixes for `status`/`logs`/`stop`.
- `list`/`status`/`logs`/`stop`/`prune` scope to the current directory's repo
  (via `repo_slug()`) — run them from within the relevant repo/worktree.

## When to use what (do not confuse these)

| Need | Use |
|---|---|
| Local OS process that must survive session/terminal death | **this skill** |
| Shell command finishing within this session | `Bash(run_in_background: true)` |
| Notify when a file/log/condition changes | `Monitor` tool |
| Recurring LLM work on a schedule | `/loop`, `CronCreate` (+ `RemoteTrigger`) |
| Cluster workloads | Kubernetes Jobs (already persist server-side) |

## Limitations

- Jobs do **not** survive a machine reboot — the process dies with the OS.
  After reboot, unfinished jobs show as `dead`. True boot persistence would
  need a launchd LaunchAgent (macOS) or systemd unit, out of scope here.
- The registry is per-machine and per-user; a job started on another host is
  not visible.
