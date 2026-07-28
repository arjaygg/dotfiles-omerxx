#!/usr/bin/env python3
"""Remove machine-local-only keys from `.claude/settings.json` on its way into a commit.

Why
---
`skipDangerousModePermissionPrompt: true` is a deliberate local default on this
machine — it lives in `.claude/settings.local.json`, which is gitignored and takes
precedence over the tracked file. But Claude Code also writes the key into
`~/.claude/settings.json`, and that path is a symlink into this repo, so the value
keeps arriving in a tracked, published file where
`test_tracked_settings_do_not_enable_dangerous_mode_bypass` rejects it.

Stripping it from the *staged* blob is therefore lossless: the runtime keeps the
setting from the local overlay, and the commit stays clean. Same split as
`normalize_home_paths.py` — the working copy is never touched.

Minimal-diff by design
----------------------
The key's line is removed textually rather than by re-serialising the document,
because `json.dump` would reformat all ~580 lines and bury the real change. The
result is re-parsed to guarantee validity, and a dangling comma is repaired if the
removed key happened to be the last member of its object.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Keys that are legitimate machine-local settings but must never be committed.
# Each belongs in .claude/settings.local.json (gitignored, higher precedence).
LOCAL_ONLY_KEYS: tuple[str, ...] = ("skipDangerousModePermissionPrompt",)


def _drop_top_level_key(text: str, key: str) -> str:
    """Remove a top-level `"key": <scalar>` line, repairing a dangling comma."""
    pattern = re.compile(rf'^[ \t]*"{re.escape(key)}"[ \t]*:[^\n]*\n', re.M)
    stripped = pattern.sub("", text, count=1)
    if stripped == text:
        return text

    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        # The key was the final member, so the preceding line's trailing comma is
        # now dangling. Drop that one comma and re-validate.
        repaired = re.sub(r",(\s*[}\]])", r"\1", stripped, count=1)
        json.loads(repaired)  # raises if we still broke it — better than emitting junk
        return repaired


def strip_local_only(text: str, keys: tuple[str, ...] = LOCAL_ONLY_KEYS) -> str:
    """Remove every local-only key. Idempotent. Raises on invalid input JSON."""
    json.loads(text)  # refuse to touch a file we cannot parse
    for key in keys:
        text = _drop_top_level_key(text, key)
    return text


def present_keys(text: str, keys: tuple[str, ...] = LOCAL_ONLY_KEYS) -> list[str]:
    document = json.loads(text)
    return [k for k in keys if k in document]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if a local-only key is present",
    )
    parser.add_argument("--label", default="<stdin>", help="path label for messages")
    args = parser.parse_args(argv)

    original = sys.stdin.read()
    try:
        found = present_keys(original)
    except json.JSONDecodeError as exc:
        print(f"{args.label}: not valid JSON, refusing to edit: {exc}", file=sys.stderr)
        return 2

    if args.check:
        if found:
            print(
                f"{args.label}: local-only key(s) present: {', '.join(found)}",
                file=sys.stderr,
            )
            return 1
        return 0

    result = strip_local_only(original)
    if found:
        print(
            f"{args.label}: stripped {', '.join(found)} "
            f"(kept in .claude/settings.local.json)",
            file=sys.stderr,
        )
    sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
