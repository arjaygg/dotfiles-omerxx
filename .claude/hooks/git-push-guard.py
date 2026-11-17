#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash): force a permission prompt for risky git pushes.

Risky = force/delete/mirror pushes, pushes to main/master (explicit, by refspec, or
implicit via the current branch), and any push to the arjaygg remote. Plain pushes of
a feature branch pass through. Fails open: any parse error prints nothing.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "master"}
RISKY_REMOTES = {"arjaygg"}
OPS = {"&&", "||", ";", "|", "&"}
GLOBAL_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def current_branch(cwd):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "symbolic-ref", "--short", "-q", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def dst_of(refspec):
    spec = refspec.lstrip("+")
    dst = spec.split(":", 1)[1] if ":" in spec else spec
    return re.sub(r"^refs/heads/", "", dst)


def analyze_push(args, cwd):
    """args = tokens after 'push' up to the next shell operator. Returns reason or None."""
    flags = [a for a in args if a.startswith("-")]
    pos = [a for a in args if not a.startswith("-")]
    for f in flags:
        if f.startswith(("--force-with-lease", "--force-if-includes")):
            continue  # safe force variants; protected-branch checks below still apply
        if f == "-f" or f.startswith("--force") or f in ("--mirror", "--all", "--prune"):
            return "push uses %s (force or bulk push)" % f
    remote = pos[0] if pos else ""
    if remote in RISKY_REMOTES:
        return "push targets the %s remote (may be public)" % remote
    refspecs = pos[1:]
    for r in refspecs:
        if r.startswith("+"):
            return "refspec %s forces the update" % r
        if dst_of(r) in PROTECTED:
            return "push targets protected branch %s" % dst_of(r)
    if not refspecs:
        branch = current_branch(cwd)
        if branch in PROTECTED:
            return "bare push while on protected branch %s" % branch
    return None


def check(command, cwd):
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        tokens = command.split()
    i = 0
    while i < len(tokens):
        t = tokens[i]
        # shell -c "git push ..." : inspect the inner command string
        if os.path.basename(t) in ("bash", "sh", "zsh") and "-c" in tokens[i + 1:i + 3]:
            j = tokens.index("-c", i)
            if j + 1 < len(tokens):
                inner = check(tokens[j + 1], cwd)
                if inner:
                    return inner
        if os.path.basename(t) == "git":
            j = i + 1
            run_cwd = cwd
            while j < len(tokens) and tokens[j].startswith("-"):
                opt = tokens[j]
                if opt in GLOBAL_OPTS_WITH_ARG:
                    if opt == "-C" and j + 1 < len(tokens):
                        run_cwd = tokens[j + 1] if os.path.isabs(tokens[j + 1]) else os.path.join(cwd, tokens[j + 1])
                    j += 2
                else:
                    j += 1
            if j < len(tokens) and tokens[j] == "push":
                k = j + 1
                args = []
                while k < len(tokens) and tokens[k] not in OPS:
                    args.append(tokens[k])
                    k += 1
                reason = analyze_push(args, run_cwd)
                if reason:
                    return reason
        i += 1
    return None


def main():
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command", "")
        cwd = data.get("cwd") or os.getcwd()
        reason = check(command, cwd) if "push" in command else None
    except Exception:
        return
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "git-push-guard: " + reason,
        }}))


main()
