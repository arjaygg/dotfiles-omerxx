# Read Audit Hook

## Primitive Decision

**You need a HOOK, not a skill.**

Here's why, using the decision tree from the skill:

- A skill is user-invocable — the user runs a slash command and Claude responds conversationally. That's not what you want here.
- A hook is lifecycle-driven — it fires automatically when something happens in the Claude Code harness, without any user action.

Your goal is: "every time Claude reads a file, silently log it." That maps directly to:

> Triggered automatically when something happens (tool runs) → **HOOK**

Specifically, this is a **PostToolUse** hook matching the `Read` tool. PostToolUse is the right lifecycle event because:
- The file path is only available in the tool input after the tool has been called
- You don't want to block reads (no enforcement, pure tracking)
- Exit 0 always — this hook is transparent to Claude

---

## Artifacts

### Hook script: `read-auditor.sh`

Place at: `~/.dotfiles/.claude/hooks/read-auditor.sh`

The hook:
1. Reads stdin (Claude Code passes JSON on stdin for all hooks)
2. Guards on `tool_name == "Read"` to be safe even if matcher is broad
3. Extracts `tool_input.file_path`
4. Appends a timestamped line to `~/.claude/read-audit.log`
5. Exits 0 — never blocks

Log format:
```
2026-04-01T14:23:05Z READ: /Users/axos-agallentes/git/myrepo/src/main.go
2026-04-01T14:23:07Z READ: /Users/axos-agallentes/.dotfiles/.claude/settings.json
```

### settings.json registration snippet

Merge this into the `hooks.PostToolUse` array in `~/.dotfiles/.claude/settings.json`:

```json
{
  "matcher": "Read",
  "hooks": [
    {
      "type": "command",
      "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/read-auditor.sh\"'"
    }
  ]
}
```

**Note:** Your `settings.json` already has a `read-tracker.sh` registered under PostToolUse/Read (line 225-231). That hook tracks files for the edit-without-read gate (writes to `/tmp/.claude-read-log-<uid>`). The new `read-auditor.sh` is additive — it writes to a persistent audit log at `~/.claude/read-audit.log`. You can add it as a second hook entry under the same `"matcher": "Read"` block, or as a separate matcher entry.

---

## Installation Steps

1. Copy `read-auditor.sh` to `~/.dotfiles/.claude/hooks/read-auditor.sh`
2. Make it executable: `chmod +x ~/.dotfiles/.claude/hooks/read-auditor.sh`
3. Add the settings snippet to `~/.dotfiles/.claude/settings.json` under `hooks.PostToolUse`
4. Verify: trigger a Read in a new Claude Code session, then check `~/.claude/read-audit.log`

---

## Why not a skill?

A skill would require the user to manually run `/read-audit` to capture reads — and by then the session might be over. The hook fires automatically on every Read tool invocation, making it zero-friction and complete.
