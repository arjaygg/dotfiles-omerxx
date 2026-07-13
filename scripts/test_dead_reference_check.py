import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.dead_reference_check import Finding, compare_baseline, scan_root


ROOT = Path(__file__).resolve().parents[1]


class DeadReferenceTests(unittest.TestCase):
    def test_scan_reports_broken_distribution_symlinks_without_following_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / ".claude/commands"
            commands.mkdir(parents=True)
            (commands / "old.md").symlink_to("../../ai/commands/old.md")

            findings = scan_root(root)

        self.assertEqual(
            findings,
            [
                Finding(
                    "broken-symlink",
                    ".claude/commands/old.md",
                    "../../ai/commands/old.md",
                    "symlink target does not exist",
                )
            ],
        )

    def test_scan_reports_only_missing_explicit_repository_script_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / "ai/commands"
            commands.mkdir(parents=True)
            (root / "scripts/existing.py").parent.mkdir()
            (root / "scripts/existing.py").write_text("pass\n", encoding="utf-8")
            (commands / "example.md").write_text(
                "python3 scripts/existing.py\n"
                "python3 scripts/missing.py\n"
                "https://example.test/scripts/not-a-local-file.py\n",
                encoding="utf-8",
            )

            findings = scan_root(root)

        self.assertEqual(
            findings,
            [
                Finding(
                    "missing-script-reference",
                    "ai/commands/example.md",
                    "scripts/missing.py",
                    "referenced repository script does not exist",
                )
            ],
        )

    def test_compare_baseline_reports_added_and_removed_findings(self):
        baseline = [
            Finding("broken-symlink", ".claude/commands/old.md", "old", "missing"),
        ]
        current = baseline + [
            Finding("missing-script-reference", "ai/commands/a.md", "scripts/new.py", "missing"),
        ]

        comparison = compare_baseline(current, baseline)

        self.assertEqual(comparison["added"], [current[1].as_dict()])
        self.assertEqual(comparison["removed"], [])
        self.assertFalse(comparison["match"])

    def test_cli_emits_json_and_nonzero_when_findings_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / "ai/commands"
            commands.mkdir(parents=True)
            (commands / "example.md").write_text("python3 scripts/missing.py\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/dead_reference_check.py"), "--root", str(root), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["findings"][0]["reference"], "scripts/missing.py")

    def test_cli_accepts_an_unchanged_reviewed_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / ".claude/commands"
            commands.mkdir(parents=True)
            (commands / "old.md").symlink_to("../../ai/commands/old.md")
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "findings": [
                            {
                                "kind": "broken-symlink",
                                "source": ".claude/commands/old.md",
                                "reference": "../../ai/commands/old.md",
                                "message": "symlink target does not exist",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/dead_reference_check.py"),
                    "--root",
                    str(root),
                    "--baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn('"match": true', result.stdout)


if __name__ == "__main__":
    unittest.main()
