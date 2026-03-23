#!/usr/bin/env bash
# Render the current context-evaluation metrics from the local gitignored store.

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
STORE_DIR="${CONTEXT_EVAL_STORE_DIR:-$REPO_ROOT/.claude/cache/context-eval}"
STORE_FILE="$STORE_DIR/events.jsonl"
CURRENT_MODE="${CONTEXT_EVAL_MODE:-baseline}"

python3 - "$REPO_ROOT" "$STORE_DIR" "$STORE_FILE" "$CURRENT_MODE" <<'PYEOF'
import json
import sys
from pathlib import Path

repo_root, store_dir, store_file, current_mode = sys.argv[1:5]
store_path = Path(store_file)


def pct(part: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{(part / total) * 100:.0f}%"


def ratio(value: float) -> str:
    return f"{value:.2f}"


def delta_line(label: str, base_value: float, trial_value: float, lower_is_better: bool) -> str:
    delta = trial_value - base_value
    if abs(delta) < 1e-9:
        verdict = "no change"
    elif lower_is_better:
        verdict = "better" if delta < 0 else "worse"
    else:
        verdict = "better" if delta > 0 else "worse"
    sign = "+" if delta > 0 else ""
    return f"- {label}: baseline {base_value:.2f} → context-mode {trial_value:.2f} ({sign}{delta:.2f}, {verdict})"


def empty_stats(mode: str) -> dict:
    return {
        "mode": mode,
        "events": 0,
        "session_starts": 0,
        "starts_with_handoff": 0,
        "notifications": 0,
        "warnings_30": 0,
        "warnings_15": 0,
        "warnings_5": 0,
        "artifact_risk_notifications": 0,
        "precompact": 0,
        "precompact_manual": 0,
        "precompact_auto": 0,
        "bash_events": 0,
        "bash_compactions": 0,
        "bash_output_lines_total": 0,
        "stops": 0,
        "handoff_writes": 0,
        "latest_timestamp": None,
    }


def summarize(mode: str, events: list[dict]) -> dict:
    stats = empty_stats(mode)
    for event in events:
        stats["events"] += 1
        stats["latest_timestamp"] = event.get("timestamp") or stats["latest_timestamp"]
        name = event.get("event")
        data = event.get("data") or {}
        if name == "session-start":
            stats["session_starts"] += 1
            if data.get("handoff_present"):
                stats["starts_with_handoff"] += 1
        elif name == "notification":
            if data.get("matched_context_warning"):
                stats["notifications"] += 1
            remaining = data.get("context_remaining")
            if isinstance(remaining, int):
                if remaining <= 30:
                    stats["warnings_30"] += 1
                if remaining <= 15:
                    stats["warnings_15"] += 1
                if remaining <= 5:
                    stats["warnings_5"] += 1
            if data.get("artifact_risk"):
                stats["artifact_risk_notifications"] += 1
        elif name == "pre-compact":
            stats["precompact"] += 1
            trigger = data.get("trigger")
            if trigger == "manual":
                stats["precompact_manual"] += 1
            elif trigger == "auto":
                stats["precompact_auto"] += 1
        elif name == "post-bash":
            stats["bash_events"] += 1
            stats["bash_output_lines_total"] += int(data.get("output_line_count") or 0)
            if data.get("compacted"):
                stats["bash_compactions"] += 1
        elif name == "stop":
            stats["stops"] += 1
            if data.get("handoff_written"):
                stats["handoff_writes"] += 1

    sessions = max(stats["session_starts"], 1)
    stops = max(stats["stops"], 1)
    bash_events = max(stats["bash_events"], 1)

    stats["warnings_per_session"] = stats["notifications"] / sessions
    stats["precompact_per_session"] = stats["precompact"] / sessions
    stats["handoff_start_rate"] = stats["starts_with_handoff"] / sessions
    stats["handoff_write_rate"] = stats["handoff_writes"] / stops
    stats["bash_compaction_rate"] = stats["bash_compactions"] / bash_events
    stats["avg_bash_output_lines"] = stats["bash_output_lines_total"] / bash_events
    return stats


if not store_path.exists() or store_path.stat().st_size == 0:
    print("# Context Evaluation Report")
    print("")
    print(f"- Repo: `{repo_root}`")
    print(f"- Store: `{store_dir}`")
    print(f"- Current mode: `{current_mode}`")
    print("")
    print("No evaluation data has been captured yet.")
    print("")
    print("Automatic coverage starts after the new hooks fire at least once.")
    sys.exit(0)

records = []
with open(store_path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)

modes: dict[str, list[dict]] = {}
for record in records:
    mode = record.get("mode") or "baseline"
    modes.setdefault(mode, []).append(record)

stats_by_mode = {mode: summarize(mode, items) for mode, items in modes.items()}
mode_names = sorted(stats_by_mode.keys())

print("# Context Evaluation Report")
print("")
print(f"- Repo: `{repo_root}`")
print(f"- Store: `{store_dir}`")
print(f"- Current mode: `{current_mode}`")
print(f"- Captured events: **{len(records)}**")
print(f"- Modes seen: {', '.join(f'`{m}`' for m in mode_names)}")
print("")
print("## Automated coverage")
print("")
print("This report currently measures:")
print("- context warning frequency from `Notification`")
print("- compaction frequency from `PreCompact`")
print("- large Bash-output compaction from `PostToolUse(Bash)`")
print("- handoff presence/write coverage from `SessionStart` and `Stop`")
print("")
print("Still manual later:")
print("- resume quality after `/compact`")
print("- operator effort / recovery friction")
print("- subjective output noise / cleanliness")

for mode in mode_names:
    stats = stats_by_mode[mode]
    print("")
    print(f"## Mode: `{mode}`")
    print("")
    print(f"- Last event: `{stats['latest_timestamp']}`" if stats["latest_timestamp"] else "- Last event: none")
    print(f"- Session starts: **{stats['session_starts']}**")
    print(f"- Notifications: **{stats['notifications']}** ({ratio(stats['warnings_per_session'])} per session)")
    print(f"- Context warnings ≤30/15/5%: **{stats['warnings_30']} / {stats['warnings_15']} / {stats['warnings_5']}**")
    print(f"- PreCompact events: **{stats['precompact']}** ({ratio(stats['precompact_per_session'])} per session; manual {stats['precompact_manual']}, auto {stats['precompact_auto']})")
    print(f"- Bash outputs seen: **{stats['bash_events']}** (avg {stats['avg_bash_output_lines']:.1f} lines; compacted {stats['bash_compactions']} = {pct(stats['bash_compactions'], stats['bash_events'])})")
    print(f"- Session starts with handoff present: **{stats['starts_with_handoff']} / {stats['session_starts']}** ({pct(stats['starts_with_handoff'], stats['session_starts'])})")
    print(f"- Stop events with handoff written: **{stats['handoff_writes']} / {stats['stops']}** ({pct(stats['handoff_writes'], stats['stops'])})")
    if stats["artifact_risk_notifications"]:
        print(f"- Artifact-risk notifications: **{stats['artifact_risk_notifications']}**")

baseline = stats_by_mode.get("baseline")
trial = stats_by_mode.get("context-mode")
if baseline and trial:
    print("")
    print("## Baseline vs context-mode")
    print("")
    print(delta_line("Notifications per session", baseline["warnings_per_session"], trial["warnings_per_session"], lower_is_better=True))
    print(delta_line("PreCompact events per session", baseline["precompact_per_session"], trial["precompact_per_session"], lower_is_better=True))
    print(delta_line("Handoff-present rate at session start", baseline["handoff_start_rate"], trial["handoff_start_rate"], lower_is_better=False))
    print(delta_line("Handoff-written rate at stop", baseline["handoff_write_rate"], trial["handoff_write_rate"], lower_is_better=False))
    print("")
    improving = 0
    if trial["warnings_per_session"] < baseline["warnings_per_session"]:
        improving += 1
    if trial["precompact_per_session"] < baseline["precompact_per_session"]:
        improving += 1
    if trial["handoff_start_rate"] >= baseline["handoff_start_rate"]:
        improving += 1
    if trial["handoff_write_rate"] >= baseline["handoff_write_rate"]:
        improving += 1
    if improving >= 3:
        print("Automated signal: **favors context-mode so far**.")
    elif improving == 2:
        print("Automated signal: **mixed so far**.")
    else:
        print("Automated signal: **does not favor context-mode yet**.")
elif baseline and not trial:
    print("")
    print("## Trial status")
    print("")
    print("Only `baseline` data is present so far.")
    print("Switch `CONTEXT_EVAL_MODE` to `context-mode` when the trial integration starts so comparisons stay clean.")
elif trial and not baseline:
    print("")
    print("## Trial status")
    print("")
    print("Only `context-mode` data is present so far.")
    print("Capture some `baseline` runs too if you want a direct before/after comparison.")
PYEOF
