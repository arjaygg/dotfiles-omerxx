import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.effective_context import build_report, resolve_markdown_chain


ROOT = Path(__file__).resolve().parents[1]


class EffectiveContextTests(unittest.TestCase):
    def test_resolver_follows_imports_once_in_deterministic_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CLAUDE.md").write_text("# adapter\n@AGENTS.md\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# policy\n@ai/rules/core.md\n", encoding="utf-8")
            (root / "ai/rules").mkdir(parents=True)
            (root / "ai/rules/core.md").write_text("stable\n", encoding="utf-8")

            result = resolve_markdown_chain(root, Path("CLAUDE.md"))

        self.assertEqual(result["files"], ["CLAUDE.md", "AGENTS.md", "ai/rules/core.md"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["cycles"], [])

    def test_resolver_reports_missing_imports_and_cycles_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.md").write_text("@two.md\n@missing.md\n", encoding="utf-8")
            (root / "two.md").write_text("@one.md\n", encoding="utf-8")

            result = resolve_markdown_chain(root, Path("one.md"))

        self.assertEqual(result["files"], ["one.md", "two.md"])
        self.assertEqual(result["missing"], ["missing.md"])
        self.assertEqual(result["cycles"], [["one.md", "two.md", "one.md"]])

    def test_resolver_reports_imports_that_escape_the_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            (root / "entry.md").write_text("@../../outside.md\n", encoding="utf-8")

            result = resolve_markdown_chain(root, Path("entry.md"))

        self.assertEqual(result["files"], ["entry.md"])
        self.assertEqual(result["outside_root"], ["<outside-root>"])

    def test_report_measures_clients_and_deduplicates_aggregate_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("one two\n", encoding="utf-8")
            (root / "ai/rules").mkdir(parents=True)
            (root / "ai/rules/agent-user-global.md").write_text("global\n", encoding="utf-8")
            (root / "ai/config/codex").mkdir(parents=True)
            (root / "ai/config/codex/config.base.toml").write_text(
                'model_instructions_file = "~/.dotfiles/ai/rules/agent-user-global.md"\n'
                'project_doc_fallback_filenames = ["AGENTS.md"]\n',
                encoding="utf-8",
            )
            (root / ".gemini").mkdir()
            (root / ".gemini/settings.json").write_text(
                json.dumps({"context": {"fileName": ["AGENTS.md"]}}), encoding="utf-8"
            )

            report = build_report(root)

        self.assertEqual(
            list(report["clients"]), ["repository", "claude", "codex", "gemini"]
        )
        self.assertEqual(report["clients"]["claude"]["metrics"]["lines"], 2)
        self.assertEqual(report["clients"]["codex"]["files"], [
            "ai/rules/agent-user-global.md",
            "AGENTS.md",
        ])
        self.assertEqual(report["aggregate"]["files"], [
            "AGENTS.md",
            "CLAUDE.md",
            "ai/rules/agent-user-global.md",
        ])
        self.assertEqual(report["aggregate"]["metrics"]["lines"], 3)

    def test_cli_emits_stable_json_and_budget_failure(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/effective_context.py"),
                "--root",
                str(ROOT),
                "--max-lines",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(list(payload["clients"]), ["repository", "claude", "codex", "gemini"])
        self.assertTrue(payload["budget_violations"])


if __name__ == "__main__":
    unittest.main()
