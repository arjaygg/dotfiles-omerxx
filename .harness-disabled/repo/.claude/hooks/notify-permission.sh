#!/usr/bin/env bash
# Notification hook: macOS notification when Claude needs permission approval
# Hook event: Notification (matcher: .*)

osascript -e 'display notification "Claude Code needs your approval" with title "Claude Code" sound name "Ping"' 2>/dev/null || true
