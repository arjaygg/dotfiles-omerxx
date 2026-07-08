#!/usr/bin/env bash
# bg-job.sh — persistent local background job runner.
#
# Starts an arbitrary command fully detached from the invoking shell / tmux
# pane / Claude Code process (new session, no controlling terminal, stdio on
# /dev/null + log file), so it survives the originating session, pane, window,
# and tmux server being CLOSED — not merely detached. Any later shell or
# Claude Code session can rediscover the job and read its status, exit code,
# and logs.
#
# Registry location: ~/.claude/bg-jobs/<repo-slug>/<job-id>/
#   - Deliberately OUTSIDE the repo: worktree conventions copy .claude/ per
#     worktree, so an in-repo registry would fragment across worktrees. A
#     user-level dir keyed by a stable repo identity (remote origin URL
#     basename, falling back to the shared git-common-dir) means every
#     worktree and every session of the same repo sees ONE registry.
#   - Override with BG_JOB_ROOT for testing.
#
# Per-job files:
#   cmd        exact command string (run via `bash -c`)
#   cwd        directory the job was started from (runner cds there)
#   meta       key=value: name, repo, created_at, launcher
#   pid        runner PID (written by the runner itself, its own session)
#   pgid       runner process group (used by `stop` to kill the whole tree)
#   started_at / ended_at   UTC timestamps
#   log        combined stdout+stderr of the command
#   exit_code  written by the runner when the command finishes — the
#              authoritative "finished" marker (PIDs get reused; never trust
#              `ps` alone for exit status)
#
# Detachment mechanism (macOS-aware):
#   1. `setsid` binary if present (Linux, or brew util-linux on macOS)
#   2. perl POSIX::setsid fork+setsid+exec (/usr/bin/perl ships with macOS;
#      macOS has NO native setsid binary)
#   3. nohup + disown as a last resort (same session, but SIGHUP ignored)
# In paths 1-2 the runner ends up with: new session (session leader,
# pgid == pid), PPID 1 (reparented to init/launchd), TTY "??". Closing the
# originating tmux pane/session delivers SIGHUP only to process groups of
# THAT terminal's session — the runner is in a different session with no
# controlling terminal, so nothing is delivered to it.
#
# Limitations: jobs do NOT survive a machine reboot (that would need a
# launchd LaunchAgent / systemd unit). After a reboot, un-finished jobs show
# as "dead" (no exit_code, PID gone).

set -euo pipefail

REGISTRY_ROOT="${BG_JOB_ROOT:-$HOME/.claude/bg-jobs}"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

die() { printf 'bg-job: %s\n' "$*" >&2; exit 1; }

# Stable repo identity shared by all worktrees/clones of the same repo.
repo_slug() {
  local url dir
  if url=$(git config --get remote.origin.url 2>/dev/null) && [ -n "$url" ]; then
    url=${url%/}; url=${url%.git}
    printf '%s' "${url##*[/:]}" | tr -c 'A-Za-z0-9._-' '-'
  elif dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
    printf '%s' "$(basename "$(dirname "$dir")")" | tr -c 'A-Za-z0-9._-' '-'
  else
    printf '_global'
  fi
}

