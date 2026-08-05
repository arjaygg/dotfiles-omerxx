# Block Direct Push to Main/Master

**Primitive chosen:** PreToolUse hook — because it intercepts Bash commands *before* execution, enabling hard blocking (exit 2) with no side effects on non-matching commands.

## What was built

A blocking hook script at `~/.dotfiles/.claude/hooks/block-main-push.sh` that:
- Intercepts every `Bash` tool invocation
- Exits 0 immediately for any non-Bash tool (never accidentally blocks)
- Checks the command for `git push` targeting `main` or `master`
- Exits 2 with a clear error message if matched, which Claude Code treats as a hard block

## Registration

Add the following to `~/.claude/settings.json` under `hooks`:

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/block-main-push.sh\"'"
      }
    ]
  }
]
```

## Verification

- Non-matching commands (e.g., `git status`, `git push origin feat/my-branch`) pass through unaffected.
- `git push origin main` or `git push --force origin master` are blocked with:
  ```
  BLOCKED: Direct push to main/master not allowed. Use a PR.
  ```

This enforcement is automatic — no per-session instruction needed.
