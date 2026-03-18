---
name: Report output analysis and actions
overview: Interpret the `activtrak report --today` output, explain why Focus Score is 0 and productivity shows 34% Uncategorized, and list concrete user/config/code actions.
todos: []
isProject: false
---

# Analysis of `activtrak report --today` Output and Recommended Actions

## What the output shows

- **Executable table**: ~73 seconds total tracked (47s Ghostty, 12s Edge, 8s Finder, 5s Cisco, 1s Cursor).
- **Focus Score 0/100**: Comes from stored [daily_metrics](src/db.rs) (written by the tracker on a ~60s flush). Formula in [focus_score.rs](src/insights/focus_score.rs): weighted mix of deep-work ratio (40%), inverted switch rate (30%), productive ratio (30%).
- **Deep Work 0m**: Requires a *consecutive* productive block ≥ `min_streak_minutes` (default 25) in [deep_work.rs](src/insights/deep_work.rs). With ~73s total and 8 switches, no such streak exists.
- **Switches 8 total | 450.0/hr**: [switch_counter](src/insights/switch_counter.rs) extrapolates: `count / (window_seconds / 3600)`. For a ~1-minute window, 8 switches → ~400–450/hr.
- **Productivity 65% | 34% Uncategorized**: [reclassify_today](src/main.rs) in `main.rs` re-runs the current [RuleSet](src/productivity.rs) on raw activity. Ghostty and Cursor match “Productive Active” in [productivity_rules.toml](productivity_rules.toml). **Microsoft Edge, Finder, Cisco Secure Client** have no rules → they fall through to **Uncategorized** (default in rules).

---

## Why Focus Score is 0

1. **No deep work**: No 25-minute productive streak → deep-work component = 0 (40% of score).
2. **Very high switch rate**: 450/hr >> default `max_switches_per_hour` (30) → normalized switch component = 1 → inverted term = 0 (30% of score).
3. **Only productive ratio helps**: Even with 65% productive time, the **stored** focus score was computed when the tracker last flushed; with 0 + 0 + (0.65 × 0.30)×100 ≈ 19.5, you’d expect ~20, not 0. So either:
  - The stored `daily_metrics` were written when productive seconds were still 0 (e.g. very early in the session), or
  - The report is showing metrics from a different run (e.g. earlier today) where the session was tiny.

So: **Focus 0 is consistent with a very short, switch-heavy session and no sustained focus block**, and/or with metrics being written before much productive time accumulated.

---

## What we can learn (summary)


| Observation           | Interpretation                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------- |
| Total time ~73s       | Very short tracking window; metrics are volatile.                                           |
| Focus 0, Deep Work 0m | No sustained focus; high context-switching.                                                 |
| 450/hr switches       | Extrapolated from a ~1–2 min window; not necessarily “real” hourly rate.                    |
| 34% Uncategorized     | Edge, Finder, Cisco Secure Client are not in `productivity_rules.toml`.                     |
| 65% Productive        | Ghostty + Cursor classified as productive; rest is uncategorized (and a bit of other apps). |


---

## Recommended actions

### 1. User / behavior (no code)

- **Run the tracker longer** so daily_metrics and focus score reflect a real session (e.g. 30+ minutes).
- **Reduce context switches** and batch work so deep-work streaks can form (e.g. stay in Ghostty/Cursor for 25+ min blocks).
- **Interpret “per hour” with care** when the report is based on < 5 minutes of data; the rate is extrapolated and can look extreme.

### 2. Config: shrink Uncategorized (rules)

Add rules in [productivity_rules.toml](productivity_rules.toml) so Edge, Finder, and Cisco are classified instead of defaulting to Uncategorized:

- **Microsoft Edge**: Add a rule (e.g. `match_executable = "Microsoft Edge"`). Choose status:
  - **Passive** if you use it for communication/docs.
  - **Productive Active** if you use it mainly for work (e.g. Azure DevOps, GitHub, docs).
  - Or use title-based rules (e.g. “Azure DevOps” → Productive) and a catch-all Edge → Passive.
- **Finder**: Usually system/admin; **Passive** or leave as Uncategorized if you prefer.
- **Cisco Secure Client**: VPN; **Passive** is reasonable.

After adding rules, re-run `activtrak report --today`; Uncategorized should drop and Productive/Passive will absorb that time.

### 3. Code / product (optional improvements)

- **Recompute focus in report when useful**: Today’s Focus/Deep Work/Switches come only from stored `daily_metrics`. Option: when generating the report, optionally recompute focus (and show it) from **current** raw activity + reclassified productivity (same inputs as `reclassify_today`) so that “report --today” reflects the latest state even if the tracker hasn’t flushed recently or ran only briefly. That would make the 65% productive time actually influence the displayed score.
- **Short-session caveat**: When total tracked time today is below a threshold (e.g. 5 minutes), print a one-line note: e.g. “Focus and switches/hr are based on a short session and may be volatile.”
- **Docs**: In user-facing docs or AGENTS.md, briefly explain that Focus/Deep Work/Switches are from the last tracker flush and that Productivity % is recomputed from current rules so they can differ in timing.

---

## Summary

- **Learn**: The day was short and switch-heavy; no deep work; 34% uncategorized because three apps have no productivity rules; focus score 0 is driven by 0 deep work and very high extrapolated switch rate (and possibly stale/early daily_metrics).
- **Actions**: (1) Run tracker longer and batch work to improve focus; (2) add rules for Microsoft Edge, Finder, and Cisco Secure Client to reduce Uncategorized; (3) optionally, recompute focus in the report from current activity, add a short-session caveat, and document where the numbers come from.

