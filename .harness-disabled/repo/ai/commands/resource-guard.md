---
description: 'Check resource guard status or trigger a manual kill sweep'
allowed-tools:
  - Bash(bash /Users/axos-agallentes/.local/bin/resource-guard.sh)
  - Bash(python3 *)
  - Read
---

# Resource Guard — Status & Manual Sweep

Show the resource guard cron status and recent kill log, with option to trigger a manual sweep.

## Instructions

1. Show current cron schedule:
   ```bash
   crontab -l 2>/dev/null | grep resource-guard
   ```

2. Show the last 20 log entries from `~/.local/log/resource-guard.log`

3. Summarize:
   - Current cron interval
   - Total kills today
   - Top offenders by memory (RSS)
   - Whether adaptive scheduling has changed the interval

4. Ask user if they want to trigger a manual sweep now. If yes:
   ```bash
   bash /Users/axos-agallentes/.local/bin/resource-guard.sh
   ```
   Then show updated log tail.
