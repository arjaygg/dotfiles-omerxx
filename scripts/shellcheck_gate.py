#!/usr/bin/env python3
"""Lint governed shell scripts with shellcheck at error severity.

Why this exists: `scripts/shell_syntax_check.py` runs `bash -n`, which is a *syntax parse*. It
accepts code that parses but is wrong. The only other shellcheck invocation in the repo is inside
`scripts/ai/validate-changeset.sh`, which lints just the *staged* changeset and is called only by
the auto-ship skill — not by CI and not by `git/hooks/pre-commit`. So repo-wide shell lint had no
coverage.

It found a real defect on its first run: `.cursor/hooks/before-shell-git-commit.sh` had a heredoc
overriding its piped stdin (SC2259), which made the Cursor commit gate fail *open* — it allowed
every raw `git commit` in a hyper-atomic repo, the exact opposite of its purpose.

Severity is `error`, not `warning`, on purpose: the governed set carries 113 warning-level findings
today, so gating on warnings would be red from day one and would train people to ignore it. Raising
the bar later is a deliberate, separate decision.

The file list is NOT redefined here — it reuses `shell_syntax_check.candidate_files()` so the two
gates can never drift apart on which files count as governed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from shell_syntax_check import candidate_files  # noqa: E402

SEVERITY = "error"


def run_shellcheck(root: Path, files: Sequence[Path]) -> tuple[list[dict], str | None]:
    """Returns (findings, error). `error` is set when shellcheck could not run at all."""
    if not files:
        return [], None
    if shutil.which("shellcheck") is None:
        return [], "shellcheck is not installed"

    proc = subprocess.run(
        ["shellcheck", f"--severity={SEVERITY}", "--format=json", *[str(f) for f in files]],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    # shellcheck exits 1 when it reports findings, which is not a failure to run. Only treat
    # unparseable output as a real error, so a lint hit and a broken toolchain stay distinguishable.
    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return [], f"could not parse shellcheck output (exit {proc.returncode}): {proc.stderr[:300]}"

    findings = [
        {
            "path": str(Path(item.get("file", "")).relative_to(root))
            if Path(item.get("file", "")).is_absolute() and str(root) in item.get("file", "")
            else item.get("file", ""),
            "line": item.get("line"),
            "column": item.get("column"),
            "code": f"SC{item.get('code')}",
            "message": item.get("message", ""),
        }
        for item in raw
    ]
    findings.sort(key=lambda f: (f["path"], f["line"] or 0, f["code"]))
    return findings, None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--summary", action="store_true", help="emit JSON instead of lines")
    args = parser.parse_args(argv)

    root = args.repo_root.resolve()
    files = candidate_files(root)
    findings, error = run_shellcheck(root, files)

    if error:
        # Fail loudly rather than silently passing: a gate that cannot run is not a green gate.
        print(f"shellcheck gate could not run: {error}", file=sys.stderr)
        return 1

    if args.summary:
        by_code: dict[str, int] = {}
        for f in findings:
            by_code[f["code"]] = by_code.get(f["code"], 0) + 1
        print(json.dumps({
            "shell_files": len(files),
            "severity": SEVERITY,
            "findings": len(findings),
            "by_code": dict(sorted(by_code.items())),
            "paths": sorted({f["path"] for f in findings}),
        }, indent=2))
    else:
        print(f"shellcheck: {len(findings)} {SEVERITY}-severity finding(s) over {len(files)} files")
        for f in findings:
            print(f"  {f['path']}:{f['line']}:{f['column']}: {f['code']}: {f['message']}")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
