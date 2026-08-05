# Is `$HOME` in the exec-form `args` array a safe portable-path fix?

**No.** Replacing the hardcoded path with `"$HOME/.dotfiles/.claude/hooks/rtk-rewrite.sh"` inside that same `args` array looks like a fix but is not — it will silently break the hook.

## Why it fails

The entry is **exec-form**:

```json
{"type": "command", "command": "bash", "args": ["/Users/axos-agallentes/.dotfiles/.claude/hooks/rtk-rewrite.sh"]}
```

Exec-form spawns the command via `execve()` directly, with **no shell parsing of the `args` array**. Only Claude Code's own built-in tokens (`$CLAUDE_PROJECT_DIR`, `$CLAUDE_PLUGIN_ROOT`) are substituted inline by Claude Code itself. Any other `$VAR` reference — including `$HOME` — is passed through completely literally: bash would try to open a script file literally named `$HOME/.dotfiles/.claude/hooks/rtk-rewrite.sh` (a path starting with a dollar sign) and fail.

Worse, the failure mode is **silent**: there is no error at settings-load time. The hook simply stops enforcing anything, and nothing tells you. For `rtk-rewrite.sh` that means shell commands quietly stop being rewritten through rtk.

## Why `$CLAUDE_PROJECT_DIR` is also the wrong fix here

`$CLAUDE_PROJECT_DIR` *would* be substituted by Claude Code, but it resolves to whatever project is currently open. That's correct for a hook that ships inside a project — but this repo's `.claude/settings.json` is the **global user settings file**, symlinked into `~/.claude/settings.json` and applied across every project on the machine. The hook script lives at a fixed location (`~/.dotfiles/.claude/hooks/`) and must resolve there regardless of which project triggered it. As soon as you're working in any other repo, `$CLAUDE_PROJECT_DIR` would point at the wrong repo entirely.

## The correct fix: convert the entry to shell-form

Use `$HOME/.dotfiles/...` — matching `setup.sh`'s own hardcoded `~/.dotfiles` clone-location convention — but apply it via **shell-form**, i.e. a single `command` string that goes through a real shell where `$HOME` expands normally:

```json
{"type": "command", "command": "bash -lc '$HOME/.dotfiles/.claude/hooks/rtk-rewrite.sh'"}
```

This makes the entry portable across machines and usernames: the shell expands `$HOME` at hook-invocation time, and the `.dotfiles` clone location is the one invariant `setup.sh` already assumes.

## Verification procedure

Because a bad conversion silently disables that hook's enforcement with no error at settings-load time:

1. Convert **one entry at a time** — don't batch-convert all exec-form entries in `settings.json`.
2. After converting the `rtk-rewrite.sh` entry, **live-test the guarded tool call in a real session** (e.g. run a shell command that rtk-rewrite should rewrite, and confirm the rewrite actually happens).
3. Only after confirming the hook still fires, move on to the next entry.
