---
name: ci-status
description: "Read the current CI watch status from plans/ci-status.md. Use after /ci-watch to check
  progress without interrupting the background agent."
version: 1.0
triggers:
  - "/ci-status"
---

# CI Status Skill

Reads and displays the current CI watch status written by the `/ci-watch` background agent.

## Instructions

Read `plans/ci-status.md` and display its contents to the user.

If the file does not exist, tell the user:
> No active CI watch found. Run `/ci-watch` on a branch with an open PR to start monitoring.

If the file exists, display it as-is — the background agent keeps it current.
