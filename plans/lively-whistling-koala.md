# Compaction System Healthcheck & Artifact Resilience

## Context

The three-layer compaction preservation system depends entirely on Claude creating and maintaining `plans/active-context.md`, `plans/decisions.md`, and `plans/progress.md` (Layer 1). No automation creates these files — if Claude forgets, the PreCompact hook injects an empty checkpoint and the Stop hook writes no handoff. Context is silently lost at compaction with no warning to the user or to Claude.

This plan adds three complementary safety nets:
1. A proactive in-context warning when artifact files are missing or stale (before compaction, not after)
2. Escalated desktop notifications when low context coincides with missing artifacts (double jeopardy alert)
3. Skeleton file seeding at session end so future healthchecks degrade gracefully from "missing" (critical) to "stale" (moderate)

---

## Files to Create / Modify

| File | Change |
|---|---|
| `.claude/hooks/plans-healthcheck.sh` | **Create** — new UserPromptSubmit hook |
| `.claude/hooks/context-monitor.sh` | **Modify** — add artifact escalation at low-context thresholds |
| `.claude/hooks/session-end.sh` | **Modify** — add skeleton seeding before the early-exit guard |
| `.claude/settings.json` | **Modify** — register new hook in UserPromptSubmit |

---

## Component A — `plans-healthcheck.sh` (new file)

New `UserPromptSubmit` hook. Fires on every user prompt. Silent when healthy; outputs a structured warning (which becomes a `<system-reminder>` visible to Claude) when action is needed.

**Logic:**
1. Guard: `[[ -d "$CWD/plans" ]] || exit 0` — opt-in via `plans/` presence
2. For each of the three artifact files: check existence, then check `mtime == today` (macOS: `date -r <file> +%Y-%m-%d`)
3. Check if `plans/session-handoff.md` exists (unread prior-session state)
4. If all healthy and no handoff → silent exit 0
5. If issues found → output structured plain-text warning via python3 heredoc

**Warning output structure:**
```
[PLANS HEALTH] Session artifact status:

MISSING (must create before compaction):
  - plans/active-context.md
  - plans/decisions.md
Action: Create missing files now per CLAUDE.md instructions.
  active-context.md — current focus/learnings, ≤30 lines
  decisions.md      — append-only ADL log
  progress.md       — task state in checkbox format

STALE (exist but not updated today):
  - plans/progress.md
Action: Update stale files to reflect current session state.

HANDOFF AVAILABLE: plans/session-handoff.md exists from a prior session.
Action: Read plans/session-handoff.md to restore prior session context, then delete it.
```

Only sections that apply are printed. The hook never exits non-zero.

**Key implementation note:** Use `"${MISSING[*]:-}"` (not `"${MISSING[*]}"`) when passing arrays as strings under `set -euo pipefail` — the `:-` handles the empty-array case that would otherwise trigger "unbound variable".

---

## Component B — Enhanced `context-monitor.sh`

Add an `artifact_status()` function that returns a comma-separated string of problematic files when `plans/` exists and any artifact is missing or stale. Returns empty string otherwise.

Insert a single `ARTIFACT_ISSUES=$(artifact_status)` call before the threshold chain, then escalate within each branch when `ARTIFACT_ISSUES` is non-empty:

| Context % | No artifact issues | Artifact issues |
|---|---|---|
| ≤5% | `"CRITICAL"` — Save and compact NOW | `"ARTIFACT RISK"` — `${pct}% left + missing: ${files}. Update NOW then /compact.` |
| ≤15% | `"Low Context"` — consider /compact | `"ARTIFACT RISK"` — `${pct}% left. Missing: ${files}. Update before compacting!` |
| ≤30% | `"Context Warning"` — standard alert | `"ARTIFACT RISK"` — `${pct}% left. Missing: ${files}.` |

The `artifact_status()` function mirrors `plans-healthcheck.sh` logic but trims paths to basenames to fit macOS notification banner limits.

---

## Component C — Skeleton seeding in `session-end.sh`

**Critical placement:** The skeleton block must be inserted **before** the existing early-exit guard (line 27: `if [[ -z "$ACTIVE_CTX" ]] && [[ -z "$PROGRESS" ]]; then exit 0; fi`). If inserted after, it never runs when all three files are absent — the early exit fires first.

**Logic:** Check if all three artifact files are absent. If yes, write minimal skeleton files using python3. Only runs when ALL THREE are absent — if any one exists, Claude is managing them consciously.

**Skeleton content:** Each file contains a clear HTML comment marking it as a template, not real content. This ensures:
- `pre-compact.sh` injecting the skeleton content is harmless (short, clearly labelled)
- Next session's healthcheck reports "stale" (moderate nudge) not "missing" (critical warning)
- Claude recognises it needs to replace the template with real content

Add `|| true` after the `python3` call to handle read-only filesystem edge cases without breaking the hook.

```
# Active Context
<!-- SKELETON — Claude: update with current session focus (≤30 lines per CLAUDE.md) -->
```

---

## Component D — `settings.json`

Add the new hook to `UserPromptSubmit` alongside `qmd-sync.sh`:

```json
"UserPromptSubmit": [
  {
    "matcher": ".*",
    "hooks": [
      { "type": "command", "command": "bash ~/.dotfiles/.claude/hooks/qmd-sync.sh" },
      { "type": "command", "command": "bash ~/.dotfiles/.claude/hooks/plans-healthcheck.sh" }
    ]
  }
]
```

`qmd-sync.sh` runs first (infrastructure, silent). `plans-healthcheck.sh` runs second (outputs warning only when needed).

---

## Edge Cases

- **Cross-midnight sessions**: Files written before midnight are flagged stale the next day. Minor false positive; Claude updates them and it resolves.
- **Read-only filesystems**: Skeleton seeding uses `|| true` — fails silently without breaking the Stop hook.
- **Handoff file persistence**: The healthcheck reminds Claude to read and delete `session-handoff.md`. If Claude forgets, the reminder repeats each turn. This is intentional persistence. `session-end.sh` already comments "Delete when no longer relevant" on the handoff file.
- **Skeleton content injected at compaction**: `pre-compact.sh` injects `active-context.md` (head 30 lines). A skeleton is ≤3 lines of comment text — negligible token cost, clearly labelled as empty.

---

## Verification

1. Create a test project directory with a `plans/` subdirectory but no artifact files
2. Start a Claude Code session in it and send any message → confirm `[PLANS HEALTH]` warning appears in the system-reminder
3. Let Claude create the artifact files → next message should produce no warning
4. Rename the files to yesterday's date (via `touch -t`) → confirm "STALE" warning appears
5. End the session without creating artifacts → confirm skeleton files were written by `session-end.sh`
6. Trigger a context notification (or mock one) with missing artifacts → confirm desktop notification title changes to "ARTIFACT RISK"
