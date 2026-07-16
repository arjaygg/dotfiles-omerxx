import tempfile
import unittest
from pathlib import Path

from scripts.shell_syntax_check import check_shell_syntax, summarize_results


class ShellSyntaxCheckTests(unittest.TestCase):
    def test_reports_ok_and_invalid_shell_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / "good.sh"
            bad = root / "bad.sh"
            good.write_text("if true; then\n  echo ok\nfi\n", encoding="utf-8")
            bad.write_text("if true; then\n  echo broken\n", encoding="utf-8")

            results = check_shell_syntax(root, [good, bad])

        self.assertEqual(
            [(result.path, result.status) for result in results],
            [("good.sh", "ok"), ("bad.sh", "invalid")],
        )
        self.assertEqual(
            summarize_results(results),
            {"total": 2, "by_status": {"invalid": 1, "ok": 1}},
        )

    def test_current_tracked_shell_scripts_are_valid_bash_syntax(self):
        root = Path(__file__).resolve().parents[1]
        results = check_shell_syntax(root)

        self.assertTrue(results)
        self.assertEqual([result for result in results if result.status != "ok"], [])


if __name__ == "__main__":
    unittest.main()
