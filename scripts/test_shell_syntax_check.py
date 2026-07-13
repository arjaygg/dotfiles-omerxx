import tempfile
import unittest
from pathlib import Path

from scripts.shell_syntax_check import check_paths


class ShellSyntaxCheckTests(unittest.TestCase):
    def test_valid_shell_files_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "valid.sh").write_text("#!/bin/sh\nprintf '%s\\n' ok\n", encoding="utf-8")
            (root / "nested/valid.bash").write_text("#!/usr/bin/env bash\nset -e\n", encoding="utf-8")

            self.assertEqual(check_paths([root]), [])

    def test_invalid_shell_file_reports_bash_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.sh"
            path.write_text("#!/bin/sh\nif true; then\n", encoding="utf-8")

            issues = check_paths([path])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].path, str(path))
        self.assertIn("syntax error", issues[0].message)

    def test_non_shell_files_are_ignored_and_paths_are_sorted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.sh").write_text("if true; then\n", encoding="utf-8")
            (root / "a.sh").write_text("if true; then\n", encoding="utf-8")
            (root / "notes.txt").write_text("not shell\n", encoding="utf-8")

            issues = check_paths([root])

        self.assertEqual([Path(issue.path).name for issue in issues], ["a.sh", "z.sh"])


if __name__ == "__main__":
    unittest.main()
