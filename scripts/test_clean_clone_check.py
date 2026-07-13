import tempfile
import unittest
from pathlib import Path

from scripts.clean_clone_check import CleanCloneError, run_check


ROOT = Path(__file__).resolve().parents[1]


class CleanCloneCheckTests(unittest.TestCase):
    def test_clean_clone_runs_proposal_only_setup_for_all_clients(self):
        result = run_check(ROOT)

        self.assertEqual(
            result["clients"],
            ["claude", "codex", "cursor", "gemini", "pctx", "windsurf"],
        )
        self.assertEqual(result["client_count"], 6)
        self.assertFalse(result["runtime_writes"])

    def test_missing_setup_script_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            with self.assertRaises(CleanCloneError):
                run_check(root)

if __name__ == "__main__":
    unittest.main()
