import tempfile
import unittest
from pathlib import Path

from scripts.syntax_check import check_syntax, summarize_results


class SyntaxCheckTests(unittest.TestCase):
    def test_reports_ok_and_invalid_json_toml(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good_json = root / "good.json"
            bad_json = root / "bad.json"
            good_toml = root / "good.toml"
            bad_toml = root / "bad.toml"
            good_json.write_text('{"ok": true}\n', encoding="utf-8")
            bad_json.write_text("{broken\n", encoding="utf-8")
            good_toml.write_text("ok = true\n", encoding="utf-8")
            bad_toml.write_text("broken =\n", encoding="utf-8")

            results = check_syntax(
                root,
                [
                    (good_json, "json"),
                    (bad_json, "json"),
                    (good_toml, "toml"),
                    (bad_toml, "toml"),
                ],
            )

        self.assertEqual(
            [(result.path, result.kind, result.status) for result in results],
            [
                ("good.json", "json", "ok"),
                ("bad.json", "json", "invalid"),
                ("good.toml", "toml", "ok"),
                ("bad.toml", "toml", "invalid"),
            ],
        )
        self.assertEqual(
            summarize_results(results),
            {
                "total": 4,
                "by_kind": {"json": 2, "toml": 2},
                "by_status": {"invalid": 2, "ok": 2},
            },
        )

    def test_current_repo_syntax_candidates_are_parseable_or_yaml_parser_unavailable(self):
        root = Path(__file__).resolve().parents[1]
        results = check_syntax(root)

        self.assertTrue(results)
        self.assertEqual([result for result in results if result.status == "invalid"], [])


if __name__ == "__main__":
    unittest.main()
