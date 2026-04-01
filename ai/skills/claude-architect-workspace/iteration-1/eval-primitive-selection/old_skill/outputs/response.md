# Primitive Selection: Read Audit Logging

## Decision: Hook (not a skill)

**Use a PostToolUse hook on the `Read` matcher.**

### Why a hook, not a skill

| Criterion | Skill | Hook |
|---|---|---|
| Triggered automatically on every `Read` | No — must be invoked manually | Yes — fires unconditionally |
| Requires user action | Yes | No |
| Works even when Claude forgets | No | Yes |
| Adds conversational overhead | Yes | No |
| Survives context compaction | N/A | Yes (OS-level process) |

A skill is the right primitive when the user wants to invoke a behaviour on demand. Audit logging is the opposite: it must be silent, automatic, and guaranteed — it fires on every `Read` tool call without Claude's involvement. That is exactly what `PostToolUse` hooks exist for.

### Existing infrastructure note

This dotfiles setup already has `read-tracker.sh` (a PostToolUse/Read hook), but it writes to `/tmp/.claude-read-log-$(id -u)` for a different purpose (edit-without-read enforcement). The audit log is a separate concern:

- Different destination: `~/.claude/read-audit.log` (persistent, not ephemeral `/tmp`)
- Different format: timestamped, session-tagged entries suitable for auditing
- Different retention: permanent until manually rotated

### Hook: `read-audit.sh`

See `read-audit.sh` in this directory.

**What it logs per Read call:**

```
2026-04-01T14:23:01Z  session=abc123  /absolute/path/to/file.py
```

Fields: ISO-8601 UTC timestamp, session ID (from `CLAUDE_SESSION_ID` env var or a stable fallback), absolute file path.

### settings.json snippet

See `settings-snippet.json` in this directory.

Add the hook entry to the existing `PostToolUse.Read` block. The existing `read-tracker.sh` entry stays — the audit hook is additive.

### Wiring summary

1. Copy `read-audit.sh` to `~/.dotfiles/.claude/hooks/read-audit.sh`
2. Make it executable: `chmod +x ~/.dotfiles/.claude/hooks/read-audit.sh`
3. Add the hook entry from `settings-snippet.json` into the `PostToolUse` → `Read` matcher block in `~/.dotfiles/.claude/settings.json`
4. Symlink propagates automatically via the existing dotfiles setup

The log file `~/.claude/read-audit.log` is created automatically on first Read. Rotate it manually with `mv ~/.claude/read-audit.log ~/.claude/read-audit.log.$(date +%Y%m%d)`.
