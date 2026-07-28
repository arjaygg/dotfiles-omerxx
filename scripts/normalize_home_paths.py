#!/usr/bin/env python3
"""Rewrite this machine's home directory to `$HOME` in text destined for a commit.

Why this exists
---------------
`lean-ctx doctor --fix` (also `setup` / `wrap`) re-registers its three Claude Code
interception hooks — `read-dedup`, `rewrite`, `redirect` — in `.claude/settings.json`
using the absolute path of its own binary:

    "command": "/Users/<you>/.cargo/bin/lean-ctx hook read-dedup"

`~/.claude/settings.json` is a symlink into this tracked repo, so that
machine-specific path lands in a file we publish, and
`test_tracked_settings_have_no_private_environment_context` fails.

Writing the entry differently does not help: verified empirically that
`doctor --fix` re-absolutises those three entries from `$HOME/...` *and* from a
bare `lean-ctx hook ...`, and re-serialises the whole file. lean-ctx owns them.

So the tracked artifact is kept portable at commit time instead of fighting the
tool: the live file may hold absolute paths (they work fine), while anything
staged is normalised to `$HOME`.

Deliberately conservative: only the *current* machine's home is rewritten. A path
under some other user's home is reported rather than silently rewritten, since
`$HOME` would be the wrong answer for it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from public_hygiene_check import scan_text  # noqa: E402  (needs the path above)


def normalize(text: str, home: str) -> str:
    """Replace `<home>/` with `$HOME/`. Idempotent."""
    home = home.rstrip("/")
    if not home:
        return text
    return text.replace(home + "/", "$HOME/")


def residual_findings(path_label: str, text: str) -> list:
    """absolute-home-path findings still present after normalisation.

    These are paths outside the current home — a different user, or a Windows/UNC
    form. `$HOME` is not a safe substitution for them, so they need a human.
    """
    return [f for f in scan_text(path_label, text) if f.rule == "absolute-home-path"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if input is not already normalised",
    )
    parser.add_argument(
        "--label",
        default="<stdin>",
        help="path label used in reported findings",
    )
    parser.add_argument(
        "--home",
        default=str(Path.home()),
        help="home directory to rewrite (default: this machine's)",
    )
    args = parser.parse_args(argv)

    original = sys.stdin.read()
    normalized = normalize(original, args.home)

    residual = residual_findings(args.label, normalized)
    if residual:
        for finding in residual:
            print(
                f"{args.label}:{finding.line}: absolute home path outside "
                f"$HOME, needs manual review: {finding.excerpt}",
                file=sys.stderr,
            )
        return 2

    if args.check:
        if normalized != original:
            print(
                f"{args.label}: contains {args.home}; run without --check to normalise",
                file=sys.stderr,
            )
            return 1
        return 0

    sys.stdout.write(normalized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
