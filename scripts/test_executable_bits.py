"""Asserts the executable bit on scripts that are invoked directly.

Why this exists: `ctx_patch` (lean-ctx) rewrites a file without preserving its mode, so editing a
shell script silently drops 100755 -> 100644. It happened twice in one session — `setup.sh` and
`.claude/scripts/stack-ship.sh` — and both times the only signal was a `mode change` line in
`git commit` output that is easy to miss. Nothing in the suite caught it.

The consequence is not cosmetic: `./setup.sh` is the documented fresh-machine install path, and the
`stack` scripts are invoked as executables by the skills. A non-executable mode breaks them with a
bare "permission denied" that looks nothing like an editing mistake.

Scope: files that are actually invoked as `./x` or `<path>/x`, not every script. A library sourced
with `.`/`source` does not need the bit, so requiring it everywhere would be noise.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Entry points invoked directly. Verified present at the time of writing; a missing file fails
# loudly rather than being skipped, because a renamed entry point should be noticed here.
MUST_BE_EXECUTABLE = [
    "setup.sh",
    ".claude/scripts/stack",
    ".claude/scripts/stack-ship.sh",
    "scripts/ai/commit.sh",
    "scripts/ai/checkpoint.sh",
    "scripts/ai/atomic-status.sh",
    "scripts/ai/pipeline-status.sh",
    "scripts/ai/validate-changeset.sh",
    "scripts/ai/autonomy-tier.sh",
    "scripts/ai/git_lifecycle.py",
]


def git_mode(rel: str) -> str:
    """The mode git has recorded, which is what a fresh clone gets."""
    r = subprocess.run(["git", "ls-files", "-s", "--", rel],
                       cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    return r.stdout.split()[0]


class ExecutableBitTests(unittest.TestCase):
    def test_entry_points_are_executable_in_git(self):
        broken = []
        for rel in MUST_BE_EXECUTABLE:
            p = ROOT / rel
            if not p.exists():
                broken.append(f"{rel}: MISSING from the worktree")
                continue
            mode = git_mode(rel)
            if not mode:
                broken.append(f"{rel}: not tracked by git")
            elif mode != "100755":
                broken.append(f"{rel}: git mode {mode}, expected 100755")
        self.assertEqual(
            broken, [],
            "entry-point scripts lost their executable bit — likely an editor that does not "
            "preserve mode. Restore with: git update-index --chmod=+x <path>\n  "
            + "\n  ".join(broken),
        )

    def test_entry_points_are_executable_on_disk(self):
        """git mode and filesystem mode can disagree; a fresh clone honours git, but the current
        working tree is what a local `./script` run actually uses."""
        broken = [rel for rel in MUST_BE_EXECUTABLE
                  if (ROOT / rel).exists() and not (ROOT / rel).stat().st_mode & 0o111]
        self.assertEqual(broken, [], f"not executable on disk: {broken}")


if __name__ == "__main__":
    unittest.main()
