import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.context_health_report import build_report


ROOT = Path(__file__).resolve().parents[1]


class ContextHealthReportTests(unittest.TestCase):
    def test_direct_and_module_help_invocations_load_without_runtime_dependencies(self):
        invocations = (
            [sys.executable, "scripts/context_health_report.py", "--help"],
            [sys.executable, "-m", "scripts.context_health_report", "--help"],
        )
        for command in invocations:
            with self.subTest(command=command):
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_combines_privacy_safe_sections(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".claude").mkdir()
            (root / ".claude/CLAUDE.md").write_text("small", encoding="utf-8")
            report = build_report(
                root,
                [],
                lean_summary={"available": True, "tokens_saved": 10},
                containers=[
                    {
                        "name": "headroom-default",
                        "kind": "persistent",
                        "health": "healthy",
                    }
                ],
                ccr={"total": 0, "invalid": 0, "ok": True},
            )
        self.assertIn("routing", report)
        self.assertIn("instructions", report)
        self.assertEqual(report["leanctx"]["tokens_saved"], 10)
        self.assertTrue(report["headroom"]["containers"]["ok"])


if __name__ == "__main__":
    unittest.main()
