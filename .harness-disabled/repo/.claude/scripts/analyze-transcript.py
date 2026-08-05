#!/usr/bin/env python3
"""Analyze Claude Code transcript JSONL for hook behavioral effectiveness."""
import json
import sys
from collections import Counter


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze-transcript.py <transcript.jsonl>", file=sys.stderr)
        sys.exit(1)

    transcript_path = sys.argv[1]

    tool_calls = []
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get('type') == 'tool_use':
                    tool_calls.append(entry)
            except json.JSONDecodeError:
                continue

    if not tool_calls:
        print("No tool calls found in transcript.")
        return

    # Tool usage distribution
    tool_counts = Counter(tc.get('tool_name', 'unknown') for tc in tool_calls)
    total = sum(tool_counts.values())

    print("Tool Usage Distribution")
    print("=" * 50)
    for tool, count in tool_counts.most_common():
        pct = 100 * count / total
        print(f"  {tool:<30} {count:>4} ({pct:5.1f}%)")
    print(f"  {'TOTAL':<30} {total:>4}")
    print()

    # Block/recover analysis
    blocked_patterns = {
        'cat': 'Read', 'head': 'Read', 'tail': 'Read',
        'grep': 'Grep', 'rg': 'Grep',
        'find': 'Glob', 'ls': 'Glob',
    }

    block_recover = 0
    block_repeat = 0
    preemptive = 0

    for i, tc in enumerate(tool_calls):
        tool = tc.get('tool_name', '')
        cmd = tc.get('tool_input', {}).get('command', '')

        if tool == 'Bash':
            first_word = cmd.split()[0] if cmd else ''
            if first_word in blocked_patterns:
                # Check if next call uses the correct tool
                if i + 1 < len(tool_calls):
                    next_tool = tool_calls[i + 1].get('tool_name', '')
                    expected = blocked_patterns[first_word]
                    if next_tool == expected:
                        block_recover += 1
                    elif next_tool == 'Bash':
                        next_cmd = tool_calls[i + 1].get('tool_input', {}).get('command', '')
                        next_first = next_cmd.split()[0] if next_cmd else ''
                        if next_first == first_word:
                            block_repeat += 1
        elif tool in ('Read', 'Grep', 'Glob'):
            preemptive += 1

    print("Behavioral Classification")
    print("=" * 50)
    print(f"  Preemptive compliance:  {preemptive}")
    print(f"  Block-then-recover:     {block_recover}")
    print(f"  Block-then-repeat:      {block_repeat}")

    total_events = preemptive + block_recover + block_repeat
    if total_events > 0:
        les = (2 * preemptive + block_recover - 2 * block_repeat) / total_events
        print(f"  Learning Effectiveness Score (LES): {les:.2f}")
    print()


if __name__ == '__main__':
    main()
