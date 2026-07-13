import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.instruction_compliance import Issue, check_paths, compare_baseline, load_baseline


ROOT = Path(__file__).resolve().parents[1]


class InstructionComplianceTests(unittest.TestCase):
    def test_current_baseline_matches_tracked_always_loaded_layers(self):
        paths = [
            Path("AGENTS.md"),
            Path("CLAUDE.md"),
            Path(".codex/AGENT.md"),
            Path(".gemini/GEMINI.md"),
            Path("ai/rules/agent-user-global.md"),
        ]
        expected = load_baseline(ROOT / "scripts/fixtures/instruction-compliance-baseline.json")

        self.assertEqual(compare_baseline(check_paths(paths), expected), [])

    def test_scanner_detects_transient_and_absolute_path_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guidance.md"
            path.write_text(
                "## Current (2026-07-13)\n"
                "Done this session; see /Users/example/.config.\n",
                encoding="utf-8",
            )

            rules = {issue.rule for issue in check_paths([path])}

        self.assertEqual(rules, {"dated-current-section", "session-state-marker", "absolute-user-path"})

    def test_baseline_reports_new_and_missing_findings(self):
        actual = [Issue("AGENTS.md", "memory-section", 4, "memory")]
        expected = [Issue("AGENTS.md", "session-state-marker", 5, "session")]

        differences = compare_baseline(actual, expected)

        self.assertEqual({issue.rule for issue in differences}, {"baseline-new", "baseline-missing"})

    def test_baseline_rejects_invalid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps([{"path": "AGENTS.md"}]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "requires path"):
                load_baseline(path)

    def test_cli_passes_reviewed_baseline(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/instruction_compliance.py"),
                "--baseline",
                str(ROOT / "scripts/fixtures/instruction-compliance-baseline.json"),
                "--json",
                "AGENTS.md",
                "CLAUDE.md",
                ".codex/AGENT.md",
                ".gemini/GEMINI.md",
                "ai/rules/agent-user-global.md",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