sanitize() { printf '%s' "$1" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//;s/-*$//'; }

job_dir() {
  local id=$1 base
  base="$REGISTRY_ROOT/$(repo_slug)"
  [ -d "$base/$id" ] && { printf '%s' "$base/$id"; return 0; }
  # allow unambiguous prefix match
  local matches=()
  for d in "$base/$id"*/; do [ -d "$d" ] && matches+=("${d%/}"); done
  [ ${#matches[@]} -eq 1 ] && { printf '%s' "${matches[0]}"; return 0; }
  [ ${#matches[@]} -gt 1 ] && die "ambiguous job id '$id' (${#matches[@]} matches)"
  die "no such job '$id' under $base"
}

# Running = no exit_code yet AND pid alive AND that pid is really our runner
# (its argv contains the unique job dir — guards against PID reuse).
job_running() {
  local dir=$1 pid
  [ -f "$dir/exit_code" ] && return 1
  [ -f "$dir/pid" ] || return 1
  pid=$(cat "$dir/pid")
  kill -0 "$pid" 2>/dev/null || return 1
  ps -o command= -p "$pid" 2>/dev/null | grep -qF "$dir"
}

job_status() {
  local dir=$1
  if [ -f "$dir/exit_code" ]; then
    printf 'exited:%s' "$(cat "$dir/exit_code")"
  elif job_running "$dir"; then
    printf 'running'
  else
    printf 'dead'   # no exit code, process gone (SIGKILL, crash, or reboot)
  fi
}

launch_detached() {
  local dir=$1
  if command -v setsid >/dev/null 2>&1; then
    printf 'launcher=setsid\n' >> "$dir/meta"
    setsid bash "$SCRIPT_PATH" __runner "$dir" < /dev/null > /dev/null 2>&1 &
  elif command -v perl >/dev/null 2>&1; then
    printf 'launcher=perl-setsid\n' >> "$dir/meta"
    perl -MPOSIX=setsid -e '
      my $p = fork(); defined $p or die "fork: $!";
      exit 0 if $p;
      setsid() != -1 or die "setsid: $!";
      exec @ARGV or die "exec: $!";
    ' -- bash "$SCRIPT_PATH" __runner "$dir" < /dev/null > /dev/null 2>&1
  else
    printf 'launcher=nohup\n' >> "$dir/meta"
    nohup bash "$SCRIPT_PATH" __runner "$dir" < /dev/null > /dev/null 2>&1 &
    disown 2>/dev/null || true
  fi
}

# --- runner: executes inside the detached session -------------------------
cmd_runner() {
  local dir=$1 child ec
  trap '' HUP                       # belt-and-braces for the nohup fallback
  printf '%s\n' "$$" > "$dir/pid"
  ps -o pgid= -p "$$" | tr -d ' ' > "$dir/pgid"
  cd "$(cat "$dir/cwd")" 2>/dev/null || cd /
  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/started_at"
  set +e
  # Run the command as a child so that `stop` (SIGTERM to the process group)
  # does not kill the runner before it can record the exit code: the runner
  # traps TERM/INT, forwards them, and waits for the child's real status.
  bash -c "$(cat "$dir/cmd")" < /dev/null >> "$dir/log" 2>&1 &
  child=$!
  trap 'kill -TERM "$child" 2>/dev/null' TERM INT
  wait "$child"; ec=$?
  while kill -0 "$child" 2>/dev/null; do wait "$child"; ec=$?; done
  set -e
  printf '%s\n' "$ec" > "$dir/exit_code"
  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/ended_at"
}

# --- CLI subcommands -------------------------------------------------------
cmd_start() {
  local name=""
  while [ $# -gt 0 ]; do
    case $1 in
      -n|--name) name=$2; shift 2 ;;
      --) shift; break ;;
      -*) die "unknown start flag: $1" ;;
      *) break ;;
    esac
  done
  [ $# -gt 0 ] || die "usage: bg-job start [-n name] -- <command ...>"

  local cmd
  if [ $# -eq 1 ]; then
    cmd=$1                          # single arg: treat as a shell string
  else
    cmd=$(printf '%q ' "$@")        # multiple args: quote each safely
  fi
  [ -n "$name" ] || name=$(sanitize "$(basename "${1%% *}")")
  [ -n "$name" ] || name="job"

  local slug id dir
  slug=$(repo_slug)
  id="${name}-$(date +%Y%m%d-%H%M%S)-$(printf '%04x' $((RANDOM % 65536)))"
  dir="$REGISTRY_ROOT/$slug/$id"
  mkdir -p "$dir"
  printf '%s\n' "$cmd" > "$dir/cmd"
  pwd > "$dir/cwd"
  : > "$dir/log"
  {
    printf 'name=%s\n' "$name"
    printf 'repo=%s\n' "$slug"
    printf 'created_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$dir/meta"

  launch_detached "$dir"

  local i=0
  while [ ! -s "$dir/pid" ] && [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done
  [ -s "$dir/pid" ] || die "job did not start (no pid after 5s); see $dir"

  printf '%s\n' "$id"
  printf 'pid=%s  log=%s\n' "$(cat "$dir/pid")" "$dir/log" >&2
}

cmd_list() {
  local base="$REGISTRY_ROOT/$(repo_slug)" dir id st started cmd
  [ -d "$base" ] || { printf 'no jobs for repo %s\n' "$(repo_slug)"; return 0; }
  printf '%-45s %-12s %-20s %s\n' "JOB ID" "STATUS" "STARTED (UTC)" "COMMAND"
  for dir in "$base"/*/; do
    [ -d "$dir" ] || continue
    dir=${dir%/}
    id=$(basename "$dir")
    st=$(job_status "$dir")
    started=$(cat "$dir/started_at" 2>/dev/null || printf '?')
    cmd=$(head -c 60 "$dir/cmd" 2>/dev/null | tr '\n' ' ')
    printf '%-45s %-12s %-20s %s\n' "$id" "$st" "$started" "$cmd"
  done
}

cmd_status() {
  local dir; dir=$(job_dir "${1:?usage: bg-job status <job-id>}")
  printf 'job:     %s\n' "$(basename "$dir")"
  printf 'status:  %s\n' "$(job_status "$dir")"
  printf 'pid:     %s (pgid %s)\n' "$(cat "$dir/pid" 2>/dev/null || echo '?')" "$(cat "$dir/pgid" 2>/dev/null || echo '?')"
  printf 'cwd:     %s\n' "$(cat "$dir/cwd" 2>/dev/null || echo '?')"
  printf 'command: %s\n' "$(cat "$dir/cmd")"
  printf 'started: %s\n' "$(cat "$dir/started_at" 2>/dev/null || echo '?')"
  [ -f "$dir/ended_at" ] && printf 'ended:   %s\n' "$(cat "$dir/ended_at")"
  printf 'log:     %s\n' "$dir/log"
  if [ -s "$dir/log" ]; then
    printf -- '--- last 20 log lines ---\n'
    tail -n 20 "$dir/log"
  fi
}

cmd_logs() {
  local follow="" n=50
  while [ $# -gt 0 ]; do
    case $1 in
      -f|--follow) follow=1; shift ;;
      -n) n=$2; shift 2 ;;
      *) break ;;
    esac
  done
  local dir; dir=$(job_dir "${1:?usage: bg-job logs [-f] [-n N] <job-id>}")
  if [ -n "$follow" ]; then tail -n "$n" -f "$dir/log"; else tail -n "$n" "$dir/log"; fi
}

cmd_stop() {
  local dir pgid i
  dir=$(job_dir "${1:?usage: bg-job stop <job-id>}")
  job_running "$dir" || { printf 'job %s is not running (%s)\n' "$(basename "$dir")" "$(job_status "$dir")"; return 0; }
  pgid=$(cat "$dir/pgid")
  kill -TERM -- "-$pgid" 2>/dev/null || true
  i=0
  while job_running "$dir" && [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done
  if job_running "$dir"; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
    printf 'job %s: SIGKILL sent to pgid %s\n' "$(basename "$dir")" "$pgid"
  else
    printf 'job %s: stopped\n' "$(basename "$dir")"
  fi
}

cmd_prune() {
  local days=7 base dir st ref now cutoff ended
  case "${1:-}" in --days) days=$2; shift 2 ;; esac
  base="$REGISTRY_ROOT/$(repo_slug)"
  [ -d "$base" ] || return 0
  now=$(date +%s); cutoff=$((now - days*86400))
  for dir in "$base"/*/; do
    [ -d "$dir" ] || continue
    dir=${dir%/}
    st=$(job_status "$dir")
    [ "$st" = running ] && continue
    ref="$dir/ended_at"; [ -f "$ref" ] || ref="$dir"
    ended=$(stat -f %m "$ref" 2>/dev/null || stat -c %Y "$ref" 2>/dev/null || echo "$now")
    if [ "$ended" -lt "$cutoff" ]; then
      rm -rf "$dir"
      printf 'pruned %s (%s)\n' "$(basename "$dir")" "$st"
    fi
  done
}

usage() {
  cat <<'EOF'
usage: bg-job.sh <subcommand>
  start [-n name] -- <command ...>   start a detached job, print its job id
  list                               list this repo's jobs with status
  status <job-id>                    detail + last log lines (prefix match ok)
  logs [-f] [-n N] <job-id>          tail the job log
  stop <job-id>                      SIGTERM (then SIGKILL) the job's process group
  prune [--days N]                   delete finished job records older than N days (default 7)
Registry: ~/.claude/bg-jobs/<repo-slug>/ (override: BG_JOB_ROOT)
EOF
}

case "${1:-}" in
  __runner) shift; cmd_runner "$@" ;;
  start)    shift; cmd_start "$@" ;;
  list)     shift; cmd_list "$@" ;;
  status)   shift; cmd_status "$@" ;;
  logs)     shift; cmd_logs "$@" ;;
  stop)     shift; cmd_stop "$@" ;;
  prune)    shift; cmd_prune "$@" ;;
  -h|--help|help|"") usage ;;
  *) die "unknown subcommand: $1 (try --help)" ;;
esac
