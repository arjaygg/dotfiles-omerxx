---
name: rtk
description: >
  RTK (Rust Token Killer) — token-optimized CLI proxy. A shell hook transparently rewrites
  commands (e.g. `git status` → `rtk git status`) at zero token overhead, so normal use needs
  no action. Use this skill for the meta-commands (savings stats, discovery, bypass) and for
  troubleshooting a wrong `rtk` binary on PATH.
triggers:
  - rtk gain
  - rtk discover
  - rtk proxy
  - token savings
  - rtk
---

# RTK — Rust Token Killer

Token-optimized CLI proxy. A hook transparently rewrites shell commands (e.g. `git status` →
`rtk git status`) at 0 token overhead — **no action needed for normal use**.

## Meta commands

Use these directly; they are not hook-rewritten.

| Command | Purpose |
|---|---|
| `rtk gain` | Token-savings stats for the current session |
| `rtk gain --history` | Savings across past sessions |
| `rtk discover` | Find commands not yet routed through rtk (missed opportunities) |
| `rtk proxy <cmd>` | Run `<cmd>` bypassing rtk filtering (debugging) |

## Troubleshooting

⚠️ If `rtk gain` fails, check `which rtk` — the binary on PATH may be
`reachingforthejack/rtk` (Rust Type Kit), a different project with the same name.
