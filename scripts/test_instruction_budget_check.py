import tempfile
import unittest
from pathlib import Path

from scripts.instruction_budget_check import (
    check_client_instruction_budgets,
    check_instruction_budgets,
    summarize_results,
)


class InstructionBudgetCheckTests(unittest.TestCase):
    def test_reports_ok_missing_and_over_budget(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "small.md").write_text("abc", encoding="utf-8")
            (root / "large.md").write_text("abcdef", encoding="utf-8")

            results = check_instruction_budgets(
                root,
                {
                    "large.md": 3,
                    "missing.md": 10,
                    "small.md": 3,
                },
            )

        self.assertEqual(
            [(result.path, result.status) for result in results],
            [
                ("large.md", "over-budget"),
                ("missing.md", "missing"),
                ("small.md", "ok"),
            ],
        )
        self.assertEqual(
            summarize_results(results),
            {
                "total": 3,
                "by_status": {"missing": 1, "ok": 1, "over-budget": 1},
                "max_overage_bytes": 3,
            },
        )

    def test_current_instruction_files_are_within_budget(self):
        root = Path(__file__).resolve().parents[1]
        results = check_instruction_budgets(root)

        self.assertTrue(results)
        self.assertEqual(
            [result for result in results if result.status != "ok"],
            [],
        )

    def test_client_budgets_follow_transitive_imports_and_deduplicate_real_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shared = root / "shared.md"
            shared.write_text("shared text", encoding="utf-8")
            nested = root / "nested.md"
            nested.write_text("@shared.md\n", encoding="utf-8")
            adapter = root / "adapter.md"
            adapter.write_text("@nested.md\n@shared.md\n", encoding="utf-8")

            results = check_client_instruction_budgets(
                root,
                {"test-client": "adapter.md"},
            )

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.client, "test-client")
        self.assertEqual(result.files, 3)
        self.assertEqual(result.actual_bytes, len("@nested.md\n@shared.md\n@shared.md\nshared text"))
        self.assertEqual(result.estimated_tokens, (result.actual_bytes + 3) // 4)


if __name__ == "__main__":
    unittest.main()
