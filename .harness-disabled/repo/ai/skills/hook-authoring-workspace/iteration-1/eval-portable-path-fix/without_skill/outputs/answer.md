# Is `$HOME` inside the hook `args` array safe? — No.

**Short answer:** No. Dropping `"$HOME/.dotfiles/.claude/hooks/rtk-rewrite.sh"` into the `args` array of a `{"command": "bash", "args": [...]}` hook entry will break the hook. `$HOME` expansion is a **shell** feature — it happens only when a shell parses a command string. The `command` + `args` form exists precisely to bypass shell parsing: the args are passed verbatim (exec-style) to the spawned process. `bash` would receive the literal 21-character string `$HOME/.dotfiles/...` as its script-path argument, look for a file literally named `$HOME/...`, and fail with "No such file or directory" on every matched tool call — and since this file is the global user settings, that failure applies in every project on the machine.

**One factual correction first:** the actual `rtk-rewrite.sh` entry in `.claude/settings.json` (lines 275–283) is *not* the `bash`+`args` shape — it's the bare string form:

```json
{ "type": "command", "command": "/Users/axos-agallentes/.dotfiles/.claude/hooks/rtk-rewrite.sh" }
```

The `bash`+`args` shape described in the question is what all the *other* hooks in the file use (`pre-tool-gate-v2.sh`, `sessionstart.sh`, etc.). The distinction matters because the two forms have opposite answers:

| Form | Executed via | Does `$HOME` expand? |
|---|---|---|
| `"command": "<string>"` (no `args`) | shell (`sh -c` / `bash -c` style) | **Yes** — variables and `~` expand |
| `"command": "bash", "args": ["<path>"]` | direct spawn, no shell | **No** — args passed literally |

Evidence within this same file that the string form is shell-interpreted: line 289 uses `"command": "bash -lc 'lean-ctx hook redirect'"` (quoting only a shell would parse), and the statusline command on line 502 relies on `~` expansion.

## Correct fixes

**For the rtk-rewrite entry as it actually exists (string form)** — just swap the path in place, and quote it so a home directory containing spaces doesn't word-split:

```json
{ "type": "command", "command": "\"$HOME\"/.dotfiles/.claude/hooks/rtk-rewrite.sh" }
```

**For the `bash`+`args` shaped entries** (the shape the question describes), either:

1. Convert them to the string form above (simplest, and consistent), or
2. Keep the args array but make bash itself perform the expansion by going through `-c`:

```json
{
  "type": "command",
  "command": "bash",
  "args": ["-c", "exec \"$HOME/.dotfiles/.claude/hooks/rtk-rewrite.sh\""]
}
```

Here `$HOME` sits inside a string that bash *parses as shell code*, so expansion works. The `exec` avoids leaving an extra bash process in the chain. Note the inner double quotes: without them, a space in the home path breaks the invocation.

## Why not other approaches

- **`~/.dotfiles/...` inside `args`:** fails for the same reason — tilde expansion is also shell-only. It works in the string `command` form, but `$HOME` is the more conventional choice in config that may be machine-generated.
- **`$CLAUDE_PROJECT_DIR`:** wrong tool here. It points at the *current project's* root at hook-fire time. This is the global settings file symlinked to `~/.claude/settings.json` and active in every repo, so `$CLAUDE_PROJECT_DIR` would resolve to whatever project you happen to be in, not the dotfiles repo. It's only appropriate for hooks defined in a project-local `.claude/settings.json` referring to scripts in that same project.

## Two caveats to be aware of

1. **`$HOME` fixes the username, not the clone location.** The path still assumes the repo lives at `~/.dotfiles`. That's consistent with this repo's own conventions (setup.sh, the symlink layout, `AGENTS.md`), so it's a reasonable invariant to keep — but if you ever want the clone location to be flexible too, the clean options are (a) have `setup.sh` render the real absolute path into the installed settings file, or (b) symlink the hooks directory to a stable location under `$HOME` and reference that.

2. **Fix all entries, not just one.** There are ~20 hook entries in this file with the same hardcoded `/Users/axos-agallentes/.dotfiles/...` prefix, plus two that hardcode paths outside the repo: `tmux/scripts/claude-tmux-bridge.sh` (in-repo, same fix) and the SessionEnd hook's `/Users/axos-agallentes/.cargo/bin/lean-ctx` (a per-machine binary path — on a new machine this should become `"$HOME"/.cargo/bin/lean-ctx` in string form, or better, rely on `PATH`). Fixing only `rtk-rewrite.sh` leaves the settings file just as non-portable. The statusline command already uses `~` correctly and needs no change.

## Verification after changing

Hooks config is read at session start, so after editing, start a fresh session and confirm: (1) a benign `Bash` tool call still gets rtk-rewritten (`rtk gain` counter moves), and (2) no "hook command failed" warnings appear. A hook whose script path doesn't resolve fails on *every* matched tool call, so breakage is loud and immediate — but only in the *next* session, which is exactly why an untested `$HOME`-in-args edit is easy to ship broken.
