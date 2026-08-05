# Block Direct Push to main/master

## What Was Set Up

A `PreToolUse` hook that intercepts every `Bash` tool call and exits with code `2` (blocking) if the command matches a `git push` targeting `main` or `master`.

## Files Created

| File | Purpose |
|---|---|
| `block-main-push.sh` | Hook script — reads tool input from stdin, pattern-matches the command, blocks if it targets main/master |
| `settings-snippet.json` | Claude Code settings fragment to register the hook under `PreToolUse` with a `Bash` matcher |

## Hook Design Decisions

### Event: PreToolUse (not PostToolUse)

`PreToolUse` runs **before** the command executes, so it can return exit code `2` to cancel the tool call entirely. `PostToolUse` only observes after the fact — the push would have already happened.

### Blocking vs Observing

Exit code `2` = block + surface the error message to Claude and the user.
Exit code `0` = allow (used on all non-matching paths to avoid false positives).

### Pattern Used

```
git push\b.*\b(main|master)\b
```

This matches:
- `git push origin main`
- `git push --force origin master`
- `git push origin HEAD:main`
- `git push main` (no remote specified)

And does **not** match:
- `git push origin feature/my-branch`
- `git push` (no branch specified — ambiguous, allowed)
- Comments or echo statements containing the word "main"

### Safety: Exit 0 on All Non-Matching Paths

The script exits `0` immediately if:
1. The tool is not `Bash`
2. The command does not match the push pattern

This ensures the hook never accidentally blocks unrelated tool calls.

## How to Register

Merge the `settings-snippet.json` into your `~/.claude/settings.json` (or the project-level `.claude/settings.json`):

```bash
# Merge into global settings
jq -s '.[0] * .[1]' ~/.claude/settings.json settings-snippet.json > /tmp/merged.json \
  && mv /tmp/merged.json ~/.claude/settings.json
```

Or manually add the `PreToolUse` hook array under the `hooks` key in your existing settings file.

## Verification

After registering, ask Claude to run:

```bash
git push origin main
```

You should see:

```
BLOCKED: Direct push to main/master is not allowed. Use a feature branch and create a PR instead.
```

And the push will never execute.
