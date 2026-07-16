import tempfile
import unittest
from pathlib import Path

from scripts.guidance_adapter_check import check_guidance_adapters, summarize_results


def write(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class GuidanceAdapterCheckTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        write(root / "AGENTS.md")
        write(root / "docs/agent-configuration-architecture.md")
        write(root / "ai/rules/agent-user-global.md")
        write(root / "ai/rules/tool-priority.md")
        write(root / "ai/rules/context-and-compaction.md")
        write(root / "CLAUDE.md", "@AGENTS.md\n")
        write(
            root / ".claude/CLAUDE.md",
            "\n".join(
                [
                    "@../ai/rules/agent-user-global.md",
                    "@../ai/rules/tool-priority.md",
                    "@../ai/rules/context-and-compaction.md",
                ]
            ),
        )
        write(
            root / ".gemini/GEMINI.md",
            "\n".join(["@../ai/rules/agent-user-global.md", "@../ai/rules/tool-priority.md"]),
        )
        write(
            root / ".cursor/rules.md",
            "\n".join(
                [
                    "@../ai/rules/agent-user-global.md",
                    "@../ai/rules/tool-priority.md",
                    "@../ai/rules/context-and-compaction.md",
                ]
            ),
        )
        write(
            root / ".codex/config.toml",
            'model_instructions_file = "~/.dotfiles/ai/rules/agent-user-global.md"\n'
            'project_doc_fallback_filenames = ["AGENTS.md"]\n',
        )
        write(root / ".gemini/settings.json", '{"context": {"fileName": ["AGENTS.md"]}}\n')

    def test_valid_guidance_adapter_layout_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)

            results = check_guidance_adapters(root)

        self.assertFalse([result for result in results if result.status == "fail"])
        summary = summarize_results(results)
        self.assertEqual(summary["by_status"], {"ok": summary["total"]})

    def test_missing_shared_import_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            write(root / ".gemini/GEMINI.md", "@../ai/rules/tool-priority.md\n")

            results = check_guidance_adapters(root)

        self.assertIn(
            ("gemini-imports-global", ".gemini/GEMINI.md", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_current_repo_guidance_adapters_pass(self):
        root = Path(__file__).resolve().parents[1]
        results = check_guidance_adapters(root)

        self.assertFalse([result for result in results if result.status == "fail"])


if __name__ == "__main__":
    unittest.main()
