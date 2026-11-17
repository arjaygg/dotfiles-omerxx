#!/usr/bin/env python3
"""PreToolUse guard: keep edits out of an opted-in repo's primary checkout on the default branch.

User-level. Opt a repository in with `git config worktreeguard.enabled true` (the key lives in
the shared .git/config, so every worktree sees it). A guardrail for a cooperative agent, not a
security boundary. Decisions:

- Edit, Write, NotebookEdit: judged by the target file's repository.
- Bash: git verbs that change the tree or history (commit, merge, pull, reset, checkout, ...), plus shell writes (`>`/`>>`, tee, cp, mv, rm,
  mkdir, touch, ln, install, truncate, dd of=, sed -i, perl -i, and python/node/ruby one-liners
  that write). The write targets are judged: absolute and ~ paths, relative paths against the
  working directory (following a leading `cd`). Reads, tests and `git status/log/diff/show/
  worktree add` pass. THE BASH CHECK IS A HEURISTIC: it reads the command text, so a script
  that writes on its own, variable-built paths, `xargs`, or `eval` are not seen.
- Allowed: another repository, a linked worktree, a non-default branch, a bare repo.
- Allowed: any repository that has not opted in.
- Ask (or deny): the primary checkout of an opted-in repo on main, master or a detached HEAD.

Mode, most specific first: WORKTREE_GUARD_MODE set at launch (`ask`, `deny`, `off`) overrides
everything; otherwise `git config worktreeguard.mode` of the judged repo; default `ask`.
An unknown mode value or an error while judging asks instead of allowing silently.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_BRANCHES = {"main", "master"}
MODES = {"ask", "deny", "off"}
FILE_TOOLS = {"Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}
GIT_WRITE_VERBS = {
    "commit", "cherry-pick", "revert", "rebase", "am", "apply", "merge", "pull", "reset",
    "checkout", "switch", "restore", "clean", "rm", "mv", "add",
}
GIT_STASH_READ = {"list", "show"}
GIT_OPT_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1([^\n]*)\n.*?\n\s*\2(?=\s|$)", re.S)
REDIRECT = re.compile(r"(?:\d|&)?>>?(?!&)\s*([^\s;|&<>()]+)")
ALL_ARGS = {"rm", "mkdir", "rmdir", "touch", "truncate", "tee", "mv", "patch"}
MODE_ARG = {"chmod", "chown", "chgrp"}
LAST_ARG = {"cp", "install", "ln"}
WRAPPERS = {"sudo", "command", "env", "nohup", "time", "exec"}
SUDO_VALUE_FLAGS = {"-u", "-g", "-C", "-h", "-p", "-U", "-T", "-R", "-D"}
PY_PATH_ARG = re.compile(
    r"""(?:open|Path|remove|rename|replace|unlink|makedirs|mkdir|rmtree|copy\w*|move|writeFile\w*"""
    r"""|appendFile\w*)\(\s*['"]([^'"]+)['"]"""
)
INLINE_INTERP = {"python", "python3", "node", "ruby", "perl"}
INLINE_WRITE = re.compile(
    r"open\([^)]*['\"][wax]\+?b?['\"]|write_text|write_bytes|writeFile|appendFile|File\.write"
    r"|os\.(?:remove|rename|replace|unlink|makedirs|mkdir)|shutil\.|\.unlink\(|\.write\("
)
REASON = (
    "This repository's primary checkout is on %s. Call EnterWorktree and make the change there. "
    "The user can approve a one-off edit, or launch with WORKTREE_GUARD_MODE=off."
)
DENY_REASON = (
    "Blocked: this repository's primary checkout is on %s and its guard mode is deny. "
    "Call EnterWorktree and make the change there instead."
)


def git(directory, *args):
    done = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        timeout=10,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    )
    return done.stdout.strip() if done.returncode == 0 else None


def existing_dir(path):
    path = Path(path).expanduser()
    for candidate in [path, *path.parents]:
        if candidate.is_dir():
            return candidate
    return None


def repo_facts(directory):
    """(git_dir, common_dir, branch) as real paths; None when not a normal repository."""
    if directory is None or git(directory, "rev-parse", "--is-bare-repository") != "false":
        return None
    git_dir = git(directory, "rev-parse", "--absolute-git-dir")
    common = git(directory, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not git_dir or not common:
        return None
    branch = git(directory, "symbolic-ref", "-q", "--short", "HEAD")
    return os.path.realpath(git_dir), os.path.realpath(common), branch


def resolve(path, cwd):
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.join(cwd, path)


def split_segments(command):
    """Split on ; & | && || and newlines, but not inside quotes."""
    segments, current, quote, i = [], [], None, 0
    while i < len(command):
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(command):
                current.append(command[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            current.append(ch)
        elif ch == "\\" and i + 1 < len(command):
            current.append(command[i : i + 2])
            i += 1
        elif ch in ";&|\n" and not (ch == "&" and current and current[-1] in "<>"):
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    segments.append("".join(current))
    return segments


def split_tokens(segment):
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def mask_quotes(segment):
    """Hide `>` inside quotes so a quoted `>` is not read as a redirect."""
    out, quote = [], None
    for ch in segment:
        if quote:
            out.append("\x00" if ch == ">" else ch)
            if ch == quote:
                quote = None
        else:
            quote = ch if ch in "'\"" else None
            out.append(ch)
    return "".join(out)


def redirect_targets(segment, cwd):
    found = []
    for m in REDIRECT.finditer(mask_quotes(segment)):
        target = m.group(1).replace("\x00", ">").strip("'\"")
        if target and target != "/dev/null":
            found.append(resolve(target, cwd))
    return found


def git_write_dir(words, cwd):
    """Directory of a tree- or history-changing git command, else None. words[0] is git."""
    base, i = cwd, 1
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "-C" and i + 1 < len(words):
            base = resolve(words[i + 1], base)
        i += 2 if words[i] in GIT_OPT_WITH_VALUE else 1
    if i >= len(words):
        return None
    verb = words[i]
    if verb == "stash":
        sub = words[i + 1] if i + 1 < len(words) else ""
        return None if sub in GIT_STASH_READ else base
    return base if verb in GIT_WRITE_VERBS else None


def edit_in_place_args(words):
    """Path arguments of sed/perl when run in place (-i), else []."""
    in_place, scripted, args, i = False, False, [], 1
    while i < len(words):
        w = words[i]
        if w in ("-e", "-f"):
            scripted = True
            i += 2
            continue
        if w.startswith("-") and w != "-":
            in_place = in_place or bool(re.match(r"^-\w*i", w) or w.startswith("--in-place"))
            if re.match(r"^-[a-zA-Z]*[ef]$", w) and w not in ("-i",):
                scripted = True  # combined flags such as perl -pe / -pie take the script next
                i += 2
                continue
        elif w:
            args.append(w)
        i += 1
    if not in_place:
        return []
    return args if scripted else args[1:]


def inline_write_targets(raw, cwd):
    literal = PY_PATH_ARG.findall(raw)
    absolute = re.findall(r"""['"]((?:~|/)[^'"\s]*)['"]""", raw)
    paths = [resolve(t, cwd) for t in literal + absolute]
    return paths or [cwd]


def segment_targets(tokens, cwd, segment):
    """Paths a command segment may write to (absolute), judged heuristically."""
    targets = redirect_targets(segment, cwd)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "=" in tok.split("/")[0] and not tok.startswith("-"):
            i += 1
        elif tok in WRAPPERS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 2 if tok == "sudo" and tokens[i] in SUDO_VALUE_FLAGS else 1
        else:
            break
    words = tokens[i:]
    if not words:
        return targets
    raw = " ".join(tokens)
    cmd = os.path.basename(words[0])
    args = [w for w in words[1:] if w and not w.startswith("-") and not REDIRECT.search(w)]
    if cmd in ALL_ARGS:
        targets += [resolve(a, cwd) for a in args]
    elif cmd in ("sed", "perl"):
        targets += [resolve(a, cwd) for a in edit_in_place_args(words)]
    elif cmd in MODE_ARG:
        targets += [resolve(a, cwd) for a in args[1:]]
    elif cmd in LAST_ARG and args:
        targets.append(resolve(args[-1], cwd))
    elif cmd == "dd":
        targets += [resolve(w[3:], cwd) for w in words if w.startswith("of=")]
    elif cmd == "git":
        base = git_write_dir(words, cwd)
        if base is not None:
            targets.append(base)
    elif re.match(r"^(?:python|node|ruby)[\d.]*$", cmd) and INLINE_WRITE.search(raw):
        targets += inline_write_targets(raw, cwd)
    return targets


def bash_targets(command, cwd):
    command = HEREDOC.sub(r" \3", command)
    targets, here = [], cwd
    for segment in split_segments(command):
        tokens = split_tokens(segment.strip())
        while tokens and tokens[0] != tokens[0].lstrip("({"):
            tokens[0] = tokens[0].lstrip("({")
            if not tokens[0]:
                tokens.pop(0)
        if not tokens:
            continue
        if tokens[0] in ("cd", "pushd"):
            rest = [t for t in tokens[1:] if t not in ("--", "-P", "-L", "-e", "-@")]
            if not rest:
                here = os.path.expanduser("~")
            elif rest[0] != "-":
                here = resolve(rest[0], here)
            continue
        targets += segment_targets(tokens, here, segment)
    return targets


def target_dirs(tool, tool_input, cwd):
    if tool in FILE_TOOLS:
        path = tool_input.get(FILE_TOOLS[tool])
        if not isinstance(path, str) or not path:
            return []
        return [existing_dir(resolve(path, cwd))]
    command = tool_input.get("command")
    if tool == "Bash" and isinstance(command, str):
        return [existing_dir(t) for t in bash_targets(command, cwd)]
    return []


def judge_dir(directory):
    """(branch, mode) when this directory is a guarded primary checkout, else None."""
    facts = repo_facts(directory)
    if facts is None:
        return None
    git_dir, common, branch = facts
    if git_dir != common:
        return None  # a linked worktree
    if git(directory, "config", "--bool", "worktreeguard.enabled") != "true":
        return None  # this repository has not opted in
    if branch is not None and branch not in DEFAULT_BRANCHES:
        return None
    mode = (git(directory, "config", "worktreeguard.mode") or "ask").strip().lower()
    return ("a detached HEAD" if branch is None else branch), mode


def judge(tool, tool_input, cwd):
    """Hits for every judged directory: a list of (branch, repo_mode)."""
    hits = []
    for directory in target_dirs(tool, tool_input, cwd):
        hit = judge_dir(directory)
        if hit and hit not in hits:
            hits.append(hit)
    return hits


def answer(decision, reason):
    out = {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }
    print(json.dumps({"hookSpecificOutput": out}))


def decide(hits, env_mode):
    """Combine hits into (decision, branch) or None to allow. deny beats ask beats off."""
    best = None
    for branch, repo_mode in hits:
        mode = env_mode or repo_mode
        mode = mode if mode in MODES else "ask"
        if mode == "off":
            continue
        if best is None or (mode == "deny" and best[0] == "ask"):
            best = (mode, branch)
    return best


def main():
    env_mode = os.environ.get("WORKTREE_GUARD_MODE", "").strip().lower()
    if env_mode == "off":
        return 0
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        cwd = data.get("cwd") or os.getcwd()
        verdict = decide(judge(data.get("tool_name"), tool_input, cwd), env_mode)
    except Exception as exc:
        # Any failure asks instead of allowing silently.
        answer("ask", "worktree guard could not judge this call (%s)" % type(exc).__name__)
        return 0
    if verdict is not None:
        mode, branch = verdict
        answer(mode, (DENY_REASON if mode == "deny" else REASON) % branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
