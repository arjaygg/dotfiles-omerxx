# Blocking Claude from Pushing to main/master

## What Was Done

Two artifacts were created to enforce a hard block on any Claude-initiated `git push` that targets the `main` or `master` branch:

| File | Purpose |
|---|---|
| `block-main-push.sh` | PreToolUse hook script — inspects every `Bash` tool call and exits `2` (block) when a protected-branch push is detected |
| `settings-snippet.json` | The `hooks` stanza to merge into `~/.claude/settings.json` |

---

## How It Works

Claude Code's hook framework fires **PreToolUse** hooks before executing any tool call. The hook receives a JSON payload on stdin that includes `tool_name` and `tool_input.command`.

The script:
1. Reads the JSON payload from stdin via `jq`.
2. Short-circuits (exit 0) for any tool that is not `Bash`.
3. For `Bash` calls, checks whether the command matches `git push` **and** contains a reference to `main` or `master` (including `HEAD:main`, `HEAD:master`, `--force`, etc.).
4. If both conditions are true, prints a human-readable explanation and exits `2`, which causes Claude Code to surface the block message and abort the tool call.

Exit codes:
- `0` → allow through
- `2` → block and show the message to the user

---

## Installation

### Option A — Merge into your existing `~/.claude/settings.json`

Open `~/.claude/settings.json` and add (or merge) the `hooks` key from `settings-snippet.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOME/.dotfiles/ai/skills/claude-architect-workspace/iteration-1/eval-hook-blocking/old_skill/outputs/block-main-push.sh\""
          }
        ]
      }
    ]
  }
}
```

### Option B — Symlink for dotfiles portability (recommended)

```bash
# Make the script executable
chmod +x ~/.dotfiles/ai/skills/claude-architect-workspace/iteration-1/eval-hook-blocking/old_skill/outputs/block-main-push.sh

# Copy or symlink to a stable hooks directory
ln -sf \
  ~/.dotfiles/ai/skills/claude-architect-workspace/iteration-1/eval-hook-blocking/old_skill/outputs/block-main-push.sh \
  ~/.dotfiles/ai/hooks/block-main-push.sh

# Then reference the stable path in settings.json
```

### Make the script executable

```bash
chmod +x ~/.dotfiles/ai/skills/claude-architect-workspace/iteration-1/eval-hook-blocking/old_skill/outputs/block-main-push.sh
```

---

## What Gets Blocked

| Command pattern | Blocked? |
|---|---|
| `git push origin main` | Yes |
| `git push origin master` | Yes |
| `git push origin HEAD:main` | Yes |
| `git push --force origin main` | Yes |
| `git push origin feature/my-branch` | No — allowed |
| `git push origin HEAD` (no explicit branch) | No — allowed |
| `git push` (bare, no args) | No — allowed (Claude can't know the upstream without extra context) |

> **Note on bare `git push`:** A bare `git push` with a configured upstream *could* target main. If you want to catch that too, add a check that runs `git rev-parse --abbrev-ref --symbolic-full-name @{u}` and blocks when the upstream resolves to `refs/remotes/*/main` or `master`.

---

## Why This Approach

- **Zero human memory required** — the block is enforced by the hook framework before Claude can act, regardless of what the prompt says.
- **Non-destructive** — the hook only blocks the specific tool call; it does not terminate the session or undo any work.
- **Portable** — the script lives in dotfiles and is referenced by path, so it works across machines and worktrees.
- **Transparent** — when blocked, Claude receives and surfaces a clear explanation so the user understands what happened and how to proceed.
