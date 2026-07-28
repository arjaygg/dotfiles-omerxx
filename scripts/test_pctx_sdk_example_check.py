import tempfile
import unittest
from pathlib import Path

from scripts.pctx_sdk_example_check import check_sdk_examples, summarize_issues


class PctxSdkExampleCheckTests(unittest.TestCase):
    def test_reports_stale_active_guidance_examples(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / "ai/skills/demo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "\n".join(
                    [
                        "const a = await Serena.searchForPattern({ substring_pattern: 'x' });",
                        "const b = await Serena.readMemory({ name: 'START_HERE' });",
                        "const c = await LeanCtx.ctxSearch({ query: 'needle' });",
                    ]
                ),
                encoding="utf-8",
            )

            issues = check_sdk_examples(root)

        self.assertEqual(
            [(issue.kind, issue.line) for issue in issues],
            [
                ("serena-search-for-pattern-call", 1),
                ("serena-read-memory-name-field", 2),
                ("read-memory-name-field", 2),
                ("leanctx-ctxsearch-query-field", 3),
            ],
        )
        self.assertEqual(
            summarize_issues(issues),
            {
                "total": 4,
                "by_kind": {
                    "leanctx-ctxsearch-query-field": 1,
                    "read-memory-name-field": 1,
                    "serena-read-memory-name-field": 1,
                    "serena-search-for-pattern-call": 1,
                },
                "by_path": {"ai/skills/demo/SKILL.md": 4},
            },
        )

    def test_ignores_archived_hooks_and_historical_plans(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archived = root / ".claude/hooks/archive/pre-tool-gate.sh"
            archived.parent.mkdir(parents=True)
            archived.write_text("await Serena.findFile('old')\n", encoding="utf-8")
            historical = root / "plans/old.md"
            historical.parent.mkdir()
            historical.write_text("Serena.readMemory({ name: 'START_HERE' })\n", encoding="utf-8")

            issues = check_sdk_examples(root)

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
