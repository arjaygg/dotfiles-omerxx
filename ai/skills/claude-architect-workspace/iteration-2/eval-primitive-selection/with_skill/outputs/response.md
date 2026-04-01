# Primitive Selection: Hook

This is a **Hook** — it fires automatically on every Read tool call (PostToolUse), requires no user invocation, and runs in shell-only context with no Claude involvement.

## Hook Script

File: `~/.dotfiles/.claude/hooks/read-audit.sh`

The script reads stdin JSON from Claude Code, extracts the file path from the Read tool's input, and appends a timestamped line to `~/.claude/read-audit.log`.

## Settings Registration

Register under `PostToolUse` with matcher `"Read"` in `~/.claude/settings.json`.

## Files Created

- `read-audit.sh` — hook script (PostToolUse, non-blocking, always exits 0)
- `settings-snippet.json` — settings.json fragment to register the hook

## Confirmation

`~/.dotfiles/.claude/hooks/read-audit.sh` created — logs every Read tool file path to `~/.claude/read-audit.log` automatically on each session.
